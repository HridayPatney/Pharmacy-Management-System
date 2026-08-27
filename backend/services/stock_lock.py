"""Pessimistic row locks for inventory quantity mutations.

Postgres: ``SELECT ... FOR UPDATE`` waits for the row, then
``populate_existing`` refreshes the ORM identity map so stock checks see
the committed quantity — not a stale in-memory copy from an earlier
lookup in the same session.

SQLite ignores ``FOR UPDATE``; the same call path still runs in tests.

Multi-row locks are ordered by primary key to avoid A-then-B vs B-then-A
deadlocks on multi-item carts.
"""

from __future__ import annotations

from sqlalchemy import false
from sqlalchemy.orm import Query, Session

from backend.db import models


def _locked_medicines_query(db: Session, medicine_ids: list[str]) -> Query:
    ids = sorted({mid for mid in medicine_ids if mid})
    query = db.query(models.Medicine)
    if ids:
        query = query.filter(models.Medicine.id.in_(ids))
    else:
        query = query.filter(false())
    return (
        query.order_by(models.Medicine.id)
        .populate_existing()
        .with_for_update()
    )


def lock_medicine_by_id(db: Session, medicine_id: str) -> models.Medicine | None:
    """Lock one medicine row. ``None`` if it does not exist."""
    return (
        db.query(models.Medicine)
        .filter(models.Medicine.id == medicine_id)
        .populate_existing()
        .with_for_update()
        .first()
    )


def lock_medicines_by_ids(
    db: Session, medicine_ids: list[str]
) -> dict[str, models.Medicine]:
    """Lock the given medicines in id order. Missing ids are omitted."""
    ids = sorted({mid for mid in medicine_ids if mid})
    if not ids:
        return {}
    rows = _locked_medicines_query(db, ids).all()
    return {row.id: row for row in rows}


def lock_sale_by_id(db: Session, sale_id: int) -> models.Sale | None:
    """Lock one sale row (no joinedload — FOR UPDATE + outer joins are unsafe)."""
    return (
        db.query(models.Sale)
        .filter(models.Sale.id == sale_id)
        .populate_existing()
        .with_for_update()
        .first()
    )
