# Deployment — Render + Render Postgres + S3

Target architecture for PharmaAssist:

```text
Browser / React (frontend-web)
        │  HTTPS + Bearer JWT
        ▼
Render Web Service  (FastAPI; embeddings via pgvector)
        │
        ├── Render Postgres  (DATABASE_URL + pgvector)
        └── AWS S3           (prescriptions when STORAGE_BACKEND=s3)
```

For services, API prefixes, and end-to-end request flows (login, sell, similar-search,
OCR, agent), see **[architecture.md](architecture.md)**.

## 1. Render Postgres

1. In the Render dashboard create a **PostgreSQL** instance.
2. Copy the **Internal Database URL** (same private network as the web service).
3. Set as `DATABASE_URL` on the web service. The app rewrites `postgres://` / `postgresql://` to `postgresql+psycopg://` automatically.
4. On first boot the app runs `CREATE EXTENSION IF NOT EXISTS vector` and creates
   `medicine_embeddings` + an HNSW index. You can also enable the extension once
   manually in the Render Postgres shell: `CREATE EXTENSION vector;`

## 2. Render Web Service (main app)

1. New **Web Service** from this GitHub repo.
2. Runtime: **Docker** (repo `Dockerfile`) or Python:
   - Build: `pip install -r requirements-api.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. **No persistent disk** is required for vector search (pgvector lives in Postgres).

### Required env vars

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Render Postgres URL |
| `JWT_SECRET` | Long random secret |
| `BOOTSTRAP_ADMIN_EMAIL` | First admin (only when users table empty) |
| `BOOTSTRAP_ADMIN_PASSWORD` | First admin password |
| `GEMINI_API_KEY` | OCR + inventory chat planning |
| `CORS_ORIGINS` | Your React frontend origin(s) |

Remove unused `CHROMA_PATH` / disk mounts if present from older deploys.

### Health checks (Render)

- Liveness: `GET /health/live`
- Readiness: `GET /health/ready` (fails only if DB is down; pgvector missing → `degraded`; SQLite would show `skipped`)

### After deploy (embeddings)

1. Confirm `checks.pgvector.status` is `ok` on `/health/ready`.
2. As pharmacist/admin: `POST /search/reindex` (backfills all medicines).
3. Smoke **Find alternatives** on Billing/OCR or `POST /search/similar`.

### S3 prescription storage

| Variable | Purpose |
|----------|---------|
| `STORAGE_BACKEND` | `s3` in production (`local` default for DIY) |
| `S3_BUCKET` | Bucket name |
| `S3_REGION` | e.g. `ap-south-1` |
| `AWS_ACCESS_KEY_ID` | IAM user key |
| `AWS_SECRET_ACCESS_KEY` | Secret |
| `S3_ENDPOINT_URL` | Optional (R2 / MinIO) |

`POST /ocr/extract` stores the image then returns OCR fields plus `file_key`.

## 3. First deploy checklist

1. Deploy Postgres + Web Service.
2. Confirm `GET /health/live` and `GET /health/ready`.
3. Login → `POST /auth/login`.
4. Create pharmacist/cashier via `POST /auth/register`.
5. Prefer `GET /inventory/?page=1&limit=20` over `/inventory/all`.
6. `POST /search/reindex` once inventory exists.

## 4. Local vs production

| Local | Production (Render) |
|-------|---------------------|
| SQLite default (`pharma.db`) — vectors stubbed | Render Postgres via `DATABASE_URL` |
| Optional: `docker compose -f docker-compose.pgvector.yml up -d` + `DATABASE_URL` | pgvector embeddings in same DB |
| `STORAGE_BACKEND=local` | `STORAGE_BACKEND=s3` + AWS keys |

See also [architecture.md](architecture.md), [auth.md](auth.md), [environment.md](environment.md), and [vector-search.md](vector-search.md).
