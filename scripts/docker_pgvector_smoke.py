#!/usr/bin/env python3
"""Smoke-test similar-search against local Docker Postgres/pgvector.

  docker compose -f docker-compose.pgvector.yml up -d
  set DATABASE_URL=postgresql+psycopg://pharma:pharma@127.0.0.1:5432/pharma
  python scripts/docker_pgvector_smoke.py
"""

from __future__ import annotations

import os
import sys
from datetime import date, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault(
    "DATABASE_URL", "postgresql+psycopg://pharma:pharma@127.0.0.1:5432/pharma"
)
os.environ.setdefault("JWT_SECRET", "docker-pgvector-smoke-secret")
os.environ["VECTOR_SYNC_INLINE"] = "1"
os.environ.setdefault("STORAGE_BACKEND", "local")
os.environ.setdefault("BOOTSTRAP_ADMIN_EMAIL", "admin@example.com")
os.environ.setdefault("BOOTSTRAP_ADMIN_PASSWORD", "adminpass1")


def main() -> int:
    import backend.core.config as config
    import backend.db.database as database

    config.get_database_url.cache_clear()
    config.get_jwt_secret.cache_clear()
    database.DATABASE_URL = config.get_database_url()
    database.engine = database.create_engine(database.DATABASE_URL)
    database.SessionLocal = database.sessionmaker(
        autocommit=False, autoflush=False, bind=database.engine
    )

    from backend.core.bootstrap import bootstrap_admin_if_needed, ensure_schema
    from backend.services.vector_search import pgvector_status, vectors_enabled

    print("DATABASE_URL:", database.DATABASE_URL.split("@")[-1])
    if not vectors_enabled():
        print("FAIL: vectors_enabled is False")
        return 1

    ensure_schema()
    # Ensure a known admin exists (prior smoke may have seeded a different email).
    from backend.core.roles import Role
    from backend.core.security import hash_password
    from backend.db import models

    db = database.SessionLocal()
    try:
        email = "admin@example.com"
        user = db.query(models.User).filter(models.User.email == email).first()
        if user is None:
            db.add(
                models.User(
                    email=email,
                    hashed_password=hash_password("adminpass1"),
                    role=Role.ADMIN.value,
                    is_active=True,
                )
            )
            db.commit()
            print("created admin", email)
        else:
            user.hashed_password = hash_password("adminpass1")
            user.is_active = True
            db.commit()
            print("reset admin password", email)
    finally:
        db.close()

    status = pgvector_status()
    print("pgvector_status:", status)
    if status.get("status") != "ok":
        print("FAIL: pgvector not ok")
        return 1

    from fastapi.testclient import TestClient

    from backend.main import app

    expiry = (date.today() + timedelta(days=365)).isoformat()
    with TestClient(app) as client:
        login = client.post(
            "/auth/login",
            json={"email": "admin@example.com", "password": "adminpass1"},
        )
        if login.status_code != 200:
            print("FAIL: login", login.status_code, login.text)
            return 1
        headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

        for med in (
            {
                "id": "smoke-asp",
                "name": "Aspirin",
                "dosage": "100mg",
                "quantity": 20,
                "price": 5.0,
                "expiry_date": expiry,
            },
            {
                "id": "smoke-ibu",
                "name": "Ibuprofen",
                "dosage": "200mg",
                "quantity": 15,
                "price": 6.0,
                "expiry_date": expiry,
            },
            {
                "id": "smoke-amox",
                "name": "Amoxicillin",
                "dosage": "500mg",
                "quantity": 10,
                "price": 8.0,
                "expiry_date": expiry,
            },
        ):
            # idempotent: delete if leftover from prior smoke
            client.delete(f"/inventory/delete/{med['id']}", headers=headers)
            res = client.post("/inventory/add", json=med, headers=headers)
            if res.status_code != 200:
                print("FAIL: add", med["name"], res.status_code, res.text)
                return 1
            print("added", med["name"])

        ready = client.get("/health/ready")
        print("GET /health/ready:", ready.status_code, ready.json())
        if ready.json().get("checks", {}).get("pgvector", {}).get("status") != "ok":
            print("FAIL: health pgvector")
            return 1

        reindex = client.post("/search/reindex", headers=headers)
        print("POST /search/reindex:", reindex.status_code, reindex.json())
        if reindex.status_code != 200:
            return 1

        similar = client.post(
            "/search/similar",
            json={"medicine_name": "Aspirin", "top_k": 5},
            headers=headers,
        )
        print("POST /search/similar:", similar.status_code, similar.json())
        if similar.status_code != 200:
            return 1
        names = [r["name"] for r in similar.json()]
        if "Aspirin" in names:
            print("FAIL: self should be excluded", names)
            return 1
        if "Ibuprofen" not in names:
            print("WARN: expected Ibuprofen among alternatives:", names)
            # still OK if Amoxicillin or others returned — prove vectors work
            if not names:
                print("FAIL: empty similar results (no vector hits / fallback)")
                return 1

        print("ALL OK — Docker pgvector similar-search works")
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
