# Vector search (Chroma)

## When the ML stack loads

Importing `backend.main` or hitting `GET /` does **not** load Chroma.

Chroma initializes on the **first** call that needs embeddings:

- `POST /inventory/add` / `update` / `delete` (via `vector_sync`, **background** after DB commit)
- `POST /search/similar`
- Scripts such as `scripts/view_vector_db.py` or `scripts/experiments/load_medicines_to_vector_db.py`

Embeddings use Chroma's **default ONNX MiniLM** function (`onnxruntime`), not
PyTorch / sentence-transformers — so a normal `pip install -r requirements-api.txt`
is enough on Windows.

OCR (`google.genai`, optional OpenCV for the local demo preprocess) also loads
lazily inside `ocr_service` when `extract_json` / `clean_image` run.

## Configuration

| Variable | Default | Notes |
|----------|---------|-------|
| `CHROMA_PATH` | `<repo>/chroma_store` | Persistence directory |
| `CHROMA_COLLECTION` | `medicine_embeddings` | Collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Reserved / documented; API uses Chroma default ONNX EF |

Changing `CHROMA_COLLECTION` without reindexing makes similarity results wrong or empty.

## Reindex

When ``chroma_store`` is wiped or search returns empty while inventory still
has medicines, rebuild embeddings from SQL:

1. **API (pharmacist/admin):** ``POST /search/reindex`` — queues a background
   embedding job per medicine (inline under ``VECTOR_SYNC_INLINE=1`` in tests).
2. **UI:** Inventory → **Rebuild search embeddings**.
3. **CLI:** ``python scripts/reindex_vectors.py`` (runs sync inline).

Optional: delete or rename the old ``CHROMA_PATH`` directory first if the
collection/model changed.

Confirm with ``python scripts/view_vector_db.py``.

Response shape for ``POST /search/similar`` remains ``[{ "name", "score" }]`` where
``score`` is Chroma distance (lower is closer).
