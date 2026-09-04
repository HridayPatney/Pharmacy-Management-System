"""JWT, refresh-token, and password helpers for PharmaAssist auth."""

from __future__ import annotations

import hashlib
import secrets
from datetime import UTC, datetime, timedelta
from typing import Any

import bcrypt
import jwt

from backend.core.config import get_jwt_expire_minutes, get_jwt_secret

REFRESH_COOKIE_NAME = "pharmaassist_refresh"
REFRESH_COOKIE_PATH = "/auth"


def hash_password(password: str) -> str:
    """Hash a plain-text password with bcrypt."""
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    """Return True if ``password`` matches ``password_hash``."""
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except ValueError:
        return False


def create_access_token(*, subject: str, role: str, extra: dict[str, Any] | None = None) -> str:
    """Create a short-lived signed JWT access token for ``subject`` (user id as string)."""
    now = datetime.now(UTC)
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "typ": "access",
        "jti": secrets.token_urlsafe(8),
        "iat": now,
        "exp": now + timedelta(minutes=get_jwt_expire_minutes()),
    }
    if extra:
        payload.update(extra)
    return jwt.encode(payload, get_jwt_secret(), algorithm="HS256")


def decode_access_token(token: str) -> dict[str, Any]:
    """Decode and validate an access JWT; raises ``jwt.PyJWTError`` on failure."""
    payload = jwt.decode(token, get_jwt_secret(), algorithms=["HS256"])
    if payload.get("typ", "access") != "access":
        raise jwt.InvalidTokenError("Not an access token")
    return payload


def new_refresh_token() -> str:
    """Return a high-entropy opaque refresh token (not a JWT)."""
    return secrets.token_urlsafe(32)


def hash_refresh_token(raw: str) -> str:
    """SHA-256 hex digest of a refresh token (fast; tokens are already random)."""
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()
