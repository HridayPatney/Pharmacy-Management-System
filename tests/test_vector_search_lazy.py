"""Tests that Chroma initializes lazily (not at import time)."""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock


def test_get_collection_not_called_until_needed(monkeypatch):
    """Reloading vector_search must not construct PersistentClient until get_collection()."""
    # Drop the conftest stub so we exercise the real module with mocked chromadb.
    sys.modules.pop("backend.services.vector_search", None)

    fake_chromadb = MagicMock()
    fake_client = MagicMock()
    fake_collection = MagicMock()
    fake_client.get_or_create_collection.return_value = fake_collection
    fake_chromadb.PersistentClient.return_value = fake_client

    fake_ef = MagicMock()
    fake_utils = MagicMock()
    fake_utils.embedding_functions = fake_ef

    monkeypatch.setitem(sys.modules, "chromadb", fake_chromadb)
    monkeypatch.setitem(sys.modules, "chromadb.utils", fake_utils)
    monkeypatch.setitem(sys.modules, "chromadb.utils.embedding_functions", fake_ef)

    vs = importlib.import_module("backend.services.vector_search")
    importlib.reload(vs)

    fake_chromadb.PersistentClient.assert_not_called()

    collection = vs.get_collection()
    assert collection is fake_collection
    fake_chromadb.PersistentClient.assert_called_once()

    # Second call reuses cache.
    assert vs.get_collection() is fake_collection
    assert fake_chromadb.PersistentClient.call_count == 1

    # Restore stub used by other API tests.
    stub = MagicMock()
    stub.add_medicine_to_vector_db = MagicMock()
    stub.delete_medicine_from_vector_db = MagicMock()
    stub.search_similar_medicines = MagicMock(
        return_value=[{"name": "Aspirin", "score": 0.1}]
    )
    stub.get_collection = MagicMock(return_value=MagicMock())
    stub.reset_collection_for_tests = MagicMock()
    sys.modules["backend.services.vector_search"] = stub
