#!/usr/bin/env python3
"""Queue a full pgvector reindex from current SQL inventory.

Requires DATABASE_URL pointing at PostgreSQL with pgvector.

  python scripts/reindex_vectors.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def main() -> int:
    from backend.core.bootstrap import ensure_schema
    from backend.core.config import get_database_url
    from backend.db.database import SessionLocal
    from backend.services.vector_search import vectors_enabled
    from backend.services.vector_sync import reindex_all_medicines, wait_for_pending_vector_jobs

    print("DATABASE_URL dialect:", get_database_url().split("://", 1)[0])
    if not vectors_enabled():
        print("ERROR: set DATABASE_URL to PostgreSQL to reindex embeddings.")
        return 1

    ensure_schema()
    db = SessionLocal()
    try:
        result = reindex_all_medicines(db)
        print(f"Scheduled {result['scheduled']} embedding job(s). Waiting…")
    finally:
        db.close()

    wait_for_pending_vector_jobs(timeout=600.0)
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
