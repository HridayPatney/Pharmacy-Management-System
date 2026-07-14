"""Initialize the SQLite schema for PharmaAssist.

Run from the repository root::

    python scripts/init_db.py
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from backend.db import models  # noqa: F401 — registers Medicine on Base.metadata
from backend.db.database import Base, engine


def init() -> None:
    """Create all tables defined on ``Base`` if they do not already exist."""
    print("Creating tables in the configured database...")
    Base.metadata.create_all(bind=engine)
    print("Database initialized.")


if __name__ == "__main__":
    init()
