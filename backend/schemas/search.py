"""Vector similarity search request and response schemas."""

from __future__ import annotations

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Body for ``POST /search/similar``."""

    medicine_name: str
    top_k: int = Field(default=5, ge=1, le=50)


class SearchResult(BaseModel):
    """One similar-medicine hit (``score`` is Chroma distance; lower is closer)."""

    name: str
    score: float
    quantity: int | None = Field(
        default=None,
        description="Current on-hand stock when filtered to inventory",
    )


class ReindexResponse(BaseModel):
    """Result of ``POST /search/reindex``."""

    scheduled: int
    message: str = "Embedding rebuild queued for all medicines in inventory."
