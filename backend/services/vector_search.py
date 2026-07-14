"""Chroma-backed embeddings for medicine similarity search.

Collection name and storage path come from ``backend.core.config`` so the
store is not tied to the process working directory.
"""

from __future__ import annotations

import chromadb
from chromadb.utils import embedding_functions
from sentence_transformers import SentenceTransformer

from backend.core.config import (
    get_chroma_collection_name,
    get_chroma_path,
    get_embedding_model_name,
)

_embedding_model_name = get_embedding_model_name()

# Local SentenceTransformer instance (Chroma also embeds via its embedding function).
embedding_model = SentenceTransformer(_embedding_model_name)

chroma_client = chromadb.PersistentClient(path=get_chroma_path())
collection = chroma_client.get_or_create_collection(
    name=get_chroma_collection_name(),
    embedding_function=embedding_functions.SentenceTransformerEmbeddingFunction(
        _embedding_model_name
    ),
)


def add_medicine_to_vector_db(medicine_id, medicine_name, description):
    """Add or replace a medicine description in the Chroma collection."""
    try:
        collection.delete(ids=[medicine_id])
    except Exception:
        pass

    collection.add(
        documents=[description or ""],
        metadatas=[{"name": medicine_name}],
        ids=[medicine_id],
    )


def delete_medicine_from_vector_db(medicine_id):
    """Remove a medicine from the Chroma vector collection."""
    try:
        collection.delete(ids=[medicine_id])
    except Exception:
        pass


def search_similar_medicines(query_text, top_k=5):
    """Return up to ``top_k`` similar medicines for ``query_text``.

    Each result is ``{"name": str, "score": float}`` where ``score`` is Chroma
    distance (lower is more similar).
    """
    results = collection.query(
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
