"""Issue, rotate, and revoke hashed refresh tokens."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from backend.core.config import get_refresh_expire_days
from backend.core.security import hash_refresh_token, new_refresh_token
from backend.db import models


class RefreshError(Exception):
    """Refresh token is missing, expired, revoked, or reused."""


def _utcnow() -> datetime:
    return datetime.utcnow()


def issue_refresh_token(db: Session, user: models.User) -> tuple[str, models.RefreshToken]:
    """Persist a hashed refresh token and return ``(raw cookie value, row)``."""
    raw = new_refresh_token()
    row = models.RefreshToken(
        user_id=user.id,
        token_hash=hash_refresh_token(raw),
        expires_at=_utcnow() + timedelta(days=get_refresh_expire_days()),
    )
    db.add(row)
    db.flush()
    return raw, row


def revoke_all_for_user(db: Session, user_id: int) -> None:
    """Revoke every refresh token for ``user_id`` (stolen-token reuse)."""
    now = _utcnow()
    (
        db.query(models.RefreshToken)
        .filter(
            models.RefreshToken.user_id == user_id,
            models.RefreshToken.revoked_at.is_(None),
        )
        .update({"revoked_at": now}, synchronize_session=False)
    )


def _lookup(db: Session, raw: str) -> models.RefreshToken | None:
    return (
        db.query(models.RefreshToken)
        .filter(models.RefreshToken.token_hash == hash_refresh_token(raw))
        .first()
    )


def rotate_refresh_token(db: Session, raw: str) -> tuple[models.User, str]:
    """Validate ``raw``, revoke it, and issue a replacement.

    Reuse of an already-rotated token revokes the user's whole family.
    """
    row = _lookup(db, raw)
    if row is None:
        raise RefreshError("invalid")

    now = _utcnow()
    if row.revoked_at is not None:
        revoke_all_for_user(db, row.user_id)
        raise RefreshError("reused")
    if row.expires_at <= now:
        row.revoked_at = now
        raise RefreshError("expired")

    user = db.query(models.User).filter(models.User.id == row.user_id).first()
    if user is None or not user.is_active:
        row.revoked_at = now
        raise RefreshError("inactive")

    replacement, new_row = issue_refresh_token(db, user)
    row.revoked_at = now
    row.replaced_by_id = new_row.id
    return user, replacement


def revoke_refresh_token(db: Session, raw: str) -> None:
    """Revoke a single refresh token if it exists (logout)."""
    row = _lookup(db, raw)
    if row is not None and row.revoked_at is None:
        row.revoked_at = _utcnow()
