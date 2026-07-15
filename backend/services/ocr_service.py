"""Prescription OCR via Gemini, with RxNorm medicine-name validation.

Requires ``GEMINI_API_KEY`` in the environment (see ``docs/environment.md``).
Response JSON field names are part of the client contract and must not change.

Heavy imports (OpenCV, ``google.genai``) load only when the related functions run.
"""

from __future__ import annotations

import json
import os

import requests

from backend.core.config import get_gemini_api_key


def clean_image(input_path: str, output_path: str) -> None:
    """Preprocess a prescription image (grayscale, threshold, denoise) and save it.

    Used by the module ``__main__`` demo path; the live API uploads the raw image
    to Gemini without this preprocess step.
    """
    import cv2

    image = cv2.imread(input_path, cv2.IMREAD_COLOR)
    gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)

    thresh = cv2.adaptiveThreshold(
        gray, 255,
        cv2.ADAPTIVE_THRESH_GAUSSIAN_C,
        cv2.THRESH_BINARY,
        11, 2
    )

    denoised = cv2.fastNlMeansDenoising(thresh, h=30)
    cv2.imwrite(output_path, denoised)


def is_valid_medicine(name: str) -> bool:
    """Return True if NIH RxNorm resolves ``name`` to an RxCUI."""
    url = f"https://rxnav.nlm.nih.gov/REST/rxcui.json?name={name}"
    try:
        r = requests.get(url, timeout=3)
        return bool(r.json().get("idGroup", {}).get("rxnormId"))
    except Exception:
        return False


def validate_extracted_data(data: dict) -> dict:
    """Filter ``Medicines Prescribed`` to names accepted by RxNorm."""
    meds = data.get("Medicines Prescribed", [])
    if meds is None:
        return data

    valid_meds = [m for m in meds if is_valid_medicine(m)]
    data["Medicines Prescribed"] = valid_meds if valid_meds else None
    return data


def extract_json(image_path: str) -> dict:
    """Upload ``image_path`` to Gemini and return structured prescription fields.

    Returns a dict with keys: Patient's Name, Medicines Prescribed, Doctor's Name,
    Clinic Name, Date. Medicine names are filtered through RxNorm when possible.
    """
    from google import genai
    from google.genai import types

    # Prefer a current Flash model; override with GEMINI_OCR_MODEL if needed.
    model = os.getenv("GEMINI_OCR_MODEL", "gemini-3-flash-preview").strip() or "gemini-3-flash-preview"

    client = genai.Client(api_key=get_gemini_api_key())
    file = client.files.upload(file=image_path)

    contents = [
        types.Content(
            role="user",
            parts=[
                types.Part.from_uri(
                    file_uri=file.uri,
                    mime_type=file.mime_type,
                ),
            ],
        )
    ]

    generate_content_config = types.GenerateContentConfig(
        temperature=1,
        top_p=0.95,
        top_k=40,
        max_output_tokens=8192,
        response_mime_type="application/json",
        system_instruction=[
            types.Part.from_text(text="""
You are a medical assistant AI. A scanned image of a handwritten doctor's prescription will be provided.

From this prescription, extract the following structured information. If any information is missing or unreadable, return `null` for that field.

Respond ONLY with a valid JSON object with these exact fields:

- "Patient's Name": Full name of the patient as a string.
- "Medicines Prescribed": A list of valid medicine names (no dosages, instructions, or duplicates). Only include real medicines. Return `null` if none are found.
- "Doctor's Name": Full name of the doctor as a string.
- "Clinic Name": Name of the clinic or hospital (if present).
- "Date": Date on the prescription in YYYY-MM-DD format, if written.

Strictly return a JSON object. Do not include any explanation or markdown.
            """)
        ],
    )

    extracted_text = ""
    for chunk in client.models.generate_content_stream(
        model=model,
        contents=contents,
        config=generate_content_config,
    ):
        piece = getattr(chunk, "text", None)
        if piece:
            extracted_text += piece

    try:
        data = json.loads(extracted_text)
        return validate_extracted_data(data)
    except json.JSONDecodeError as e:
        print("Gemini returned invalid JSON:\n")
        print(extracted_text)
        raise ValueError(f"JSON parse error: {str(e)}") from e


if __name__ == "__main__":
    input_img = "image.png"
    cleaned_img = "cleaned_newest.png"

    if not os.path.exists(input_img):
        print(f"Image not found: {input_img}")
    else:
        print("Cleaning image...")
        clean_image(input_img, cleaned_img)

        print("Sending to Gemini...")
        result = extract_json(cleaned_img)

        print("\nFinal Extracted and Validated Data:\n")
        print(json.dumps(result, indent=2))
