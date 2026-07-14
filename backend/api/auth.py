"""Authentication and admin user-management routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from backend.core.deps import get_current_user, require_roles
from backend.core.roles import Role
from backend.core.security import create_access_token, hash_password, verify_password
from backend.db import models
from backend.db.database import get_db
from backend.schemas.auth import (
    AuditLogOut,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
)

router = APIRouter()


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, db: Session = Depends(get_db)):
    """Exchange email/password for a JWT access token."""
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    token = create_access_token(subject=str(user.id), role=user.role)
    return TokenResponse(access_token=token, user=UserOut.model_validate(user))


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return user


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(Role.ADMIN)),
):
    """Create a staff user (admin only)."""
    email = payload.email.lower()
    if db.query(models.User).filter(models.User.email == email).first():
        raise HTTPException(status_code=400, detail="Email already registered")

    user = models.User(
        email=email,
        hashed_password=hash_password(payload.password),
        role=payload.role.value,
        is_active=True,
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit", response_model=list[AuditLogOut])
def list_audit(
    limit: int = 50,
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(Role.ADMIN)),
):
    """Return recent audit log entries (admin only)."""
    limit = min(max(limit, 1), 200)
    return (
        db.query(models.AuditLog)
        .order_by(models.AuditLog.created_at.desc())
        .limit(limit)
        .all()
    )
