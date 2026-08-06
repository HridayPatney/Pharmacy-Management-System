"""Text → embedding vectors for similar-medicine search.

Uses Chroma's default ONNX MiniLM (same model as the old Chroma path) so
reindexed catalogs stay comparable. Loaded lazily on first embed call.
"""

from __future__ import annotations

import threading
from typing import Any

_lock = threading.Lock()
_ef: Any | None = None

# all-MiniLM-L6-v2 / Chroma DefaultEmbeddingFunction output size
EMBEDDING_DIM = 384


def reset_embedding_fn_for_tests() -> None:
    """Clear the cached embedding function (tests only)."""
    global _ef
    with _lock:
        _ef = None


def _get_embedding_fn() -> Any:
    global _ef
    if _ef is not None:
        return _ef
    with _lock:
        if _ef is not None:
            return _ef
        from chromadb.utils.embedding_functions import DefaultEmbeddingFunction

        _ef = DefaultEmbeddingFunction()
        return _ef


def embed_text(text: str) -> list[float]:
    """Return a 384-d embedding for ``text`` (empty string allowed)."""
    vectors = _get_embedding_fn()([text or ""])
    return list(vectors[0])
