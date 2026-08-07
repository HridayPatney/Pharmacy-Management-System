"""Postgres/pgvector embeddings for medicine similarity search.

Vectors are stored in ``medicine_embeddings`` (same DB as inventory). On SQLite
(local default), vector ops are no-ops / empty results — use Postgres to exercise
similar-search (Docker ``pgvector/pgvector`` or Render).
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any

from sqlalchemy import select, text

from backend.core.config import get_database_url

logger = logging.getLogger(__name__)


def vectors_enabled() -> bool:
    """True when ``DATABASE_URL`` is PostgreSQL (pgvector path)."""
    return get_database_url().startswith("postgresql")


def reset_collection_for_tests() -> None:
    """Compat shim for older tests; clears embedding cache."""
    from backend.services.embeddings import reset_embedding_fn_for_tests

    reset_embedding_fn_for_tests()


def get_collection() -> Any:
    """Deprecated Chroma hook — prefer ``vectors_enabled`` / health pgvector check."""
    raise RuntimeError(
        "Chroma PersistentClient was removed; similar-search uses Postgres pgvector. "
        "Set DATABASE_URL to PostgreSQL and call /search/reindex."
    )


def add_medicine_to_vector_db(medicine_id, medicine_name, description) -> None:
    """Upsert a medicine embedding in Postgres. No-op on SQLite."""
    if not vectors_enabled():
        logger.debug("Skipping vector upsert on non-Postgres DB for id=%s", medicine_id)
        return

    from backend.db.database import SessionLocal
    from backend.db.models import MedicineEmbedding
    from backend.services.embeddings import embed_text

    vector = embed_text(description or "")
    db = SessionLocal()
    try:
        row = db.get(MedicineEmbedding, medicine_id)
        if row is None:
            row = MedicineEmbedding(
                medicine_id=medicine_id,
                name=medicine_name,
                summary=description or "",
                embedding=vector,
                updated_at=datetime.utcnow(),
            )
            db.add(row)
        else:
            row.name = medicine_name
            row.summary = description or ""
            row.embedding = vector
            row.updated_at = datetime.utcnow()
        db.commit()
    finally:
        db.close()


def delete_medicine_from_vector_db(medicine_id) -> None:
    """Delete a medicine embedding. No-op on SQLite; missing rows ignored."""
    if not vectors_enabled():
        logger.debug("Skipping vector delete on non-Postgres DB for id=%s", medicine_id)
        return

    from backend.db.database import SessionLocal
    from backend.db.models import MedicineEmbedding

    db = SessionLocal()
    try:
        row = db.get(MedicineEmbedding, medicine_id)
        if row is not None:
            db.delete(row)
            db.commit()
    finally:
        db.close()


def search_similar_medicines(query_text, top_k=5) -> list[dict[str, Any]]:
    """Return up to ``top_k`` similar in-stock medicines for ``query_text``.

    Each result is ``{"name": str, "score": float}`` where ``score`` is cosine
    distance (lower is closer). Empty list on SQLite or when no embeddings exist.
    """
    if not vectors_enabled():
        return []

    from backend.db.database import SessionLocal
    from backend.db.models import Medicine, MedicineEmbedding
    from backend.services.embeddings import embed_text

    if not (query_text or "").strip():
        return []

    query_vec = embed_text(query_text)
    distance = MedicineEmbedding.embedding.cosine_distance(query_vec)

    db = SessionLocal()
    try:
        stmt = (
            select(Medicine.name, distance.label("score"))
            .join(Medicine, Medicine.id == MedicineEmbedding.medicine_id)
            .where(Medicine.quantity > 0)
            .order_by(distance)
            .limit(top_k)
        )
        rows = db.execute(stmt).all()
        return [{"name": name, "score": float(score)} for name, score in rows]
    finally:
        db.close()


def pgvector_status() -> dict[str, Any]:
    """Health helper: extension + table reachability on Postgres."""
    if not vectors_enabled():
        return {
            "status": "skipped",
            "detail": "Vector search requires PostgreSQL (SQLite stubs vectors)",
        }
    from backend.db.database import SessionLocal

    db = SessionLocal()
    try:
        ext = db.execute(
            text("SELECT 1 FROM pg_extension WHERE extname = 'vector'")
        ).scalar()
        if not ext:
            return {"status": "fail", "detail": "pgvector extension not installed"}
        count = db.execute(text("SELECT COUNT(*) FROM medicine_embeddings")).scalar()
        return {"status": "ok", "detail": f"embeddings={count}"}
    except Exception as exc:
        return {"status": "fail", "detail": str(exc)}
    finally:
        db.close()
