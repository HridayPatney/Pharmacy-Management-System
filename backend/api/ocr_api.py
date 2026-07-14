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
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    contents = await file.read()
    if not contents:
        raise HTTPException(status_code=400, detail="Uploaded file is empty.")

    storage = get_storage()
    key = build_prescription_key(user.id, file.filename)
    content_type = file.content_type or "application/octet-stream"
    try:
        storage.save_bytes(key, contents, content_type=content_type)
    except Exception as exc:
        raise HTTPException(status_code=503, detail=f"Failed to store upload: {exc}") from exc

    suffix = Path(file.filename).suffix or ".img"
    # Create + close the handle before writing (Windows cannot overwrite an open NamedTemporaryFile).
    fd, image_path = tempfile.mkstemp(suffix=suffix)
    os.close(fd)
    try:
        Path(image_path).write_bytes(contents)
        result = extract_json(image_path)
        if isinstance(result, dict):
            result = {**result, "file_key": key}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}") from e
    finally:
        _safe_unlink(image_path)
