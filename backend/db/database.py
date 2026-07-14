"""SQLAlchemy engine, session factory, and declarative base.

Database location is controlled by ``DATABASE_URL`` / project-root defaults
in ``backend.core.config``.
"""

from __future__ import annotations

from collections.abc import Generator

from sqlalchemy import create_engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from backend.core.config import get_database_url

DATABASE_URL = get_database_url()

engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)


class Base(DeclarativeBase):
    """Base class for ORM models."""


def get_db() -> Generator[Session, None, None]:
    """Yield a request-scoped SQLAlchemy session and close it afterward."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
