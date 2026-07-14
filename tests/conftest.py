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

# Auth config required before app import; safe default for the test suite.
os.environ.setdefault("JWT_SECRET", "test-jwt-secret-not-for-production")


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
    fake_collection = MagicMock()
    fake_collection.count.return_value = 0
    vector_mod.get_collection = MagicMock(return_value=fake_collection)
    vector_mod.reset_collection_for_tests = MagicMock()
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
    upload_dir = tmp_path / "uploads"
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{db_path.as_posix()}")
    monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-not-for-production")
    # Never inherit production S3 settings from a developer ``.env``.
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_dir))
    monkeypatch.delenv("S3_BUCKET", raising=False)
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    monkeypatch.delenv("AWS_SECRET_ACCESS_KEY", raising=False)

    import backend.core.config as config
    import backend.db.database as database

    config.get_database_url.cache_clear()
    config.get_jwt_secret.cache_clear()
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


def _create_user(db, *, email: str, password: str, role: str):
    from backend.core.security import hash_password
    from backend.db import models

    user = models.User(
        email=email.lower(),
        hashed_password=hash_password(password),
        role=role,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@pytest.fixture
def admin_headers(client):
    """Bearer headers for an admin user."""
    from backend.db.database import SessionLocal

    db = SessionLocal()
    try:
        _create_user(db, email="admin@test.com", password="adminpass1", role="admin")
    finally:
        db.close()

    token = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "adminpass1"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def pharmacist_headers(client):
    """Bearer headers for a pharmacist user."""
    from backend.db.database import SessionLocal

    db = SessionLocal()
    try:
        _create_user(db, email="pharm@test.com", password="pharmpass1", role="pharmacist")
    finally:
        db.close()

    token = client.post(
        "/auth/login",
        json={"email": "pharm@test.com", "password": "pharmpass1"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def cashier_headers(client):
    """Bearer headers for a cashier user."""
    from backend.db.database import SessionLocal

    db = SessionLocal()
    try:
        _create_user(db, email="cash@test.com", password="cashpass1", role="cashier")
    finally:
        db.close()

    token = client.post(
        "/auth/login",
        json={"email": "cash@test.com", "password": "cashpass1"},
    ).json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


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
