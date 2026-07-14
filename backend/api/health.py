"""Liveness and readiness health checks."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter
from fastapi.responses import JSONResponse
from sqlalchemy import text

from backend.core.config import get_gemini_api_key
import os
from backend.db.database import SessionLocal

router = APIRouter()


def _check_db() -> dict[str, Any]:
    try:
        db = SessionLocal()
        try:
            db.execute(text("SELECT 1"))
        finally:
            db.close()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "fail", "detail": str(exc)}


def _check_chroma() -> dict[str, Any]:
    try:
        from backend.services.vector_search import get_collection

        collection = get_collection()
        collection.count()
        return {"status": "ok"}
    except Exception as exc:
        return {"status": "fail", "detail": str(exc)}


def _check_gemini() -> dict[str, Any]:
    """Optional: only reports configured vs missing (no network call by default)."""
    try:
        get_gemini_api_key()
        return {"status": "ok", "detail": "GEMINI_API_KEY configured"}
    except RuntimeError as exc:
        return {"status": "fail", "detail": str(exc)}


@router.get("/live")
def live():
    """Liveness: process is up (no dependency checks)."""
    return {"status": "ok"}


@router.get("/ready")
def ready():
    """Readiness: database required; Chroma/Gemini degrade rather than always fail.

    Returns HTTP 200 when overall status is ``ok`` or ``degraded``, 503 when ``fail``.
    """
    checks: dict[str, Any] = {
        "db": _check_db(),
        "chroma": _check_chroma(),
    }
    if os.getenv("HEALTH_CHECK_GEMINI", "false").strip().lower() in ("1", "true", "yes"):
        checks["gemini"] = _check_gemini()

    db_ok = checks["db"]["status"] == "ok"
    chroma_ok = checks["chroma"]["status"] == "ok"
    gemini = checks.get("gemini")
    gemini_fail = gemini is not None and gemini["status"] != "ok"

    if not db_ok:
        overall = "fail"
    elif not chroma_ok or gemini_fail:
        overall = "degraded"
    else:
        overall = "ok"

    body = {"status": overall, "checks": checks}
    status_code = 503 if overall == "fail" else 200
    return JSONResponse(status_code=status_code, content=body)
