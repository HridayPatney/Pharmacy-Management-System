# Backend architecture

## Layers

```
frontend/ (Streamlit today → React later)
        │  HTTP JSON
        ▼
backend/main.py          FastAPI app, CORS, router mount
backend/api/             Route handlers (thin)
backend/schemas/         Pydantic request/response models
backend/services/        Drug metadata, Chroma search, Gemini OCR
backend/db/              SQLAlchemy engine, sessions, ORM models
backend/core/config.py   Paths, secrets, CORS from environment
```

## Data stores

| Store | Role | Config |
|-------|------|--------|
| SQLite (`pharma.db`) | Source of truth for inventory quantity, price, expiry | `DATABASE_URL` or project-root default |
| Chroma (`chroma_store/`) | Embeddings for similar-medicine search | `CHROMA_PATH`, `CHROMA_COLLECTION`, `EMBEDDING_MODEL` |

## Dual-write: SQLite ↔ Chroma

On **add**, **update**, and **delete**, inventory routes update SQLite and then sync Chroma:

1. Commit the SQLAlchemy change.
2. Fetch (or clear) a drug summary via `drug_api`.
3. Add/delete the corresponding Chroma document by medicine `id`.

**Sell** only changes SQLite quantities; embeddings stay valid because metadata is name/description, not stock.

These two stores are **not** in one ACID transaction. A crash between commit and Chroma update can leave them briefly out of sync. Hardening that policy is covered in a later reliability PR; until then, re-add/update the medicine to refresh the vector index.

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
