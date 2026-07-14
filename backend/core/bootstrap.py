"""Bootstrap first admin and ensure ORM tables exist on startup."""

from __future__ import annotations

import logging

from sqlalchemy import inspect, text

from backend.core.config import get_bootstrap_admin_email, get_bootstrap_admin_password
from backend.core.roles import Role
from backend.core.security import hash_password
from backend.db import models
from backend.db.database import Base, SessionLocal, engine

logger = logging.getLogger(__name__)


def _add_missing_columns() -> None:
    """Add columns introduced after initial create_all (SQLite-friendly)."""
    insp = inspect(engine)
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
    if not alters:
        return
    with engine.begin() as conn:
        for stmt in alters:
            conn.execute(text(stmt))
            logger.info("Applied schema patch: %s", stmt)


def ensure_schema() -> None:
    """Create missing tables and patch additive columns (dev-friendly)."""
    Base.metadata.create_all(bind=engine)
    _add_missing_columns()


def bootstrap_admin_if_needed() -> None:
    """Create the first admin when the users table is empty and bootstrap env is set."""
    email = get_bootstrap_admin_email()
    password = get_bootstrap_admin_password()
    if not email or not password:
        return

    db = SessionLocal()
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
