"""HTTP routes for prescription image OCR with object storage."""

from __future__ import annotations

import os
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.core.deps import require_roles
from backend.core.roles import STAFF_ROLES
from backend.db import models
from backend.services.ocr_service import extract_json
from backend.services.storage import build_prescription_key, get_storage

router = APIRouter()


def _safe_unlink(path: str, *, attempts: int = 5) -> None:
    """Delete a temp path; retry briefly on Windows file locks."""
    for i in range(attempts):
        try:
            if os.path.exists(path):
                os.unlink(path)
            return
        except OSError:
            if i == attempts - 1:
                return
            time.sleep(0.05 * (i + 1))


def _storage_error(exc: Exception) -> HTTPException:
    text = str(exc)
    lower = text.lower()
    if "credentials" in lower or "accesskey" in lower or "unable to locate credentials" in lower:
        message = (
            "Prescription storage is unavailable: cloud credentials are missing or invalid. "
            "Check STORAGE_BACKEND / AWS keys, or switch to STORAGE_BACKEND=local."
        )
    elif "nosuchbucket" in lower or "bucket" in lower and "not" in lower:
        message = (
            "Prescription storage is unavailable: S3 bucket is missing or misconfigured. "
            "Verify S3_BUCKET and region."
        )
    else:
        message = (
            "Could not store the prescription image. "
            "Check STORAGE_BACKEND (local or s3) and try again."
        )
    return HTTPException(
        status_code=503,
        detail={
            "code": "STORAGE_UNAVAILABLE",
            "message": message,
            "details": {"reason": text},
        },
    )


def _ocr_provider_error(exc: Exception) -> HTTPException:
    text = str(exc)
    lower = text.lower()
    if "gemini_api_key" in lower or "api key" in lower or "api_key" in lower:
        message = (
            "OCR provider is not configured. Set GEMINI_API_KEY in the backend .env "
            "and restart the API."
        )
        code = "OCR_CONFIG"
    elif "permission" in lower or "403" in lower or "401" in lower:
        message = (
            "Gemini rejected the OCR request (auth/permission). "
            "Verify GEMINI_API_KEY and model access."
        )
        code = "OCR_PROVIDER_AUTH"
    elif "quota" in lower or "rate" in lower or "429" in lower:
        message = "Gemini rate limit/quota hit. Wait a moment and retry OCR."
        code = "OCR_PROVIDER_QUOTA"
    elif "404" in lower or "not found" in lower or "is not found" in lower:
        message = (
            "Gemini model is unavailable. Set GEMINI_OCR_MODEL to a current model "
            "(e.g. gemini-2.5-flash) and redeploy."
        )
        code = "OCR_PROVIDER_MODEL"
    elif "winerror 32" in lower or "being used by another process" in lower:
        message = (
            "Temporary image file was locked on Windows during OCR. "
            "Retry the upload; if it persists, restart the API."
        )
        code = "OCR_TEMP_FILE"
    else:
        message = (
            "OCR failed while reading the prescription with Gemini. "
            "Try another image or check the API logs."
        )
        code = "OCR_FAILED"
    return HTTPException(
        status_code=503 if code.startswith("OCR_PROVIDER") or code == "OCR_CONFIG" else 500,
        detail={"code": code, "message": message, "details": {"reason": text}},
    )


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    user: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Upload a prescription image to configured storage, run OCR, return fields + file_key.

    Durable copy goes to local disk or S3 (``STORAGE_BACKEND``). Gemini still needs a
    short-lived local temp file; on Windows that file must not stay locked while we write it.
    """
    if not file.filename:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UPLOAD_INVALID",
                "message": "Choose an image file before running OCR.",
            },
        )

    contents = await file.read()
    if not contents:
        raise HTTPException(
            status_code=400,
            detail={
                "code": "UPLOAD_EMPTY",
                "message": "The uploaded file is empty. Pick a clear prescription photo.",
            },
        )

    try:
        storage = get_storage()
    except Exception as exc:
        raise _storage_error(exc) from exc

    key = build_prescription_key(user.id, file.filename)
    content_type = file.content_type or "application/octet-stream"
    try:
        storage.save_bytes(key, contents, content_type=content_type)
    except Exception as exc:
        raise _storage_error(exc) from exc

    suffix = Path(file.filename).suffix or ".img"
    fd, image_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        Path(image_path).write_bytes(contents)
        result = extract_json(image_path)
        if isinstance(result, dict):
            meds = result.get("Medicines Prescribed")
            if not meds:
                result = {
                    **result,
                    "file_key": key,
                    "warning": (
                        "No medicines were detected. Check image quality or enter lines manually."
                    ),
                }
            else:
                result = {**result, "file_key": key}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise _ocr_provider_error(e) from e
    finally:
        _safe_unlink(image_path)
