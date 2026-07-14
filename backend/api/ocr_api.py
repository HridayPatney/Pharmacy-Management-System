"""HTTP routes for prescription image OCR with object storage."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile

from backend.core.deps import require_roles
from backend.core.roles import STAFF_ROLES
from backend.db import models
from backend.services.ocr_service import extract_json
from backend.services.storage import build_prescription_key, get_storage

router = APIRouter()


@router.post("/extract")
async def extract(
    file: UploadFile = File(...),
    user: models.User = Depends(require_roles(*STAFF_ROLES)),
):
    """Upload a prescription image to configured storage, run OCR, return fields + file_key.

    Uses local disk by default (``STORAGE_BACKEND=local``) or S3 when configured.
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
    image_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            storage.materialize_to_path(key, tmp.name)
            image_path = tmp.name

        result = extract_json(image_path)
        if isinstance(result, dict):
            result = {**result, "file_key": key}
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}") from e
    finally:
        if image_path and os.path.exists(image_path):
            try:
                os.unlink(image_path)
            except OSError:
                pass
