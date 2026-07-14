"""HTTP routes for prescription image OCR."""

from fastapi import APIRouter, UploadFile, File, HTTPException
from backend.services.ocr_service import extract_json
import tempfile

router = APIRouter()


@router.post("/extract")
async def extract(file: UploadFile = File(...)):
    """Accept an uploaded prescription image and return structured JSON fields."""
    try:
        suffix = file.filename.split(".")[-1]
        with tempfile.NamedTemporaryFile(delete=False, suffix=f".{suffix}") as tmp:
            contents = await file.read()
            tmp.write(contents)
            image_path = tmp.name

        # Run Gemini OCR
        result = extract_json(image_path)
        return result

    except Exception as e:
        raise HTTPException(status_code=500, detail=f"OCR failed: {str(e)}")
