"""Auth request and response schemas."""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, EmailStr, Field

from backend.core.roles import Role


class LoginRequest(BaseModel):
    """Body for ``POST /auth/login``."""

    email: EmailStr
    password: str = Field(min_length=1)


class RegisterRequest(BaseModel):
    """Body for ``POST /auth/register`` (admin only)."""

    email: EmailStr
    password: str = Field(min_length=8, max_length=128)
    role: Role = Role.CASHIER


class UserOut(BaseModel):
    """Public user profile."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    email: EmailStr
    role: Role
    is_active: bool
    created_at: datetime


class TokenResponse(BaseModel):
    """JWT login response."""

    access_token: str
    token_type: str = "bearer"
    user: UserOut


class AuditLogOut(BaseModel):
    """One audit row for admin listing."""

    model_config = ConfigDict(from_attributes=True)

    id: int
    user_id: int
    user_email: str | None = None
    action: str
    entity_type: str
    entity_id: str | None
    details: str | None
    created_at: datetime
