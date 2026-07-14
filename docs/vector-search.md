# Vector search (Chroma)

## When the ML stack loads

Importing `backend.main` or hitting `GET /` does **not** load Chroma or
sentence-transformers.

Those dependencies initialize on the **first** call that needs embeddings:

- `POST /inventory/add` / `update` / `delete` (via `vector_sync`)
- `POST /search/similar`
- Scripts such as `scripts/view_vector_db.py` or `scripts/experiments/load_medicines_to_vector_db.py`

OCR (`google.genai`, optional OpenCV for the local demo preprocess) also loads
lazily inside `ocr_service` when `extract_json` / `clean_image` run.

## Configuration

| Variable | Default | Notes |
|----------|---------|-------|
| `CHROMA_PATH` | `<repo>/chroma_store` | Persistence directory |
| `CHROMA_COLLECTION` | `medicine_embeddings` | Collection name |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Must match how existing vectors were built |

Changing `EMBEDDING_MODEL` or `CHROMA_COLLECTION` without reindexing makes
similarity results wrong or empty.

## Reindex

1. Stop the API process.
2. Optionally delete or rename the old `CHROMA_PATH` directory (backup first).
3. Set the new env vars in `.env`.
4. Restart the API and re-add medicines (inventory **update** or **add**), or run
   `python scripts/experiments/load_medicines_to_vector_db.py` for a sample seed.
5. Confirm with `python scripts/view_vector_db.py`.

Response shape for `POST /search/similar` remains `[{ "name", "score" }]` where
`score` is Chroma distance (lower is closer).
