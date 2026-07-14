"""Unified API error envelope: ``{ "error": { "code", "message", "details" } }``."""

from __future__ import annotations

from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _code_for_status(status_code: int) -> str:
    mapping = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        409: "CONFLICT",
        422: "VALIDATION_ERROR",
        429: "RATE_LIMITED",
        503: "SERVICE_UNAVAILABLE",
    }
    return mapping.get(status_code, "HTTP_ERROR")


def error_body(
    *,
    code: str,
    message: str,
    details: Any = None,
) -> dict[str, Any]:
    """Build the standard error JSON payload."""
    body: dict[str, Any] = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


def register_exception_handlers(app: FastAPI) -> None:
    """Attach handlers so all errors share the same response shape."""

    @app.exception_handler(RequestValidationError)
    async def validation_handler(_request: Request, exc: RequestValidationError):
        return JSONResponse(
            status_code=422,
            content=error_body(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details=exc.errors(),
            ),
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException):
        detail = exc.detail
        if isinstance(detail, dict) and "code" in detail and "message" in detail:
            code = str(detail["code"])
            message = str(detail["message"])
            details = detail.get("details")
        else:
            code = _code_for_status(exc.status_code)
            message = detail if isinstance(detail, str) else str(detail)
            details = None
        headers = getattr(exc, "headers", None)
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(code=code, message=message, details=details),
            headers=headers,
        )

    @app.exception_handler(StarletteHTTPException)
    async def starlette_http_handler(_request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=error_body(
                code=_code_for_status(exc.status_code),
                message=str(exc.detail),
            ),
        )

    @app.exception_handler(Exception)
    async def unhandled_handler(_request: Request, exc: Exception):
        return JSONResponse(
            status_code=500,
            content=error_body(
                code="INTERNAL_ERROR",
                message="An unexpected error occurred",
                details={"type": type(exc).__name__},
            ),
        )
