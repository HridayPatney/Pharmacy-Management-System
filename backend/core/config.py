"""Application configuration loaded from environment variables.

Secrets must never be hardcoded. Copy ``.env.example`` to ``.env`` and set
values locally. See ``docs/environment.md`` for details.
"""

from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from dotenv import load_dotenv

# Repo root: Pharmacy-Management-System/
PROJECT_ROOT = Path(__file__).resolve().parents[2]

load_dotenv(PROJECT_ROOT / ".env")


def _env(name: str, default: str | None = None) -> str | None:
    value = os.getenv(name)
    if value is None or not str(value).strip():
        return default
    return str(value).strip()


@lru_cache(maxsize=1)
def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from ``CORS_ORIGINS`` (comma-separated).

    Defaults to local Streamlit (``http://localhost:8501``) when unset.
    Use ``*`` only for local experiments; do not deploy with a wildcard.
    """
    raw = _env("CORS_ORIGINS", "http://localhost:8501") or "http://localhost:8501"
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_gemini_api_key() -> str:
    """Return the Gemini API key from ``GEMINI_API_KEY``.

    Raises:
        RuntimeError: If the environment variable is missing or empty.
    """
    key = _env("GEMINI_API_KEY")
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key. "
            "See docs/environment.md."
        )
    return key


@lru_cache(maxsize=1)
def get_database_url() -> str:
    """Return the SQLAlchemy database URL.

    Default: SQLite file ``pharma.db`` under the project root (CWD-independent).
    Override with ``DATABASE_URL``.
    """
    override = _env("DATABASE_URL")
    if override:
        return override
    db_path = (PROJECT_ROOT / "pharma.db").resolve()
    # SQLite URLs need forward slashes on Windows.
    return f"sqlite:///{db_path.as_posix()}"


@lru_cache(maxsize=1)
def get_chroma_path() -> str:
    """Return the persistent Chroma directory path.

    Default: ``chroma_store/`` under the project root. Override with ``CHROMA_PATH``.
    """
    override = _env("CHROMA_PATH")
    if override:
        return str(Path(override).expanduser().resolve())
    return str((PROJECT_ROOT / "chroma_store").resolve())


@lru_cache(maxsize=1)
def get_chroma_collection_name() -> str:
    """Return the Chroma collection name (default ``medicine_embeddings``)."""
    return _env("CHROMA_COLLECTION", "medicine_embeddings") or "medicine_embeddings"


@lru_cache(maxsize=1)
def get_embedding_model_name() -> str:
    """Return the sentence-transformers model name used for embeddings."""
    return _env("EMBEDDING_MODEL", "all-MiniLM-L6-v2") or "all-MiniLM-L6-v2"
