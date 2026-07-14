"""Bootstrap first admin and ensure ORM tables exist on startup."""

from __future__ import annotations

import logging

from backend.core.config import get_bootstrap_admin_email, get_bootstrap_admin_password
from backend.core.roles import Role
from backend.core.security import hash_password
from backend.db import models
from backend.db.database import Base, SessionLocal, engine

logger = logging.getLogger(__name__)


def ensure_schema() -> None:
    """Create missing tables (dev-friendly; Alembic can replace this later)."""
    Base.metadata.create_all(bind=engine)


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
