"""Chroma-backed embeddings for medicine similarity search.

Chroma and the sentence-transformers embedding function are initialized on
**first use**, not at import time, so ``uvicorn`` / ``GET /`` stay fast.

Collection name and storage path come from ``backend.core.config``.
See ``docs/vector-search.md`` for load timing and reindex notes.
"""

from __future__ import annotations

import threading
from typing import Any

from backend.core.config import (
    get_chroma_collection_name,
    get_chroma_path,
    get_embedding_model_name,
)

_lock = threading.Lock()
_collection: Any | None = None


def get_collection():
    """Return the shared Chroma collection, creating the client on first call."""
    global _collection
    if _collection is not None:
        return _collection

    with _lock:
        if _collection is not None:
            return _collection

        import chromadb
        from chromadb.utils import embedding_functions

        model_name = get_embedding_model_name()
        client = chromadb.PersistentClient(path=get_chroma_path())
        _collection = client.get_or_create_collection(
            name=get_chroma_collection_name(),
            embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name
            ),
        )
        return _collection


def reset_collection_for_tests() -> None:
    """Clear the cached collection (test helper only)."""
    global _collection
    with _lock:
        _collection = None


def add_medicine_to_vector_db(medicine_id, medicine_name, description):
    """Add or replace a medicine description in the Chroma collection.

    Callers (``vector_sync``) are responsible for translating failures into API errors.
    """
    collection = get_collection()
    existing = collection.get(ids=[medicine_id])
    if existing and existing.get("ids"):
        collection.delete(ids=[medicine_id])

    collection.add(
        documents=[description or ""],
        metadatas=[{"name": medicine_name}],
        ids=[medicine_id],
    )


def delete_medicine_from_vector_db(medicine_id):
    """Remove a medicine from the Chroma vector collection.

    Missing ids are ignored; other Chroma errors propagate to the caller.
    """
    collection = get_collection()
    existing = collection.get(ids=[medicine_id])
    if existing and existing.get("ids"):
        collection.delete(ids=[medicine_id])


def search_similar_medicines(query_text, top_k=5):
    """Return up to ``top_k`` similar medicines for ``query_text``.

    Each result is ``{"name": str, "score": float}`` where ``score`` is Chroma
    distance (lower is more similar).
    """
    results = get_collection().query(
        query_texts=[query_text],
        n_results=top_k,
    )

    matches = []
    for i in range(len(results["documents"][0])):
        matches.append({
            "name": results["metadatas"][0][i]["name"],
            "score": results["distances"][0][i],
        })
    return matches
