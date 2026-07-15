"""Local smoke test for Gemini OCR (does not print secrets)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env")


def main() -> int:
    if not os.getenv("GEMINI_API_KEY", "").strip():
        print("FAIL: GEMINI_API_KEY not set in .env")
        return 1

    try:
        from PIL import Image, ImageDraw
    except ImportError:
        print("FAIL: pillow not installed (pip install pillow)")
        return 1

    img_path = ROOT / "uploads" / "_ocr_smoke.png"
    img_path.parent.mkdir(parents=True, exist_ok=True)
    im = Image.new("RGB", (640, 360), "white")
    draw = ImageDraw.Draw(im)
    draw.text((40, 40), "Dr. Smith Clinic", fill="black")
    draw.text((40, 90), "Patient: Test Patient", fill="black")
    draw.text((40, 140), "Rx: Paracetamol", fill="black")
    draw.text((40, 190), "Ibuprofen", fill="black")
    im.save(img_path)

    model = os.getenv("GEMINI_OCR_MODEL", "gemini-3-flash-preview")
    print(f"model={model}")
    print(f"image={img_path}")

    from backend.services.ocr_service import extract_json

    result = extract_json(str(img_path))
    print("ok=True")
    print("patient=", result.get("Patient's Name"))
    print("meds=", result.get("Medicines Prescribed"))
    print("doctor=", result.get("Doctor's Name"))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"FAIL: {type(exc).__name__}: {exc}")
        raise SystemExit(1)
