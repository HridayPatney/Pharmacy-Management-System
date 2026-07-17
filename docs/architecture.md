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
backend/core/config.py   Paths, secrets, CORS, JWT from environment
backend/core/deps.py     Auth dependencies (Bearer JWT, roles)
scripts/experiments/     Non-production prototypes (scrapers, seed scripts)
```

Chroma/sentence-transformers load **lazily** on first vector operation — see
[vector-search.md](vector-search.md). Auth and roles are documented in
[auth.md](auth.md). Deploy on Render + Render Postgres + S3 — see
[deployment.md](deployment.md).
## Data stores

| Store | Role | Config |
|-------|------|--------|
| SQLite (`pharma.db`) | Source of truth for inventory quantity, price, expiry | `DATABASE_URL` or project-root default |
| Chroma (`chroma_store/`) | Embeddings for similar-medicine search | `CHROMA_PATH`, `CHROMA_COLLECTION`, `EMBEDDING_MODEL` |

## Dual-write: SQL inventory ↔ Chroma

On **add**, **update**, and **delete**, inventory routes update SQL first, then sync Chroma:

1. Commit the SQLAlchemy change (inventory DB is the source of truth).
2. **Queue** drug-summary fetch + Chroma upsert/delete on a background worker so the API responds immediately.
3. Sync Chroma through `backend.services.vector_sync` (upsert or delete by medicine `id`).

**Sell** only changes SQL quantities inside a **single transaction** (validate all lines, then apply, then one `commit`). Embeddings are untouched because they store name/description, not stock. If any line fails validation, the whole sell is rolled back.

### Sync failure policy

SQL and Chroma are **not** one ACID transaction across processes.

| Outcome | Behavior |
|---------|----------|
| SQL commit fails | Request fails; nothing to sync |
| SQL OK, Chroma fails later | Inventory change is kept; failure is **logged**; HTTP still **200** (indexing is best-effort / background) |
| Both OK | Normal 200 response |

Do **not** roll back SQL when Chroma fails: stock accuracy beats search freshness. To repair search after a wipe, use ``POST /search/reindex`` (or update individual medicines). Set `VECTOR_SYNC_INLINE=1` in tests to run indexing on the request thread.

## API contracts (do not break without a UI migration)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | Liveness (compat) |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | DB + Chroma (+ optional Gemini) |
| POST | `/inventory/add` | Body = medicine fields; rejects duplicate `id` |
| GET | `/inventory/` | Paginated list `?page&limit&q&low_stock&sort&order` |
| GET | `/inventory/all` | Full list (compat) |
| PUT | `/inventory/update/{med_id}` | Full replace + re-embed |
| DELETE | `/inventory/delete/{med_id}` | SQLite/Postgres + Chroma |
| GET | `/inventory/low-stock` | `threshold` query (default 10) |
| POST | `/inventory/sell` | `{ medicines, patient?, doctor?, clinic?, prescription_file_key? }` → invoice |
| POST | `/search/similar` | `{ medicine_name, top_k? }` → `[{ name, score }]` (score = distance) |
| POST | `/search/reindex` | Pharmacist/admin — rebuild Chroma from all SQL medicines |
| POST | `/ocr/extract` | Multipart image → prescription JSON + `file_key` |
| GET | `/ocr/prescription` | `?key=` — staff download/view stored Rx image |

Prescription uploads are durable (local or S3). Selling from OCR can attach
`prescription_file_key` on the ``Sale`` row so billing history can open the
original image. If Chroma is wiped, call ``POST /search/reindex`` (or
``scripts/reindex_vectors.py``) instead of manually re-adding every medicine.


## Schemas

Pydantic v2 models live under `backend/schemas/`. Routers should not define ad-hoc request bodies for inventory or search.

## Testing

See [testing.md](testing.md). Prefer `pytest` for unit and API tests; `scripts/smoke_test.py` remains a thin entrypoint after merges.
