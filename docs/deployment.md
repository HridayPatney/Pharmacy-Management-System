# Deployment — Render + Render Postgres + S3

Target architecture for PharmaAssist:

```text
Browser / future React
        │
        ▼
Render Web Service  (FastAPI + Chroma on persistent disk)
        │
        ├── Render Postgres  (DATABASE_URL)
        └── AWS S3           (prescription images — next PR wires uploads)
```

## 1. Render Postgres

1. In the Render dashboard create a **PostgreSQL** instance.
2. Copy the **External Database URL** (or Internal if the web service is on Render too — prefer Internal).
3. You will set this as `DATABASE_URL` on the web service. The app rewrites `postgres://` / `postgresql://` to `postgresql+psycopg://` automatically.

## 2. Render Web Service (main app)

1. New **Web Service** from this GitHub repo.
2. Runtime: **Docker** (use the repo `Dockerfile`) or native Python:
   - Build: `pip install -r requirements-api.txt`
   - Start: `uvicorn backend.main:app --host 0.0.0.0 --port $PORT`
3. Attach a **persistent disk**, mount e.g. `/data`, and set:

```env
CHROMA_PATH=/data/chroma_store
```

(SQLite is not used in prod if `DATABASE_URL` points at Render Postgres.)

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

### S3 (ready for next PR)

| Variable | Purpose |
|----------|---------|
| `S3_BUCKET` | Bucket name |
| `S3_REGION` | e.g. `ap-south-1` |
| `AWS_ACCESS_KEY_ID` | IAM user / role key |
| `AWS_SECRET_ACCESS_KEY` | Secret |

OCR currently uses temp files; S3 wiring will read these same env vars.

## 3. First deploy checklist

1. Deploy Postgres + Web Service.
2. Confirm `GET /` returns OK.
3. Login with bootstrap admin → `POST /auth/login`.
4. Create pharmacist/cashier via `POST /auth/register`.
5. Rotate bootstrap password after first login if it was shared in the dashboard.

## 4. Local vs production

| Local | Production (Render) |
|-------|---------------------|
| SQLite default file | Render Postgres via `DATABASE_URL` |
| Optional chroma under repo | Disk mount `CHROMA_PATH` |
| `.env` file | Render Environment |

See also [auth.md](auth.md) and [environment.md](environment.md).
