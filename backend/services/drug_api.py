# drug_info_pipeline.py

import requests
import time
import json

# Wikimedia requires a descriptive User-Agent (403 without one).
_HTTP_HEADERS = {
    "User-Agent": "PharmacyManagementSystem/1.0 (local-dev; drug-summary)",
    "Accept": "application/json",
}


def _get(url: str, *, timeout: int = 10):
    return requests.get(url, headers=_HTTP_HEADERS, timeout=timeout)


# 1. Wikipedia API

def fetch_from_wikipedia(drug_name):
    url = f"https://en.wikipedia.org/api/rest_v1/page/summary/{drug_name.replace(' ', '_')}"
    try:
        res = _get(url)
        if res.status_code == 200:
            data = res.json()
            return data.get("extract")
    except Exception as e:
        print(f"Wikipedia error: {e}")
    return None

# 2. PubChem PUG REST API

def fetch_from_pubchem(drug_name):
    try:
        cid_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug/compound/name/{drug_name}/cids/JSON"
        cid_res = _get(cid_url).json()
        cid = cid_res["IdentifierList"]["CID"][0]

        description_url = f"https://pubchem.ncbi.nlm.nih.gov/rest/pug_view/data/compound/{cid}/JSON"
        desc_res = _get(description_url).json()

        sections = desc_res["Record"].get("Section", [])
        for section in sections:
            if section.get("TOCHeading") == "Description":
                for info in section.get("Information", []):
                    return info.get("Value", {}).get("StringWithMarkup", [{}])[0].get("String")
    except Exception as e:
        print(f"PubChem error: {e}")
    return None

# 3. OpenFDA Drug Labeling API

def fetch_from_openfda(drug_name):
    try:
        url = f"https://api.fda.gov/drug/label.json?search=openfda.brand_name:{drug_name.lower()}&limit=1"
        res = _get(url).json()
        results = res.get("results", [])
        if results:
            return results[0].get("description", [None])[0]
    except Exception as e:
        print(f"OpenFDA error: {e}")
    return None


# 4. Gemini (last resort when public APIs fail)

def fetch_from_gemini(drug_name):
    """Ask Gemini for a short factual summary. Returns None if key/API unavailable."""
    try:
        import os

        from google import genai

        # Ensure ``.env`` is loaded; do not raise if key is missing.
        import backend.core.config  # noqa: F401

        key = os.getenv("GEMINI_API_KEY", "").strip()
        if not key:
            return None

        client = genai.Client(api_key=key)
        prompt = (
            f"Write a concise 2-4 sentence factual clinical summary of the medicine "
            f'"{drug_name}" for embedding-based similarity search. Cover indication and '
            f"drug class if known. Plain text only — no markdown, lists, or disclaimers. "
            f"If you do not recognize it as a medicine, reply exactly: UNKNOWN"
        )
        response = client.models.generate_content(
            model=os.getenv("GEMINI_OCR_MODEL", "gemini-3-flash-preview").strip()
            or "gemini-3-flash-preview",
            contents=prompt,
        )
        text = (getattr(response, "text", None) or "").strip()
        if not text or text.upper().startswith("UNKNOWN"):
            return None
        return text
    except Exception as e:
        print(f"Gemini drug-summary error: {e}")
        return None


# Fallback orchestrator

def fetch_drug_summary(drug_name):
    """Resolve a medicine description: Wikipedia → PubChem → OpenFDA → Gemini."""
    summary = fetch_from_wikipedia(drug_name)
    if not summary:
        summary = fetch_from_pubchem(drug_name)
    if not summary:
        summary = fetch_from_openfda(drug_name)
    if not summary:
        summary = fetch_from_gemini(drug_name)
    return summary or "No data found."

# Example usage
if __name__ == "__main__":
    drugs = ["Paracetamol", "Ibuprofen", "Amoxicillin", "Aspirin"]
    for drug in drugs:
        print(f"\nFetching info for: {drug}")
        summary = fetch_drug_summary(drug)
        print(summary[:500] + ("..." if len(summary) > 500 else ""))
        time.sleep(1)
