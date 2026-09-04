"""Authentication and admin user-management routes."""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query, Request, Response, status
from sqlalchemy.orm import Session, joinedload

from backend.core.config import get_cookie_samesite, get_cookie_secure, get_jwt_expire_minutes, get_refresh_expire_days
from backend.core.deps import get_current_user, require_roles
from backend.core.roles import Role
from backend.core.security import (
    REFRESH_COOKIE_NAME,
    REFRESH_COOKIE_PATH,
    create_access_token,
    hash_password,
    verify_password,
)
from backend.db import models
from backend.db.database import get_db
from backend.schemas.auth import (
    AuditLogOut,
    LoginRequest,
    RegisterRequest,
    TokenResponse,
    UserOut,
    UserUpdateRequest,
)
from backend.services.audit import write_audit
from backend.services.refresh_tokens import (
    RefreshError,
    issue_refresh_token,
    revoke_refresh_token,
    rotate_refresh_token,
)

router = APIRouter()


def _cookie_flags() -> tuple[Literal["lax", "strict", "none"], bool]:
    """Flags for the refresh cookie.

    Default is ``SameSite=None; Secure`` so the cookie is sent from a separate
    SPA origin (Vite on another port, or Render static site + API).
    """
    configured = get_cookie_samesite()
    samesite: Literal["lax", "strict", "none"] = (
        configured if configured in ("lax", "strict", "none") else "none"
    )
    if samesite == "none":
        return samesite, True
    secure_override = get_cookie_secure()
    return samesite, bool(secure_override)


def _set_refresh_cookie(response: Response, raw: str) -> None:
    samesite, secure = _cookie_flags()
    response.set_cookie(
        key=REFRESH_COOKIE_NAME,
        value=raw,
        max_age=get_refresh_expire_days() * 86400,
        httponly=True,
        secure=secure,
        samesite=samesite,
        path=REFRESH_COOKIE_PATH,
    )


def _clear_refresh_cookie(response: Response) -> None:
    samesite, secure = _cookie_flags()
    response.delete_cookie(
        key=REFRESH_COOKIE_NAME,
        path=REFRESH_COOKIE_PATH,
        httponly=True,
        secure=secure,
        samesite=samesite,
    )


def _token_response(user: models.User) -> TokenResponse:
    return TokenResponse(
        access_token=create_access_token(subject=str(user.id), role=user.role),
        expires_in=get_jwt_expire_minutes() * 60,
        user=UserOut.model_validate(user),
    )


def _active_admin_count(db: Session) -> int:
    return (
        db.query(models.User)
        .filter(models.User.role == Role.ADMIN.value, models.User.is_active.is_(True))
        .count()
    )


def _ensure_not_last_active_admin(db: Session, target: models.User, *, new_role: str, new_active: bool) -> None:
    """Block changes that would leave the system with zero active admins."""
    was_active_admin = target.role == Role.ADMIN.value and target.is_active
    stays_active_admin = new_role == Role.ADMIN.value and new_active
    if was_active_admin and not stays_active_admin and _active_admin_count(db) <= 1:
        raise HTTPException(
            status_code=400,
            detail="Cannot remove or deactivate the last active admin",
        )


@router.post("/login", response_model=TokenResponse)
def login(
    payload: LoginRequest,
    response: Response,
    db: Session = Depends(get_db),
):
    """Exchange email/password for a short-lived JWT and an httpOnly refresh cookie."""
    user = db.query(models.User).filter(models.User.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect email or password",
        )
    raw_refresh, _ = issue_refresh_token(db, user)
    db.commit()
    _set_refresh_cookie(response, raw_refresh)
    return _token_response(user)


@router.post("/refresh", response_model=TokenResponse)
def refresh(request: Request, response: Response, db: Session = Depends(get_db)):
    """Rotate the refresh cookie and return a new access JWT."""
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if not raw:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
        )
    try:
        user, new_raw = rotate_refresh_token(db, raw)
        db.commit()
    except RefreshError:
        db.commit()
        _clear_refresh_cookie(response)
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token",
        ) from None
    _set_refresh_cookie(response, new_raw)
    return _token_response(user)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, db: Session = Depends(get_db)):
    """Revoke the current refresh token and clear the cookie."""
    raw = request.cookies.get(REFRESH_COOKIE_NAME)
    if raw:
        revoke_refresh_token(db, raw)
        db.commit()
    _clear_refresh_cookie(response)


@router.get("/me", response_model=UserOut)
def me(user: models.User = Depends(get_current_user)):
    """Return the authenticated user's profile."""
    return user


@router.get("/users", response_model=list[UserOut])
def list_users(
    db: Session = Depends(get_db),
    _: models.User = Depends(require_roles(Role.ADMIN)),
):
    """List all staff accounts (admin only)."""
    return db.query(models.User).order_by(models.User.id.asc()).all()


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    payload: RegisterRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles(Role.ADMIN)),
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
    db.flush()
    write_audit(
        db,
        user=admin,
        action="auth.user.register",
        entity_type="user",
        entity_id=str(user.id),
        details={"email": user.email, "role": user.role},
    )
    db.commit()
    db.refresh(user)
    return user


@router.patch("/users/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    payload: UserUpdateRequest,
    db: Session = Depends(get_db),
    admin: models.User = Depends(require_roles(Role.ADMIN)),
):
    """Update a staff member's role or active status (admin only)."""
    if payload.role is None and payload.is_active is None:
        raise HTTPException(status_code=400, detail="No fields to update")

    target = db.query(models.User).filter(models.User.id == user_id).first()
    if not target:
        raise HTTPException(status_code=404, detail="User not found")

    if target.id == admin.id and payload.is_active is False:
        raise HTTPException(status_code=400, detail="Cannot deactivate your own account")

    new_role = payload.role.value if payload.role is not None else target.role
    new_active = payload.is_active if payload.is_active is not None else target.is_active
    _ensure_not_last_active_admin(db, target, new_role=new_role, new_active=new_active)

    before = {"role": target.role, "is_active": target.is_active}
    if payload.role is not None:
        target.role = payload.role.value
    if payload.is_active is not None:
        target.is_active = payload.is_active

    write_audit(
        db,
        user=admin,
        action="auth.user.update",
        entity_type="user",
        entity_id=str(target.id),
        details={"before": before, "after": {"role": target.role, "is_active": target.is_active}},
    )
    db.commit()
    db.refresh(target)
    return target


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
