"""Experimental PaddleOCR prescription parser (unused by production).

Production OCR uses Gemini via ``backend.services.ocr_service``.
Requires a separate PaddleOCR install; do not import this from the API.
"""

from paddleocr import PaddleOCR
import re
import os

# Initialize OCR engine only when this experimental script is run as a module
ocr = PaddleOCR(use_angle_cls=True, lang="en")

def extract_prescription_text(image_path: str) -> dict:
    result = ocr.ocr(image_path)

    all_text = []
    for line in result:
        for box in line:
            text = box[1][0]
            all_text.append(text)

    # Combine text into one string
    raw_text = " ".join(all_text)

    # Extract medicine-like words and date
    medicines = re.findall(r'\b([A-Z][a-zA-Z0-9\-]{2,})\b', raw_text)
    date_match = re.search(r'\b(\d{1,2}[/-]\d{1,2}[/-]\d{2,4})\b', raw_text)

    return {
        "raw_text": raw_text,
        "medicines": list(set(medicines)),
        "date": date_match.group(0) if date_match else None
    }

# 🔽 HARD-CODED TEST SECTION

test_image = os.path.join(os.getcwd(), "image.png")
    
if not os.path.exists(test_image):
    print(f"❌ File not found: {test_image}")
else:
    print(f"📂 Running OCR on: {test_image}")
    output = extract_prescription_text(test_image)
    print("\n🧾 OCR Output:\n")
    for key, value in output.items():
        print(f"{key}: {value}")
