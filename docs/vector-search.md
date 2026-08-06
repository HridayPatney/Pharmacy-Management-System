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

The ONNX MiniLM embedder (Chroma’s `DefaultEmbeddingFunction`, no PersistentClient)
loads on the **first** Postgres vector operation:

- `POST /inventory/add` / `update` / `delete` (via `vector_sync`, background after DB commit)
- `POST /search/similar`
- `POST /search/reindex`

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

`POST /search/similar` returns `[{ "name", "score", "quantity?" }]` where `score`
is cosine distance (lower is closer).
