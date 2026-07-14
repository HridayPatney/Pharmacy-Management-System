"""Helpers for keeping Chroma in sync after SQLite inventory commits.

Policy (documented in ``docs/architecture.md``):

* SQLite is the source of truth for stock and medicine fields.
* Chroma is updated **after** a successful SQLite commit.
* If Chroma fails, inventory stays as committed and the API returns HTTP 503
  so the client can retry (e.g. re-run update) to fix the vector index.
"""

from __future__ import annotations

import logging

from fastapi import HTTPException

from backend.services.vector_search import (
    add_medicine_to_vector_db,
    delete_medicine_from_vector_db,
)

logger = logging.getLogger(__name__)


def sync_medicine_embedding(medicine_id: str, medicine_name: str, summary: str) -> None:
    """Upsert a medicine embedding in Chroma, or raise HTTP 503 on failure."""
    try:
        add_medicine_to_vector_db(medicine_id, medicine_name, summary)
    except Exception as exc:
        logger.exception("Chroma upsert failed for medicine id=%s", medicine_id)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Medicine '{medicine_id}' was saved in inventory, but the vector index "
                f"failed to sync: {exc}. Retry via update to rebuild the embedding."
            ),
        ) from exc


def remove_medicine_embedding(medicine_id: str) -> None:
    """Delete a medicine embedding from Chroma, or raise HTTP 503 on failure."""
    try:
        delete_medicine_from_vector_db(medicine_id)
    except Exception as exc:
        logger.exception("Chroma delete failed for medicine id=%s", medicine_id)
        raise HTTPException(
            status_code=503,
            detail=(
                f"Medicine '{medicine_id}' was removed from inventory, but the vector index "
                f"failed to sync: {exc}. Delete the embedding manually or re-add then delete."
            ),
        ) from exc
