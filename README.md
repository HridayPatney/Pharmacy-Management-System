# PharmaAssist — Pharmacy Management System

FastAPI backend for inventory, similar-medicine search (Chroma), and prescription OCR (Gemini), with a Streamlit UI.

## Prerequisites

- Python 3.11+ recommended
- A Gemini API key for OCR (optional if you only use inventory/search)

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

Full stack (API + Streamlit UI):

```bash
pip install -r requirements.txt
```

API only:

```bash
pip install -r requirements-api.txt
```

UI only (expects the API already running):

```bash
pip install -r requirements-ui.txt
```

Pinned full freeze (reproducible installs): `requirements-lock.txt`.

### 3. Configure environment

```bash
cp .env.example .env
```

Set at least `JWT_SECRET`, bootstrap admin email/password, and (for OCR) `GEMINI_API_KEY`.
See [docs/environment.md](docs/environment.md) and [docs/auth.md](docs/auth.md).

### 4. Initialize the database

From the repository root:

```bash
python scripts/init_db.py
```

This creates `pharma.db` (SQLite). Chroma data is stored under `chroma_store/` when medicines are added.

### 5. Run the API

```bash
uvicorn backend.main:app --reload --host 0.0.0.0 --port 8000
```

- Health: [http://localhost:8000/](http://localhost:8000/)
- OpenAPI docs: [http://localhost:8000/docs](http://localhost:8000/docs)

### 6. Run the Streamlit UI

In a second terminal (venv activated):

```bash
streamlit run frontend/app.py
```

Default UI: [http://localhost:8501](http://localhost:8501). The UI calls `http://localhost:8000`.

### 7. Run the React UI (recommended)

```bash
cd frontend-web
cp .env.example .env
npm install
npm run dev
```

App: [http://localhost:5173](http://localhost:5173). Set backend `CORS_ORIGINS` to include `http://localhost:5173`. See [frontend-web/README.md](frontend-web/README.md).

## Project layout

```
backend/          FastAPI app, routers, DB models, services
frontend/         Streamlit UI
scripts/          DB init and utility scripts
docs/             Environment and operational docs
```

## API overview

| Area | Prefix | Notes |
|------|--------|--------|
| Inventory | `/inventory` | CRUD, low-stock, sell/invoice |
| Search | `/search` | Similar medicines via embeddings |
| OCR | `/ocr` | Prescription image → structured JSON |

## Documentation

- [Environment variables & secrets](docs/environment.md)
- [Authentication & roles](docs/auth.md)
- [Deployment (Render + Postgres + S3)](docs/deployment.md)
- [Backend architecture](docs/architecture.md)
- [Vector search / reindex](docs/vector-search.md)
- [Testing](docs/testing.md)
- [Dependency files](docs/dependencies.md)

## Smoke test / pytest

With the venv activated and API packages installed:

```bash
python scripts/smoke_test.py
# or
pytest -q
```

See [docs/testing.md](docs/testing.md).

## Security notes

- Do not commit `.env` or API keys.
- If a Gemini key was ever checked into git, rotate it immediately.
- Virtual environments (`venv/`) must never be committed.
