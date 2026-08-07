# PharmaAssist — Pharmacy Management System

FastAPI backend for inventory, sales, JWT auth, similar-medicine search
(Postgres/pgvector), prescription OCR (Gemini), and a read-only inventory chat
agent — with a **React** staff UI (`frontend-web`).

**Architecture (services, APIs, flows):** [docs/architecture.md](docs/architecture.md)

## Prerequisites

- Python 3.11+ recommended
- Node 20+ for the React UI
- A Gemini API key for OCR / chat planning (optional if you only use inventory)
- PostgreSQL + pgvector for semantic similar-search (SQLite is fine for CRUD locally)

## Quick start

### 1. Clone and create a virtual environment

```bash
git clone https://github.com/HridayPatney/Pharmacy-Management-System.git
cd Pharmacy-Management-System
python -m venv venv
```

Activate:

- Windows (PowerShell): `.\venv\Scripts\Activate.ps1`
- macOS / Linux: `source venv/bin/activate`

### 2. Install dependencies

API (recommended for backend work):

```bash
pip install -r requirements-api.txt
```

Full install (API + legacy Streamlit):

```bash
pip install -r requirements.txt
```

Pinned freeze: `requirements-lock.txt`. See [docs/dependencies.md](docs/dependencies.md).

### 3. Configure environment

```bash
cp .env.example .env
```

Set at least `JWT_SECRET`, bootstrap admin email/password, and (for OCR/chat)
`GEMINI_API_KEY`. Default CORS includes React (`5173`) and Streamlit (`8501`).
See [docs/environment.md](docs/environment.md) and [docs/auth.md](docs/auth.md).

### 4. Initialize the database

```bash
python scripts/init_db.py
```

Creates `pharma.db` (SQLite) by default. For similar-search locally:

```bash
docker compose -f docker-compose.pgvector.yml up -d
# set DATABASE_URL=postgresql://pharma:pharma@127.0.0.1:5432/pharma in .env
```

See [docs/vector-search.md](docs/vector-search.md).

### 5. Run the API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- Liveness: [http://localhost:8000/health/live](http://localhost:8000/health/live)
- OpenAPI: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Run the React UI (primary)

```bash
cd frontend-web
cp .env.example .env
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173). Set `VITE_API_URL` if the API is not on `http://127.0.0.1:8001` (see `frontend-web/.env.example`).

### 7. Legacy Streamlit UI (optional)

```bash
streamlit run frontend/app.py
```

Streamlit does **not** send JWTs — prefer React for auth-aware flows.

## Project layout

```
backend/          FastAPI app, routers, models, services
frontend-web/     React staff UI (primary)
frontend/         Streamlit UI (legacy)
scripts/          DB init, reindex, smoke helpers
docs/             Architecture and operational docs
tests/            pytest suite
```

## API overview

| Area | Prefix | Notes |
|------|--------|--------|
| Health | `/health` | live / ready (DB + pgvector) |
| Auth | `/auth` | login, users, audit |
| Inventory | `/inventory` | CRUD, low-stock, sell/invoice |
| Sales | `/sales` | summary, history, void |
| Search | `/search` | similar medicines, reindex |
| OCR | `/ocr` | prescription image → JSON |
| Agent | `/agent` | NL inventory chat |

## Documentation

- [System architecture](docs/architecture.md) — diagrams, services, request flows
- [Environment variables & secrets](docs/environment.md)
- [Authentication & roles](docs/auth.md)
- [Deployment (Render + Postgres + S3)](docs/deployment.md)
- [Vector search / reindex](docs/vector-search.md)
- [Inventory chat agent](docs/inventory-agent.md)
- [Testing](docs/testing.md)
- [Dependency files](docs/dependencies.md)

## Smoke test / pytest

```bash
python scripts/smoke_test.py
# or
pytest -q
```

See [docs/testing.md](docs/testing.md).
