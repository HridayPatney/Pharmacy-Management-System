# Backend architecture

## Layers

```
frontend/ (Streamlit today → React later)
        │  HTTP JSON
        ▼
backend/main.py          FastAPI app, CORS, router mount
backend/api/             Route handlers (thin)
backend/schemas/         Pydantic request/response models
backend/services/        Drug metadata, pgvector search, Gemini OCR, vector sync
backend/db/              SQLAlchemy engine, sessions, ORM models
backend/core/config.py   Paths, secrets, CORS, JWT from environment
backend/core/deps.py     Auth dependencies (Bearer JWT, roles)
scripts/experiments/     Non-production prototypes (scrapers, seed scripts)
```

Embedding model loads **lazily** on first Postgres vector operation — see
[vector-search.md](vector-search.md). Auth and roles are documented in
[auth.md](auth.md). Deploy on Render + Render Postgres + S3 — see
[deployment.md](deployment.md).
## Data stores

| Store | Role | Config |
|-------|------|--------|
| SQLite (`pharma.db`) or Postgres | Source of truth for inventory quantity, price, expiry | `DATABASE_URL` or project-root default |
| Postgres `medicine_embeddings` (pgvector) | Embeddings for similar-medicine search | Requires PostgreSQL `DATABASE_URL` |

## Dual-write: SQL inventory ↔ pgvector

On **add**, **update**, and **delete**, inventory routes update SQL first, then sync embeddings:

1. Commit the SQLAlchemy change (inventory DB is the source of truth).
2. **Queue** drug-summary fetch + embedding upsert/delete on a background worker so the API responds immediately.
3. Sync through `backend.services.vector_sync` (upsert or delete by medicine `id`). On **SQLite**, vector ops are no-ops.

**Sell** only changes SQL quantities inside a **single transaction** (validate all lines, then apply, then one `commit`). Embeddings are untouched because they store name/description, not stock. If any line fails validation, the whole sell is rolled back.

### Sync failure policy

SQL and embeddings are **not** one ACID transaction with the background worker.

| Outcome | Behavior |
|---------|----------|
| SQL commit fails | Request fails; nothing to sync |
| SQL OK, embedding fails later | Inventory change is kept; failure is **logged**; HTTP still **200** (indexing is best-effort / background) |
| Both OK | Normal 200 response |

Do **not** roll back SQL when embedding fails: stock accuracy beats search freshness. To repair search, call `POST /search/reindex` or update the medicine. Set `VECTOR_SYNC_INLINE=1` in tests to run indexing on the request thread.

## API contracts (do not break without a UI migration)

| Method | Path | Notes |
|--------|------|--------|
| GET | `/` | Liveness (compat) |
| GET | `/health/live` | Process liveness |
| GET | `/health/ready` | DB + pgvector (+ optional Gemini) |
| POST | `/inventory/add` | Body = medicine fields; rejects duplicate `id` |
| GET | `/inventory/` | Paginated list `?page&limit&q&low_stock&sort&order` |
| GET | `/inventory/all` | Full list (compat) |
| PUT | `/inventory/update/{med_id}` | Full replace + re-embed |
| DELETE | `/inventory/delete/{med_id}` | SQL + pgvector (no-op vectors on SQLite) |
| GET | `/inventory/low-stock` | `threshold` query (default 10) |
| POST | `/inventory/sell` | `{ "medicines": [{ "name", "quantity" }] }` → `{ "invoice": { items, total, timestamp } }` |
| POST | `/search/similar` | `{ medicine_name, top_k? }` → `[{ name, score }]` (score = cosine distance) |
| POST | `/search/reindex` | Rebuild all embeddings (pharmacist+) |
| POST | `/ocr/extract` | Multipart image → prescription JSON + `file_key` |

## Schemas

Pydantic v2 models live under `backend/schemas/`. Routers should not define ad-hoc request bodies for inventory or search.

## Testing

See [testing.md](testing.md). Prefer `pytest` for unit and API tests; `scripts/smoke_test.py` remains a thin entrypoint after merges.
