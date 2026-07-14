"""Lightweight API smoke tests that do not require Chroma/torch at import time.

Run from the repository root (venv activated)::

    python scripts/smoke_test.py

Uses FastAPI ``TestClient``. Heavy ML modules are stubbed so this can run with
only the core API packages installed.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Isolate smoke DB before backend.db is imported.
_smoke_db = ROOT / "smoke_test.db"
os.environ["DATABASE_URL"] = f"sqlite:///{_smoke_db.resolve().as_posix()}"

# Stub ML stacks before any backend import that would load them.
for name in (
    "chromadb",
    "chromadb.utils",
    "chromadb.utils.embedding_functions",
    "chromadb.config",
    "sentence_transformers",
    "cv2",
    "google",
    "google.genai",
    "google.genai.types",
):
    sys.modules.setdefault(name, MagicMock())

vector_mod = MagicMock()
vector_mod.add_medicine_to_vector_db = MagicMock()
vector_mod.delete_medicine_from_vector_db = MagicMock()
vector_mod.search_similar_medicines = MagicMock(
    return_value=[{"name": "Aspirin", "score": 0.1}]
)
sys.modules["backend.services.vector_search"] = vector_mod

drug_mod = MagicMock()
drug_mod.fetch_drug_summary = MagicMock(return_value="Pain reliever used for fever.")
sys.modules["backend.services.drug_api"] = drug_mod

ocr_mod = MagicMock()
ocr_mod.extract_json = MagicMock(
    return_value={
        "Patient's Name": "Test",
        "Medicines Prescribed": ["Aspirin"],
        "Doctor's Name": None,
        "Clinic Name": None,
        "Date": None,
    }
)
sys.modules["backend.services.ocr_service"] = ocr_mod


def main() -> int:
    from fastapi.testclient import TestClient

    from backend.core.config import get_chroma_path, get_cors_origins, get_database_url
    from backend.db import models  # noqa: F401
    from backend.db.database import Base, engine
    from backend.main import app

    assert "sqlite" in get_database_url()
    assert get_chroma_path()
    assert get_cors_origins()

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)

    client = TestClient(app)

    root = client.get("/")
    assert root.status_code == 200, root.text
    assert root.json()["message"] == "PharmaAssist API is running."

    empty = client.get("/inventory/all")
    assert empty.status_code == 200
    assert empty.json() == []

    expiry = (date.today() + timedelta(days=365)).isoformat()
    payload = {
        "id": "smoke-1",
        "name": "Aspirin",
        "dosage": "100mg",
        "quantity": 20,
        "price": 5.5,
        "expiry_date": expiry,
    }
    added = client.post("/inventory/add", json=payload)
    assert added.status_code == 200, added.text
    assert added.json()["name"] == "Aspirin"

    listed = client.get("/inventory/all")
    assert len(listed.json()) == 1

    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 2}]},
    )
    assert sold.status_code == 200, sold.text
    invoice = sold.json()["invoice"]
    assert invoice["total"] == 11.0
    assert len(invoice["items"]) == 1
    assert "timestamp" in invoice

    low = client.get("/inventory/low-stock?threshold=25")
    assert low.status_code == 200
    assert len(low.json()) == 1

    bad_sell = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 999}]},
    )
    assert bad_sell.status_code == 400

    deleted = client.delete("/inventory/delete/smoke-1")
    assert deleted.status_code == 200

    Base.metadata.drop_all(bind=engine)
    engine.dispose()
    if _smoke_db.exists():
        try:
            _smoke_db.unlink()
        except OSError:
            pass

    print("smoke_test: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
