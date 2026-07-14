"""HTTP routes for prescription image OCR."""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from fastapi import APIRouter, File, HTTPException, UploadFile

from backend.services.ocr_service import extract_json

router = APIRouter()


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Accept an uploaded prescription image and return structured JSON fields.

    Temporary upload files are always deleted after processing (or on failure).
    """
    if not file.filename:
        raise HTTPException(status_code=400, detail="Uploaded file must have a filename.")

    suffix = Path(file.filename).suffix or ".img"
    image_path: str | None = None
    try:
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            contents = await file.read()
            tmp.write(contents)
            image_path = tmp.name

        return extract_json(image_path)
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
