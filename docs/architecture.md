# Backend architecture

## Layers

```
frontend/ (Streamlit today → React later)
        │  HTTP JSON
        ▼
backend/main.py          FastAPI app, CORS, router mount
backend/api/             Route handlers (thin)
backend/schemas/         Pydantic request/response models
backend/services/        Drug metadata, Chroma search, Gemini OCR, vector sync
backend/db/              SQLAlchemy engine, sessions, ORM models
backend/core/config.py   Paths, secrets, CORS from environment
scripts/experiments/     Non-production prototypes (scrapers, seed scripts)
```

Chroma/sentence-transformers load **lazily** on first vector operation — see
[vector-search.md](vector-search.md).

## Data stores

| Store | Role | Config |
|-------|------|--------|
| SQLite (`pharma.db`) | Source of truth for inventory quantity, price, expiry | `DATABASE_URL` or project-root default |
| Chroma (`chroma_store/`) | Embeddings for similar-medicine search | `CHROMA_PATH`, `CHROMA_COLLECTION`, `EMBEDDING_MODEL` |

## Dual-write: SQLite ↔ Chroma

On **add**, **update**, and **delete**, inventory routes update SQLite and then sync Chroma:

1. Commit the SQLAlchemy change (SQLite is the source of truth).
2. Fetch a drug summary via `drug_api` when indexing (add/update).
3. Sync Chroma through `backend.services.vector_sync` (upsert or delete by medicine `id`).

**Sell** only changes SQLite quantities inside a **single transaction** (validate all lines, then apply, then one `commit`). Embeddings are untouched because they store name/description, not stock. If any line fails validation, the whole sell is rolled back.

### Sync failure policy

SQLite and Chroma are **not** one ACID transaction across processes.

| Outcome | Behavior |
|---------|----------|
| SQLite commit fails | Request fails; nothing to sync |
| SQLite OK, Chroma fails | Inventory change is kept; API returns **HTTP 503** with a message to retry indexing (e.g. call update again) |
| Both OK | Normal 200 response |

Do **not** roll back SQLite when Chroma fails: stock accuracy beats search freshness. To repair search, re-run update (or delete/re-add) for the affected medicine.

## API contracts (do not break without a UI migration)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | Liveness |
| POST | `/inventory/add` | Body = medicine fields; rejects duplicate `id` |
| GET | `/inventory/all` | Full list |
| PUT | `/inventory/update/{med_id}` | Full replace + re-embed |
| DELETE | `/inventory/delete/{med_id}` | SQLite + Chroma |
| GET | `/inventory/low-stock` | `threshold` query (default 10) |
| POST | `/inventory/sell` | `{ "medicines": [{ "name", "quantity" }] }` → `{ "invoice": { items, total, timestamp } }` |
| POST | `/search/similar` | `{ medicine_name, top_k? }` → `[{ name, score }]` (score = distance) |
| POST | `/ocr/extract` | Multipart image → prescription JSON field names used by the UI |

## Schemas

Pydantic v2 models live under `backend/schemas/`. Routers should not define ad-hoc request bodies for inventory or search.

## Testing

See [testing.md](testing.md). Prefer `pytest` for unit and API tests; `scripts/smoke_test.py` remains a thin entrypoint after merges.
