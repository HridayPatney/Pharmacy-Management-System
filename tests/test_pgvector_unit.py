"""Unit tests for Postgres/pgvector vector search (mocked DB + embeddings)."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture()
def fresh_vector_search(monkeypatch):
    """Load real vector_search with a clean module cache (no conftest stub)."""
    sys.modules.pop("backend.services.vector_search", None)
    monkeypatch.setenv(
        "DATABASE_URL", "postgresql+psycopg://pharma:pharma@127.0.0.1:5432/pharma"
    )
    import backend.core.config as config

    config.get_database_url.cache_clear()
    vs = importlib.import_module("backend.services.vector_search")
    importlib.reload(vs)
    yield vs
    # Restore API-test stub
    stub = MagicMock()
    stub.add_medicine_to_vector_db = MagicMock()
    stub.delete_medicine_from_vector_db = MagicMock()
    stub.search_similar_medicines = MagicMock(
        return_value=[{"name": "Aspirin", "score": 0.1}]
    )
    stub.get_collection = MagicMock(side_effect=RuntimeError("removed"))
    stub.reset_collection_for_tests = MagicMock()
    stub.vectors_enabled = MagicMock(return_value=False)
    stub.pgvector_status = MagicMock(
        return_value={"status": "skipped", "detail": "sqlite test stub"}
    )
    sys.modules["backend.services.vector_search"] = stub


def test_vectors_enabled_true_for_postgres(fresh_vector_search):
    assert fresh_vector_search.vectors_enabled() is True


def test_add_medicine_upserts_embedding_row(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    fake_db = MagicMock()
    fake_db.get.return_value = None
    session_factory = MagicMock(return_value=fake_db)

    monkeypatch.setattr("backend.db.database.SessionLocal", session_factory)
    monkeypatch.setattr(
        "backend.services.embeddings.embed_text",
        lambda _t: [0.1] * 384,
    )

    vs.add_medicine_to_vector_db("m1", "Aspirin", "pain reliever")

    fake_db.add.assert_called_once()
    added = fake_db.add.call_args[0][0]
    assert added.medicine_id == "m1"
    assert added.name == "Aspirin"
    assert len(added.embedding) == 384
    fake_db.commit.assert_called_once()
    fake_db.close.assert_called_once()


def test_add_medicine_updates_existing_row(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    existing = MagicMock()
    existing.medicine_id = "m1"
    fake_db = MagicMock()
    fake_db.get.return_value = existing
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))
    monkeypatch.setattr(
        "backend.services.embeddings.embed_text",
        lambda _t: [0.2] * 384,
    )

    vs.add_medicine_to_vector_db("m1", "Aspirin Forte", "updated summary")

    fake_db.add.assert_not_called()
    assert existing.name == "Aspirin Forte"
    assert existing.summary == "updated summary"
    assert existing.embedding == [0.2] * 384
    fake_db.commit.assert_called_once()


def test_delete_medicine_removes_row(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    existing = MagicMock()
    fake_db = MagicMock()
    fake_db.get.return_value = existing
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))

    vs.delete_medicine_from_vector_db("m1")

    fake_db.delete.assert_called_once_with(existing)
    fake_db.commit.assert_called_once()


def test_search_similar_maps_rows(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    fake_db = MagicMock()
    fake_db.execute.return_value.all.return_value = [
        ("Ibuprofen", 0.25),
        ("Amoxicillin", 0.4),
    ]
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))
    monkeypatch.setattr(
        "backend.services.embeddings.embed_text",
        lambda _t: [0.0] * 384,
    )

    with patch.object(vs, "vectors_enabled", return_value=True):
        hits = vs.search_similar_medicines("Aspirin", top_k=5)

    assert hits == [
        {"name": "Ibuprofen", "score": 0.25},
        {"name": "Amoxicillin", "score": 0.4},
    ]
    fake_db.close.assert_called_once()


def test_search_similar_reuses_stored_embedding(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    stored = MagicMock()
    stored.embedding = [0.1] * 384
    fake_db = MagicMock()
    fake_db.get.return_value = stored
    fake_db.execute.return_value.all.return_value = [("Ibuprofen", 0.12)]
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))
    embed = MagicMock(side_effect=AssertionError("should not re-embed"))
    monkeypatch.setattr("backend.services.embeddings.embed_text", embed)

    with patch.object(vs, "vectors_enabled", return_value=True):
        hits = vs.search_similar_medicines(
            query_medicine_id="asp-1",
            top_k=5,
            exclude_medicine_id="asp-1",
        )

    assert hits == [{"name": "Ibuprofen", "score": 0.12}]
    assert fake_db.get.call_count == 1
    assert fake_db.get.call_args.args[1] == "asp-1"
    embed.assert_not_called()
    fake_db.close.assert_called_once()


def test_search_similar_falls_back_to_text_when_no_stored_row(
    fresh_vector_search, monkeypatch
):
    vs = fresh_vector_search
    fake_db = MagicMock()
    fake_db.get.return_value = None
    fake_db.execute.return_value.all.return_value = [("Ibuprofen", 0.3)]
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))
    embed = MagicMock(return_value=[0.0] * 384)
    monkeypatch.setattr("backend.services.embeddings.embed_text", embed)

    with patch.object(vs, "vectors_enabled", return_value=True):
        hits = vs.search_similar_medicines(
            "Aspirin summary",
            top_k=3,
            query_medicine_id="missing-emb",
        )

    assert hits == [{"name": "Ibuprofen", "score": 0.3}]
    embed.assert_called_once_with("Aspirin summary")


def test_pgvector_status_ok(fresh_vector_search, monkeypatch):
    vs = fresh_vector_search
    fake_db = MagicMock()
    fake_db.execute.side_effect = [
        MagicMock(scalar=MagicMock(return_value=1)),  # extension present
        MagicMock(scalar=MagicMock(return_value=3)),  # count
    ]
    monkeypatch.setattr("backend.db.database.SessionLocal", MagicMock(return_value=fake_db))

    status = vs.pgvector_status()
    assert status["status"] == "ok"
    assert "embeddings=3" in status["detail"]
