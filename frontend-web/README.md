# PharmaAssist React frontend

Vite + React + TypeScript UI for the FastAPI backend.

## Setup

```bash
cd frontend-web
cp .env.example .env
npm install
npm run dev
```

App: http://localhost:5173  
API (default): http://localhost:8000 — set `VITE_API_URL` if different.

Ensure the backend `.env` includes your origin in `CORS_ORIGINS`, e.g.:

```env
CORS_ORIGINS=http://localhost:5173,http://localhost:8501
```

## Scripts

| Command | Purpose |
|---------|---------|
| `npm run dev` | Dev server |
| `npm run test` | Vitest unit/UI tests |
| `npm run build` | Production build |

## Features

- Login (`POST /auth/login`) + Bearer token on all staff routes
- Inventory list with pagination / search / low-stock filter; add/update/delete for pharmacist & admin
- OCR upload → availability / alternatives → sell + invoice view

## Roles

| Role | Inventory write | Sell / OCR |
|------|-----------------|------------|
| cashier | No | Yes |
| pharmacist | Yes | Yes |
| admin | Yes | Yes |
