# System architecture

PharmaAssist is a pharmacy operations stack: **React staff UI** → **FastAPI** →
**SQL inventory / sales / auth**, with **pgvector** similar-search, **Gemini** OCR
& chat planning, and optional **S3** prescription storage.

For env vars see [environment.md](environment.md). For deploy see [deployment.md](deployment.md).

## System overview

```mermaid
flowchart TB
  subgraph actors["Actors"]
    Staff["Staff browser<br/>cashier · pharmacist · admin"]
    Legacy["Streamlit UI<br/>legacy · no JWT"]
  end

  subgraph ui["Client"]
    React["frontend-web<br/>Vite + React<br/>/login /dashboard /inventory<br/>/billing /ocr /chat /admin"]
  end

  subgraph api["FastAPI — backend.main"]
    Health["/health"]
    Auth["/auth"]
    Inv["/inventory"]
    Sales["/sales"]
    Search["/search"]
    OCR["/ocr"]
    Agent["/agent"]
  end

  subgraph services["Services"]
    JWT["JWT + RBAC"]
    Sync["vector_sync<br/>background index"]
    VS["vector_search<br/>+ embeddings ONNX"]
    Drug["drug_api<br/>summaries"]
    OCRSvc["ocr_service"]
    Store["storage<br/>local or S3"]
    Agt["inventory_agent<br/>NL→SQL gates"]
    Audit["audit"]
  end

  subgraph data["Data stores"]
    SQL[("SQLite or Postgres<br/>medicines · users · sales<br/>sale_items · audit_logs")]
    PGV[("Postgres pgvector<br/>medicine_embeddings")]
    Obj[("uploads/ or S3<br/>prescription images")]
  end

  subgraph external["External"]
    Gemini["Google Gemini"]
    DrugAPIs["Wikipedia · PubChem · OpenFDA"]
  end

  Staff --> React
  Legacy -.->|"unauthenticated<br/>legacy calls"| Inv
  Legacy -.-> OCR
  React -->|"Bearer JWT JSON/HTTP"| Health & Auth & Inv & Sales & Search & OCR & Agent

  Auth --> JWT --> SQL
  Inv --> SQL
  Inv --> Sync
  Inv --> Audit
  Sales --> SQL
  Sales --> Audit
  Sync --> Drug
  Drug --> DrugAPIs
  Drug -.-> Gemini
  Sync --> VS
  VS --> PGV
  Search --> VS
  Search --> Drug
  OCR --> Store --> Obj
  OCR --> OCRSvc --> Gemini
  Agent --> Agt
  Agt --> Gemini
  Agt --> SQL
```

## Layers (code map)

```text
frontend-web/            React staff app (primary UI)
frontend/                Streamlit UI (legacy; no JWT)
backend/main.py          FastAPI app, CORS, router mount, lifespan bootstrap
backend/api/             Thin HTTP routers
backend/schemas/         Pydantic request/response models
backend/services/        Business logic (search, OCR, agent, storage, audit, …)
backend/db/              SQLAlchemy engine, sessions, ORM models
backend/core/            Config, JWT, deps, roles, errors
scripts/                 init_db, reindex, smoke helpers
```

## Data stores

| Store | Role | Config |
|-------|------|--------|
| SQLite (`pharma.db`) or Postgres | Source of truth: inventory, users, sales, audit | `DATABASE_URL` (default SQLite) |
| Postgres `medicine_embeddings` (pgvector) | Similar-medicine vectors (384-d MiniLM) | Requires PostgreSQL `DATABASE_URL` |
| Local `uploads/` or S3 | Prescription images from OCR | `STORAGE_BACKEND` |

On **SQLite**, vector upserts are no-ops; `/search/similar` falls back to fuzzy name matching when vectors are empty.

## Dual-write: SQL inventory ↔ pgvector

On **add**, **update**, and **delete**:

1. Commit SQL first (inventory is source of truth).
2. Queue drug-summary fetch + embedding upsert/delete on a background worker (`vector_sync`).
3. On SQLite, vector steps are no-ops.

**Sell** only changes SQL quantities (and writes `sales` / `sale_items`) in one transaction. Embeddings are unchanged (they store semantic text, not stock). Stock 0/low does **not** recompute embeddings — quantity is a search filter only.

Stock mutations take **pessimistic row locks** (`SELECT … FOR UPDATE`, refresh ORM via `populate_existing`):

- **Sell** — lock every cart medicine in `id` order, then re-check quantity (so two cashiers cannot both take the last unit).
- **Void** — lock the sale row first (blocks double-void), then lock medicines in `id` order before restoring qty.
- **Update / delete** — lock the medicine row so a concurrent sell cannot lose its decrement.

SQLite ignores `FOR UPDATE`; production Postgres enforces it. Locking by sorted `id` avoids multi-item deadlocks.

| Outcome | Behavior |
|---------|----------|
| SQL commit fails | Request fails |
| SQL OK, embedding fails later | Inventory kept; failure logged; HTTP still 200 |
| Both OK | Normal 200 |

Repair search with `POST /search/reindex`. Set `VECTOR_SYNC_INLINE=1` in tests.

---

## Major request flows

### 1. Login

