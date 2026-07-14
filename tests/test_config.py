"""Unit tests for configuration helpers."""

from __future__ import annotations

import backend.core.config as config


def test_cors_origins_default(monkeypatch):
    monkeypatch.delenv("CORS_ORIGINS", raising=False)
    config.get_cors_origins.cache_clear()
    assert config.get_cors_origins() == ["http://localhost:8501"]


def test_cors_origins_comma_separated(monkeypatch):
    monkeypatch.setenv("CORS_ORIGINS", "http://localhost:8501, http://localhost:5173")
    config.get_cors_origins.cache_clear()
    assert config.get_cors_origins() == [
        "http://localhost:8501",
        "http://localhost:5173",
    ]


def test_gemini_api_key_missing(monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    try:
        config.get_gemini_api_key()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "GEMINI_API_KEY" in str(exc)


def test_database_url_override(monkeypatch):
    monkeypatch.setenv("DATABASE_URL", "sqlite:///C:/tmp/custom.db")
    config.get_database_url.cache_clear()
    assert config.get_database_url() == "sqlite:///C:/tmp/custom.db"


def test_database_url_normalizes_render_postgres(monkeypatch):
    monkeypatch.setenv(
        "DATABASE_URL",
        "postgresql://user:pass@dpg-xxx/pharma",
    )
    config.get_database_url.cache_clear()
    assert config.get_database_url().startswith("postgresql+psycopg://")


def test_jwt_secret_missing(monkeypatch):
    monkeypatch.delenv("JWT_SECRET", raising=False)
    config.get_jwt_secret.cache_clear()
    try:
        config.get_jwt_secret()
        assert False, "expected RuntimeError"
    except RuntimeError as exc:
        assert "JWT_SECRET" in str(exc)
    finally:
        monkeypatch.setenv("JWT_SECRET", "test-jwt-secret-not-for-production")
        config.get_jwt_secret.cache_clear()
