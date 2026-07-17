"""Rebuild Chroma embeddings from all medicines in SQL inventory.

Usage (from repo root, venv active)::

    python scripts/reindex_vectors.py

Runs sync inline so the process exits after embeddings finish (or fail).
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Force request-thread sync so the script does not exit while jobs are queued.
os.environ["VECTOR_SYNC_INLINE"] = "1"


def main() -> int:
    from backend.core.bootstrap import ensure_schema
    from backend.db.database import SessionLocal
    from backend.services.vector_sync import reindex_all_medicines, wait_for_pending_vector_jobs

    ensure_schema()
    db = SessionLocal()
    try:
        result = reindex_all_medicines(db)
        wait_for_pending_vector_jobs(timeout=600.0)
        print(f"Reindexed embeddings for {result['scheduled']} medicine(s).")
        return 0
    finally:
        db.close()


if __name__ == "__main__":
    raise SystemExit(main())
