# Environment variables

PharmaAssist loads configuration from the process environment and optionally from a local `.env` file at the repository root (via `python-dotenv`).

## Variables

| Name | Required | Default | Purpose |
|------|----------|---------|---------|
| `JWT_SECRET` | Yes | _(none)_ | Signs access tokens |
| `JWT_EXPIRE_MINUTES` | No | `15` | Access JWT lifetime |
| `REFRESH_EXPIRE_DAYS` | No | `7` | Refresh-cookie lifetime |
| `COOKIE_SAMESITE` | No | `none` | Override only; code default is `none` for split SPA + API |
| `COOKIE_SECURE` | No | on when SameSite is `none` | Override the `Secure` flag |
| `BOOTSTRAP_ADMIN_EMAIL` | First boot | _(none)_ | Seed admin when users table empty |
| `BOOTSTRAP_ADMIN_PASSWORD` | First boot | _(none)_ | Seed admin password |
| `GEMINI_API_KEY` | Yes for OCR / agent NL planning | _(none)_ | Gemini key for `POST /ocr/extract` and inventory chat planning |
| `GEMINI_OCR_MODEL` | No | `gemini-3-flash-preview` | Model for OCR (and agent if `GEMINI_AGENT_MODEL` unset) |
| `GEMINI_AGENT_MODEL` | No | same as OCR model | Optional override for `POST /agent/query` |
| `CORS_ORIGINS` | No | React `5173` + Streamlit `8501` on localhost and 127.0.0.1 | Comma-separated browser origins |
| `DATABASE_URL` | No | `sqlite:///<repo>/pharma.db` | SQLAlchemy URL (Postgres required for pgvector similar-search) |
| `EMBEDDING_MODEL` | No | `all-MiniLM-L6-v2` | Documented 384-d MiniLM model (ONNX via Chroma EF; not a Chroma disk store) |
| `VECTOR_SYNC_INLINE` | Tests | unset | `1` runs embedding jobs on the request thread |
| `HEALTH_CHECK_GEMINI` | No | `false` | Include Gemini key presence in `/health/ready` |
| `STORAGE_BACKEND` | No | `local` | `local` or `s3` for prescription images |
| `UPLOAD_DIR` | No | `<repo>/uploads` | Local upload directory |
| `S3_BUCKET` / `S3_REGION` / `AWS_*` / `S3_ENDPOINT_URL` | For S3 | _(none)_ | Object storage when `STORAGE_BACKEND=s3` |

Changing the embedding model without reindexing makes existing vectors unusable for search.

## Local setup

1. Copy `.env.example` to `.env` in the repository root.
2. Set `JWT_SECRET` and bootstrap admin credentials.
3. Set `GEMINI_API_KEY` for OCR / chat ([Google AI Studio](https://aistudio.google.com/apikey)).
4. Adjust `CORS_ORIGINS` if the UI runs on a different host or port.
5. Optional for similar-search: `docker compose -f docker-compose.pgvector.yml up -d` and set
   `DATABASE_URL=postgresql://pharma:pharma@127.0.0.1:5432/pharma`.

OCR endpoints raise a clear error if `GEMINI_API_KEY` is missing. Inventory CRUD works without Gemini; semantic similar-search needs Postgres.

## Secret hygiene

- Never commit `.env` or paste API keys into source files.
- If a key was ever committed to git history, **revoke and rotate it** immediately.
- Prefer environment variables or a secret manager in hosted deployments.

## CORS notes

- Prefer explicit origins (e.g. `http://localhost:5173` for React).
- `CORS_ORIGINS=*` disables credentialed CORS (browsers disallow `*` with credentials). Use a wildcard only for quick local experiments.

System context: [architecture.md](architecture.md).