```mermaid
sequenceDiagram
  participant UI as React /login
  participant API as POST /auth/login
  participant DB as users

  UI->>API: email + password
  API->>DB: verify hash
  API->>DB: store hashed refresh token
  API-->>UI: access_token + Set-Cookie (httpOnly refresh)
  Note over UI: Access JWT in memory; refresh cookie used on /auth/refresh
```

### 2. Inventory CRUD + index

```mermaid
sequenceDiagram
  participant UI as React /inventory
  participant API as /inventory/*
  participant SQL as medicines
  participant Sync as vector_sync
  participant Emb as medicine_embeddings

  UI->>API: add / update / delete (JWT)
  API->>SQL: commit
  API-->>UI: 200
  API->>Sync: background job
  Sync->>Sync: drug summary + embed
  Sync->>Emb: upsert / delete
```

### 3. Sell / invoice

```mermaid
sequenceDiagram
  participant UI as React /billing
  participant Sell as POST /inventory/sell
  participant SQL as medicines + sales
  participant Hist as GET /sales

  UI->>Sell: medicines[{id?, name, qty}] + patient/doctor/clinic
  Sell->>SQL: match by id or case-insensitive name
  Sell->>SQL: SELECT medicines FOR UPDATE (id order)
  Sell->>SQL: re-check qty, decrement + Sale + SaleItem + audit (one txn)
  Sell-->>UI: invoice {items, total, timestamp, sale_id}
  UI->>Hist: list / void as needed
```

### 4. Similar search (alternatives)

```mermaid
sequenceDiagram
  participant UI as Billing / OCR
  participant API as POST /search/similar
  participant SQL as medicines
  participant Emb as medicine_embeddings
  participant Drug as drug_api
  participant EF as embed_text

  UI->>API: medicine_name, top_k
  API->>SQL: case-insensitive inventory match (any qty)
  alt In inventory AND stored embedding exists
    API->>Emb: reuse vector as query
  else Missing name OR no embedding
    API->>Drug: summary (Wiki/PubChem/OpenFDA/Gemini)
    API->>EF: fresh embed of summary or name
  end
  API->>Emb: cosine vs in-stock (qty > 0), exclude self
  alt No vector hits
    API->>SQL: fuzzy name fallback
  end
  API-->>UI: [{medicine_id, name, score, quantity}]
```

### 5. OCR → review → sell

```mermaid
sequenceDiagram
  participant UI as React /ocr
  participant OCR as POST /ocr/extract
  participant Store as storage
  participant Gemini as Gemini OCR
  participant Sell as POST /inventory/sell

  UI->>OCR: multipart image (JWT)
  OCR->>Store: save file → file_key
  OCR->>Gemini: extract fields
  OCR-->>UI: patient, meds, doctor, clinic, file_key
  UI->>Sell: optional charge after availability check
```

### 6. Inventory chat agent

```mermaid
sequenceDiagram
  participant UI as React /chat
  participant API as POST /agent/query
  participant Plan as Gemini planner
  participant Gate as SQL safety gate
  participant SQL as medicines/sales

  UI->>API: {question}
  API->>Plan: tool or guarded SQL plan
  alt SQL mode
    API->>Gate: SELECT/WITH only, allowlisted tables, LIMIT
    Gate->>SQL: execute
  else Tool fallback
    API->>SQL: ORM/keyword tools
  end
  API-->>UI: answer + mode + sql? + rows
```

### 7. Reindex

`POST /search/reindex` (pharmacist/admin) rebuilds embeddings for all medicines via background jobs. See [vector-search.md](vector-search.md).

---

## API surface

| Prefix | Purpose |
|--------|---------|
| `GET /`, `/health/live`, `/health/ready` | Liveness / readiness |
| `/auth` | Login, refresh, logout, me, users, register, audit |
| `/inventory` | CRUD, low-stock, **sell** |
| `/sales` | Summary, history, void |
| `/search` | Similar, reindex |
| `/ocr` | Prescription extract |
| `/agent` | NL inventory chat |

### Contract highlights

| Method | Path | Notes |
|--------|------|--------|
| POST | `/auth/login` | → `{ access_token, expires_in, user }` + httpOnly refresh cookie |
| POST | `/auth/refresh` | Cookie → new access JWT; rotates refresh cookie |
| POST | `/auth/logout` | Revokes refresh token and clears cookie |
| GET | `/inventory/?page&limit&q…` | Paginated list |
| GET | `/inventory/all` | Full list (compat) |
| POST | `/inventory/sell` | `{ medicines: [{ id?, name, quantity }], patient?, doctor?, clinic? }` → invoice |
| GET | `/sales/`, `/sales/summary`, `POST /sales/{id}/void` | History / metrics / void |
| POST | `/search/similar` | → `[{ medicine_id, name, score, quantity? }]` |
| POST | `/search/reindex` | Pharmacist+ |
| POST | `/ocr/extract` | Multipart → JSON + `file_key` |
| POST | `/agent/query` | `{ question }` → answer + plan metadata |

Schemas live under `backend/schemas/`. Auth details: [auth.md](auth.md). Agent gates: [inventory-agent.md](inventory-agent.md).

## Testing

See [testing.md](testing.md). Prefer pytest; use temp `DATABASE_URL` never production DB.
