"""Unit tests for pessimistic inventory/sale row locks."""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.dialects import postgresql

from backend.db import models
from backend.services import stock_lock


def test_locked_medicines_query_uses_for_update_and_id_order(client):
    from backend.db import database

    db = database.SessionLocal()
    try:
        query = stock_lock._locked_medicines_query(db, ["med-b", "med-a"])
        assert query._for_update_arg is not None
        sql = str(
            query.statement.compile(
                dialect=postgresql.dialect(),
                compile_kwargs={"literal_binds": True},
            )
        ).lower()
    finally:
        db.close()

    assert "order by" in sql
    assert "medicines.id" in sql.replace('"', "")


def test_postgres_for_update_sql_shape():
    """Document the Postgres lock clause the helpers rely on."""
    stmt = (
        select(models.Medicine)
        .where(models.Medicine.id.in_(["med-b", "med-a"]))
        .order_by(models.Medicine.id)
        .with_for_update()
    )
    sql = str(stmt.compile(dialect=postgresql.dialect())).upper()
    assert "FOR UPDATE" in sql
    assert "ORDER BY" in sql


def test_lock_medicines_by_ids_skips_empty(client):
    from backend.db import database

    db = database.SessionLocal()
    try:
        assert stock_lock.lock_medicines_by_ids(db, []) == {}
        assert stock_lock.lock_medicines_by_ids(db, ["", ""]) == {}
    finally:
        db.close()
