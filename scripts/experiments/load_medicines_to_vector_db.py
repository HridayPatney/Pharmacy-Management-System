"""Experimental: seed Chroma with sample medicines and print similarity hits.

Not part of the production API. Requires full ML deps and a configured DB path.

Run from the repository root::

    python scripts/experiments/load_medicines_to_vector_db.py
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.drug_api import fetch_drug_summary
from backend.services.vector_search import add_medicine_to_vector_db, search_similar_medicines


def find_similar_to_medicine(medicine_name: str, top_k: int = 5) -> list:
    """Fetch a drug summary and return similar medicines from Chroma."""
    summary = fetch_drug_summary(medicine_name)
    if not summary or summary == "No data found.":
        print(f"No summary found for {medicine_name}.")
        return []

    return search_similar_medicines(query_text=summary, top_k=top_k)


def test_find_similar() -> None:
    medicine = "Paracetamol"
    matches = find_similar_to_medicine(medicine, top_k=5)
    print(f"\nSimilar medicines to {medicine}:")
    for i, match in enumerate(matches, 1):
        print(f"{i}. {match['name']} (score: {match['score']:.4f})")


def load_sample_medicines() -> None:
    medicines = [
        "Paracetamol", "Ibuprofen", "Amoxicillin", "Aspirin", "Cetirizine",
        "Metformin", "Omeprazole", "Atorvastatin", "Azithromycin", "Loratadine",
        "Doxycycline", "Levothyroxine", "Losartan", "Simvastatin", "Clopidogrel",
        "Pantoprazole", "Hydrochlorothiazide", "Gabapentin", "Fluoxetine", "Ranitidine",
    ]
    for i, med in enumerate(medicines):
        print(f"\nProcessing: {med}")
        summary = fetch_drug_summary(med)
        if summary and summary != "No data found.":
            add_medicine_to_vector_db(f"med{i + 1}", med, summary)
            print(f"Added {med} to vector DB.")
        else:
            print(f"Skipped {med} — no summary found.")
        time.sleep(1)


if __name__ == "__main__":
    load_sample_medicines()
    test_find_similar()
