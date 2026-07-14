"""Shared pytest fixtures for PharmaAssist backend tests.

Heavy ML modules (Chroma, torch, Gemini, OpenCV) are stubbed so tests run with
core API packages only. Each test gets an isolated temporary SQLite database.
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


def _stub_ml_modules() -> MagicMock:
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
    return vector_mod


_VECTOR_MOD = _stub_ml_modules()


@pytest.fixture
def vector_mocks() -> MagicMock:
    """Return the stubbed ``vector_search`` module and reset call history."""
    _VECTOR_MOD.add_medicine_to_vector_db.reset_mock()
    _VECTOR_MOD.delete_medicine_from_vector_db.reset_mock()
    _VECTOR_MOD.add_medicine_to_vector_db.side_effect = None
    _VECTOR_MOD.delete_medicine_from_vector_db.side_effect = None
    return _VECTOR_MOD


@pytest.fixture()
def client(tmp_path, monkeypatch, vector_mocks):
    """FastAPI ``TestClient`` bound to an isolated temp SQLite database."""
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")

    # Config and engine are cached / module-level; rebuild for this DATABASE_URL.
    import backend.core.config as config
    import backend.db.database as database

    config.get_database_url.cache_clear()
    database.DATABASE_URL = config.get_database_url()
    database.engine = database.create_engine(
        database.DATABASE_URL,
        connect_args={"check_same_thread": False},
    )
    database.SessionLocal = database.sessionmaker(
        autocommit=False, autoflush=False, bind=database.engine
    )

    from backend.db import models  # noqa: F401
    from backend.main import app

    database.Base.metadata.drop_all(bind=database.engine)
    database.Base.metadata.create_all(bind=database.engine)

    from fastapi.testclient import TestClient

    with TestClient(app) as test_client:
        yield test_client

    database.Base.metadata.drop_all(bind=database.engine)
    database.engine.dispose()


@pytest.fixture
def sample_medicine_payload() -> dict:
    """Valid body for ``POST /inventory/add``."""
    return {
        "id": "med-1",
        "name": "Aspirin",
        "dosage": "100mg",
        "quantity": 20,
        "price": 5.5,
        "expiry_date": (date.today() + timedelta(days=365)).isoformat(),
    }
