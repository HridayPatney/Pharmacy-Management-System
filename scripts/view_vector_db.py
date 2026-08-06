"""Inspect pgvector medicine embeddings.

Requires DATABASE_URL → PostgreSQL. Run from the repository root::

    python scripts/view_vector_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def display_vector_contents() -> None:
    """Print medicine_id, name, and truncated summary from medicine_embeddings."""
    from sqlalchemy import text

    from backend.db.database import SessionLocal
    from backend.services.vector_search import vectors_enabled

    print("Inspecting pgvector medicine_embeddings...\n")
    if not vectors_enabled():
        print("Vector store requires PostgreSQL. Set DATABASE_URL and retry.")
        return

    db = SessionLocal()
    try:
        rows = db.execute(
            text(
                "SELECT medicine_id, name, LEFT(COALESCE(summary, ''), 120) AS snippet "
                "FROM medicine_embeddings ORDER BY name"
            )
        ).all()
        if not rows:
            print("No vectors found. Add medicines or POST /search/reindex.")
            return
        for medicine_id, name, snippet in rows:
            print(f"ID: {medicine_id}")
            print(f"Name: {name}")
            print(f"Description: {snippet}...")
            print("-" * 60)
        print(f"Total vectors: {len(rows)}")
    except Exception as e:
        print(f"Error reading from vector DB: {e}")
    finally:
        db.close()


if __name__ == "__main__":
    display_vector_contents()
