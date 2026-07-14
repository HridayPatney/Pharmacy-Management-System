"""Inspect Chroma contents for the configured vector store.

Loads the ML stack on first use (lazy). Run from the repository root::

    python scripts/view_vector_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.services.vector_search import get_collection


def display_vector_contents() -> None:
    """Print ids, names, and truncated documents from the medicine collection."""
    print("Inspecting ChromaDB vector store...\n")

    try:
        collection = get_collection()
        all_data = collection.get(include=["documents", "metadatas"])
        ids = all_data["ids"]
        docs = all_data["documents"]
        metas = all_data["metadatas"]

        if not ids:
            print("No vectors found in the database.")
            return

        for i in range(len(ids)):
            print(f"ID: {ids[i]}")
            print(f"Name: {metas[i].get('name', 'N/A')}")
            print(f"Description: {docs[i][:120]}...")
            print("-" * 60)

        print(f"Total vectors: {len(ids)}")

    except Exception as e:
        print(f"Error reading from vector DB: {e}")


if __name__ == "__main__":
    display_vector_contents()
