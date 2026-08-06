"""Optional live IT against Docker Postgres/pgvector.

Skipped unless ``RUN_PGVECTOR_IT=1`` and Postgres is reachable
(``docker compose -f docker-compose.pgvector.yml up -d``).
"""

from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

PG_URL = os.getenv(
    "PGVECTOR_IT_DATABASE_URL",
    "postgresql+psycopg://pharma:pharma@127.0.0.1:5432/pharma",
)


def _postgres_reachable() -> bool:
    try:
        from sqlalchemy import create_engine, text

        eng = create_engine(PG_URL, pool_pre_ping=True)
        with eng.connect() as conn:
            conn.execute(text("SELECT 1"))
        eng.dispose()
        return True
    except Exception:
        return False


pytestmark = pytest.mark.skipif(
    os.getenv("RUN_PGVECTOR_IT", "").strip().lower() not in ("1", "true", "yes")
    or not _postgres_reachable(),
    reason="Set RUN_PGVECTOR_IT=1 and start docker-compose.pgvector.yml",
)


@pytest.fixture()
def pg_client(tmp_path, monkeypatch):
    """TestClient bound to Docker Postgres (real pgvector path, stubbed Gemini/OCR)."""
    monkeypatch.setenv("DATABASE_URL", PG_URL)
    monkeypatch.setenv("JWT_SECRET", "pgvector-it-secret")
    monkeypatch.setenv("VECTOR_SYNC_INLINE", "1")
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(tmp_path / "uploads"))
    # Isolate from developer ``.env`` bootstrap (load_dotenv may have filled os.environ).
    monkeypatch.setenv("BOOTSTRAP_ADMIN_EMAIL", "")
    monkeypatch.setenv("BOOTSTRAP_ADMIN_PASSWORD", "")

    # Keep OCR stub from conftest; restore real chromadb EF + vector_search for this IT.
    import sys

    for mod in (
        "chromadb",
        "chromadb.utils",
        "chromadb.utils.embedding_functions",
        "chromadb.config",
        "backend.services.embeddings",
        "backend.services.vector_search",
    ):
        sys.modules.pop(mod, None)

    import backend.core.config as config
    import backend.db.database as database

    config.get_database_url.cache_clear()
    config.get_jwt_secret.cache_clear()
    database.DATABASE_URL = config.get_database_url()
    database.engine = database.create_engine(database.DATABASE_URL)
    database.SessionLocal = database.sessionmaker(
        autocommit=False, autoflush=False, bind=database.engine
    )

    from backend.core.bootstrap import ensure_schema
    from backend.core.roles import Role
    from backend.core.security import hash_password
    from backend.db import models
    from backend.main import app

    ensure_schema()

    # Isolate IT data in a dedicated admin + medicines with smoke-* ids.
    db = database.SessionLocal()
    try:
        email = "pgvector-it@example.com"
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            db.add(
                models.User(
                    email=email,
                    hashed_password=hash_password("pgvector-it-pass"),
                    role=Role.ADMIN.value,
                    is_active=True,
                )
            )
            db.commit()
        else:
            user.hashed_password = hash_password("pgvector-it-pass")
            user.is_active = True
            db.commit()
    finally:
        db.close()

    from fastapi.testclient import TestClient

    with TestClient(app) as client:
        yield client

    database.engine.dispose()


def test_similar_search_returns_neighbors_on_postgres(pg_client):
    login = pg_client.post(
        "/auth/login",
        json={"email": "pgvector-it@example.com", "password": "pgvector-it-pass"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    expiry = (date.today() + timedelta(days=200)).isoformat()
    for med in (
        {
            "id": "it-asp",
            "name": "Aspirin",
            "dosage": "100mg",
            "quantity": 20,
            "price": 5.0,
            "expiry_date": expiry,
        },
        {
            "id": "it-ibu",
            "name": "Ibuprofen",
            "dosage": "200mg",
            "quantity": 15,
            "price": 6.0,
            "expiry_date": expiry,
        },
    ):
        pg_client.delete(f"/inventory/delete/{med['id']}", headers=headers)
        assert pg_client.post("/inventory/add", json=med, headers=headers).status_code == 200

    ready = pg_client.get("/health/ready")
    assert ready.status_code == 200
    assert ready.json()["checks"]["pgvector"]["status"] == "ok"

    similar = pg_client.post(
        "/search/similar",
        json={"medicine_name": "Aspirin", "top_k": 5},
        headers=headers,
    )
    assert similar.status_code == 200
    names = [r["name"] for r in similar.json()]
    assert "Aspirin" not in names
    assert "Ibuprofen" in names
