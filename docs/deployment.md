# Deployment — Render + Render Postgres + S3

Target architecture for PharmaAssist:

```text
Browser / future React
        │
        ▼
Render Web Service  (FastAPI + Chroma on persistent disk)
        │
        ├── Render Postgres  (DATABASE_URL)
        └── AWS S3           (prescriptions when STORAGE_BACKEND=s3)
```

## 1. Render Postgres

1. In the Render dashboard create a **PostgreSQL** instance.
2. Copy the **Internal Database URL** (same private network as the web service).
3. Set as `DATABASE_URL` on the web service. The app rewrites `postgres://` / `postgresql://` to `postgresql+psycopg://` automatically.

## 2. Render Web Service (main app)

1. New **Web Service** from this GitHub repo.
2. Runtime: **Docker** (repo `Dockerfile`) or Python:
   - Build: `pip install -r requirements-api.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Attach a **persistent disk**, mount e.g. `/data`, and set:

```env
CHROMA_PATH=/data/chroma_store
```

### Required env vars

| Variable | Purpose |
|----------|---------|
| `DATABASE_URL` | Render Postgres URL |
| `JWT_SECRET` | Long random secret |
| `BOOTSTRAP_ADMIN_EMAIL` | First admin (only when users table empty) |
| `BOOTSTRAP_ADMIN_PASSWORD` | First admin password |
| `GEMINI_API_KEY` | OCR |
| `CORS_ORIGINS` | Your frontend origin(s) |
| `CHROMA_PATH` | Path on the persistent disk |

### Health checks (Render)

- Liveness: `GET /health/live`
- Readiness: `GET /health/ready` (fails only if DB is down; Chroma down → `degraded`)

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

## 4. Local vs production

| Local | Production (Render) |
|-------|---------------------|
| SQLite default file | Render Postgres via `DATABASE_URL` |
| `STORAGE_BACKEND=local` | `STORAGE_BACKEND=s3` + AWS keys |
| Optional chroma under repo | Disk mount `CHROMA_PATH` |

See also [auth.md](auth.md) and [environment.md](environment.md).
