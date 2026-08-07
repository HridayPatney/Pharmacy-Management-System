"""Bootstrap first admin and ensure ORM tables exist on startup."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from backend.core.config import get_bootstrap_admin_email, get_bootstrap_admin_password, get_database_url
from backend.core.roles import Role
from backend.core.security import hash_password
from backend.db import database, models
from backend.db.database import Base

logger = logging.getLogger(__name__)


def _is_postgres() -> bool:
    return get_database_url().startswith("postgresql")


def _add_missing_columns() -> None:
    """Add columns introduced after initial create_all (SQLite-friendly)."""
    eng = database.engine
    insp = inspect(eng)
    if "sales" not in insp.get_table_names():
        return
    existing = {col["name"] for col in insp.get_columns("sales")}
    alters: list[str] = []
    if "status" not in existing:
        alters.append("ALTER TABLE sales ADD COLUMN status VARCHAR(32) DEFAULT 'completed'")
    if "cancelled_at" not in existing:
        alters.append("ALTER TABLE sales ADD COLUMN cancelled_at DATETIME")
    if "cancelled_by_user_id" not in existing:
        alters.append("ALTER TABLE sales ADD COLUMN cancelled_by_user_id INTEGER")
    if "prescription_file_key" not in existing:
        alters.append("ALTER TABLE sales ADD COLUMN prescription_file_key VARCHAR(512)")
    if not alters:
        return
    with eng.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
            logger.info("Applied schema patch: %s", stmt)


def _ensure_pgvector() -> None:
    """Enable pgvector extension, create embedding table, and HNSW index."""
    eng = database.engine
    with eng.begin() as conn:
        conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
    Base.metadata.create_all(bind=eng)
    with eng.begin() as conn:
        conn.execute(
            text(
                """
                CREATE INDEX IF NOT EXISTS medicine_embeddings_hnsw
                ON medicine_embeddings
                USING hnsw (embedding vector_cosine_ops)
                """
            )
        )
    logger.info("pgvector ready (medicine_embeddings + HNSW)")


def ensure_schema() -> None:
    """Create missing tables and patch additive columns (dev-friendly)."""
    eng = database.engine
    if _is_postgres():
        _ensure_pgvector()
    else:
        # Vector(384) is Postgres-only — skip medicine_embeddings on SQLite.
        tables = [
            t for t in Base.metadata.sorted_tables if t.name != "medicine_embeddings"
        ]
        Base.metadata.create_all(bind=eng, tables=tables)
    _add_missing_columns()


def bootstrap_admin_if_needed() -> None:
    """Create the first admin when the users table is empty and bootstrap env is set."""
    email = get_bootstrap_admin_email()
    password = get_bootstrap_admin_password()
    if not email or not password:
        return

    db = database.SessionLocal()
    try:
        if db.query(models.User).count() > 0:
            return
        user = models.User(
            email=email.lower(),
            hashed_password=hash_password(password),
            role=Role.ADMIN.value,
            is_active=True,
        )
        db.add(user)
        db.commit()
        logger.info("Bootstrapped admin user %s", email.lower())
    finally:
        db.close()
