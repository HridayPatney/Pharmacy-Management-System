"""Helpers for keeping Chroma in sync after inventory commits.

Policy (documented in ``docs/architecture.md``):

* SQL inventory is the source of truth for stock and medicine fields.
* Chroma is updated **after** a successful SQL commit.
* Add/update indexing runs in a **background thread** so the HTTP response
  returns as soon as the row is saved (drug summary + embedding can be slow).
* Failures are logged; inventory is never rolled back for vector issues.
"""

from __future__ import annotations

import logging
import os
import threading
from concurrent.futures import Future, ThreadPoolExecutor
from typing import Any

from backend.services.vector_search import (
    add_medicine_to_vector_db,
    delete_medicine_from_vector_db,
)

logger = logging.getLogger(__name__)

_executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="vector-sync")
_lock = threading.Lock()
_pending: set[Future[Any]] = set()


def _inline_sync() -> bool:
    """When true (tests), run jobs on the request thread for deterministic asserts."""
    return os.getenv("VECTOR_SYNC_INLINE", "").strip().lower() in ("1", "true", "yes")


def _track(fut: Future[Any]) -> None:
    with _lock:
        _pending.add(fut)

    def _done(done: Future[Any]) -> None:
        with _lock:
            _pending.discard(done)
        exc = done.exception()
        if exc is not None:
            logger.exception("Background vector job failed: %s", exc)

    fut.add_done_callback(_done)


def wait_for_pending_vector_jobs(timeout: float | None = 10.0) -> None:
    """Block until queued background vector jobs finish (tests / scripts)."""
    with _lock:
        jobs = list(_pending)
    for fut in jobs:
        fut.result(timeout=timeout)


def _upsert_job(medicine_id: str, medicine_name: str, summary: str) -> None:
    try:
        add_medicine_to_vector_db(medicine_id, medicine_name, summary)
    except Exception:
        logger.exception(
            "Chroma upsert failed for medicine id=%s name=%s", medicine_id, medicine_name
        )


def _delete_job(medicine_id: str) -> None:
    try:
        delete_medicine_from_vector_db(medicine_id)
    except Exception:
        logger.exception("Chroma delete failed for medicine id=%s", medicine_id)


def schedule_medicine_embedding(medicine_id: str, medicine_name: str, summary: str) -> None:
    """Queue an embedding upsert (or run inline when ``VECTOR_SYNC_INLINE`` is set)."""
    if _inline_sync():
        _upsert_job(medicine_id, medicine_name, summary)
        return
    fut = _executor.submit(_upsert_job, medicine_id, medicine_name, summary)
    _track(fut)


def schedule_medicine_embedding_fetch(medicine_id: str, medicine_name: str) -> None:
    """Fetch drug summary then upsert embedding — both off the request path."""

    def _job() -> None:
        from backend.services.drug_api import fetch_drug_summary

        try:
            summary = fetch_drug_summary(medicine_name) or ""
        except Exception:
            logger.exception("Drug summary fetch failed for %s", medicine_name)
            summary = ""
        _upsert_job(medicine_id, medicine_name, summary)

    if _inline_sync():
        _job()
        return
    fut = _executor.submit(_job)
    _track(fut)


def schedule_remove_medicine_embedding(medicine_id: str) -> None:
    """Queue embedding delete after inventory delete."""
    if _inline_sync():
        _delete_job(medicine_id)
        return
    fut = _executor.submit(_delete_job, medicine_id)
    _track(fut)


# Back-compat names used by older call sites / docs.
def sync_medicine_embedding(medicine_id: str, medicine_name: str, summary: str) -> None:
    """Schedule upsert; does not raise HTTP errors (inventory already committed)."""
    schedule_medicine_embedding(medicine_id, medicine_name, summary)


def remove_medicine_embedding(medicine_id: str) -> None:
    """Schedule delete; does not raise HTTP errors."""
    schedule_remove_medicine_embedding(medicine_id)
