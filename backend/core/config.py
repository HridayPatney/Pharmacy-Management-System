"""Application configuration loaded from environment variables.

Secrets must never be hardcoded. Copy `.env.example` to `.env` and set
values locally. See `docs/environment.md` for details.
"""

from __future__ import annotations

import os
from functools import lru_cache

from dotenv import load_dotenv

load_dotenv()


@lru_cache(maxsize=1)
def get_cors_origins() -> list[str]:
    """Return allowed CORS origins from ``CORS_ORIGINS`` (comma-separated).

    Defaults to local Streamlit (``http://localhost:8501``) when unset.
    Use ``*`` only for local experiments; do not deploy with a wildcard.
    """
    raw = os.getenv("CORS_ORIGINS", "http://localhost:8501").strip()
    if raw == "*":
        return ["*"]
    return [origin.strip() for origin in raw.split(",") if origin.strip()]


def get_gemini_api_key() -> str:
    """Return the Gemini API key from ``GEMINI_API_KEY``.

    Raises:
        RuntimeError: If the environment variable is missing or empty.
    """
    key = os.getenv("GEMINI_API_KEY", "").strip()
    if not key:
        raise RuntimeError(
            "GEMINI_API_KEY is not set. Copy .env.example to .env and add your key. "
            "See docs/environment.md."
        )
    return key
