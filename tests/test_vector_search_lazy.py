"""Tests that vector search skips work on SQLite and does not load embedders at import."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock


def test_sqlite_vector_ops_are_noop_without_embedder(monkeypatch):
    """On SQLite, add/search must not call the embedding function."""
    sys.modules.pop("backend.services.vector_search", None)
    sys.modules.pop("backend.services.embeddings", None)

    monkeypatch.setenv("DATABASE_URL", "sqlite:///tmp-test-vectors.db")

    import backend.core.config as config

    config.get_database_url.cache_clear()

    fake_ef_mod = MagicMock()
    monkeypatch.setitem(sys.modules, "chromadb", MagicMock())
    monkeypatch.setitem(sys.modules, "chromadb.utils", MagicMock())
    monkeypatch.setitem(
        sys.modules, "chromadb.utils.embedding_functions", fake_ef_mod
    )

    vs = importlib.import_module("backend.services.vector_search")
    importlib.reload(vs)

    assert vs.vectors_enabled() is False
    vs.add_medicine_to_vector_db("id-1", "Aspirin", "pain reliever")
    assert vs.search_similar_medicines("aspirin", top_k=5) == []
    fake_ef_mod.DefaultEmbeddingFunction.assert_not_called()

    # Restore stub used by other API tests.
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
        return_value={"status": "skipped", "detail": "sqlite"}
    )
    sys.modules["backend.services.vector_search"] = stub
