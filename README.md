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

Edit `.env` and set `GEMINI_API_KEY`. See [docs/environment.md](docs/environment.md).

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
- [Dependency files](docs/dependencies.md)

## Security notes

- Do not commit `.env` or API keys.
- If a Gemini key was ever checked into git, rotate it immediately.
- Virtual environments (`venv/`) must never be committed.
