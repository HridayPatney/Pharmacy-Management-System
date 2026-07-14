"""Authentication and admin user-management routes."""

from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session, joinedload

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
    limit: int = Query(50, ge=1, le=200),
    action: str | None = Query(None, description="Exact action filter, e.g. inventory.sell"),
    user_id: int | None = Query(None, description="Filter by acting user id"),
    date_from: datetime | None = Query(None, description="Inclusive lower bound (UTC)"),
    date_to: datetime | None = Query(None, description="Inclusive upper bound (UTC)"),
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(Role.ADMIN)),
):
    """Return filtered audit log entries (admin only)."""
    query = db.query(models.AuditLog).options(joinedload(models.AuditLog.user))
    if action:
        query = query.filter(models.AuditLog.action == action.strip())
    if user_id is not None:
        query = query.filter(models.AuditLog.user_id == user_id)
    if date_from is not None:
        query = query.filter(models.AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.filter(models.AuditLog.created_at <= date_to)

    rows = query.order_by(models.AuditLog.created_at.desc()).limit(limit).all()
    return [
        AuditLogOut(
            id=row.id,
            user_id=row.user_id,
            user_email=row.user.email if row.user else None,
            action=row.action,
            entity_type=row.entity_type,
            entity_id=row.entity_id,
            details=row.details,
            created_at=row.created_at,
        )
        for row in rows
    ]
