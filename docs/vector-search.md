# Vector search (Postgres / pgvector)

Similar-medicine search stores embeddings in **PostgreSQL** via the
[`pgvector`](https://github.com/pgvector/pgvector) extension — the same database
as inventory (see [Render’s pgvector guidance](https://render.com/articles/simplify-ai-stack-managed-postgresql-pgvector)).

## SQLite vs Postgres

| Database | Behavior |
|----------|----------|
| **SQLite** (local default) | Vector upserts are **no-ops**; `/search/similar` returns `[]` then may use **fuzzy name fallback** |
| **PostgreSQL** | Full pgvector upsert + cosine search |

Day-to-day vector checks: run local Postgres with pgvector (see `docker-compose.pgvector.yml`) and set `DATABASE_URL`.

## When the ML stack loads

Importing `backend.main` or hitting `GET /` does **not** load the embedding model.

The ONNX MiniLM embedder loads on the **first** Postgres vector operation:

- `POST /inventory/add` / `update` / `delete` (via `vector_sync`, background after DB commit)
- `POST /search/similar` (only when a **fresh** embed is needed — not when reusing a stored vector)
- `POST /search/reindex`

## Query path (`POST /search/similar`)

1. If the typed name matches an **inventory** row (any stock, including 0) **and**
   that row has a stored embedding → **reuse** that vector (no drug-summary fetch,
   no re-embed).
2. Otherwise → fetch drug summary (or use the typed name) and **embed fresh**.
3. Rank against stored inventory embeddings with `quantity > 0`, excluding the
   queried medicine itself.
4. If vector search yields nothing → fuzzy **name** fallback on in-stock rows.

Stock changes do **not** recompute embeddings; quantity is only a filter.

## Configuration

| Variable | Notes |
|----------|-------|
| `DATABASE_URL` | Must be `postgresql…` for vector search |
| `EMBEDDING_MODEL` | Documented as `all-MiniLM-L6-v2` (384-d); keep one model for the whole catalog |

`CHROMA_PATH` / `CHROMA_COLLECTION` are **unused** for persistence (no disk mount needed on Render).

## Reindex

After deploy or when embeddings are empty:

```bash
# as pharmacist/admin
POST /search/reindex
```

Or locally against Postgres:

```bash
python scripts/reindex_vectors.py
```

Confirm with `GET /health/ready` (`checks.pgvector.status == ok`) and
`python scripts/view_vector_db.py`.

`POST /search/similar` returns `[{ "medicine_id", "name", "score", "quantity?" }]`
where `score` is cosine distance (lower is closer).

System context and sequence diagrams: [architecture.md](architecture.md).
