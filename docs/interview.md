# Interview guide — PharmaAssist

Prep sheet for explaining this project honestly and precisely. Prefer **what the
code does today** over older prototypes (Streamlit, Chroma disk store, FPDF).

Canonical architecture diagrams: [architecture.md](architecture.md).

---

## 1. Elevator pitch (30–45 seconds)

> PharmaAssist is a staff-facing pharmacy system: JWT-authenticated React UI on a
> FastAPI backend. Pharmacists manage inventory; cashiers bill with stock checks
> and similar-medicine alternatives via **Postgres pgvector**; prescriptions go
> through **Gemini OCR** with human review before sell; there’s a read-only
> NL inventory chat agent. Local default is SQLite; production is Render +
> Postgres + optional S3.

**Do not say:** “We use ChromaDB + Sentence-Transformers as the vector DB.”  
**Do say:** “Embeddings are 384-d MiniLM (ONNX); we **store and search them in
Postgres with pgvector**. Chroma’s embedding helper is only used to produce vectors.”

---

## 2. What to explain (story arc)

Use this order in interviews:

| # | Topic | One-liner |
|---|--------|-----------|
| 1 | Problem | Handwritten / scanned Rx + inventory mismatch → wrong dispense or lost sale |
| 2 | Actors | Admin, pharmacist, cashier — JWT roles |
| 3 | UI | React: inventory, billing, OCR, chat, admin |
| 4 | API | Thin FastAPI routers → services → SQL / pgvector / Gemini |
| 5 | Inventory truth | SQL quantities/prices; sell is one transaction |
| 6 | Search | Semantic alternatives for missing/low stock |
| 7 | OCR | Extract → review → sell (never silent inventory write) |
| 8 | Ops | Health checks, audit log, reindex, Render deploy |
| 9 | Honest limits | SQLite local only; agent is read-only; OCR needs human-in-the-loop |

### Architecture to draw on a whiteboard

```text
  Staff (React)
       │ Bearer JWT
       ▼
  FastAPI  ── /auth /inventory /sales /search /ocr /agent /health
       │
       ├── SQL (SQLite local / Postgres prod): medicines, users, sales, audit
       ├── pgvector: medicine_embeddings (same Postgres)
       ├── storage: uploads/ or S3 (Rx images)
       └── Gemini + Wiki/PubChem/OpenFDA (summaries / OCR / agent plan)
```

Walk **one vertical slice** deep (OCR→sell or similar-search), then zoom out.

Full mermaid + sequences: [architecture.md](architecture.md).

---

## 3. Rebuttals / “gotcha” corrections

Interviewers often assume older stack choices. Correct calmly:

| They say | You say |
|----------|---------|
| “So you use Chroma as the vector database?” | “We **used to** think that way; production path is **pgvector in Postgres**. Chroma’s package only supplies the ONNX embedding function — no PersistentClient for search.” |
| “Sentence-Transformers / PyTorch for embeds?” | “No — DefaultEmbeddingFunction / MiniLM ONNX, 384-d, same model for index and query.” |
| “OCR writes straight into inventory?” | “No. OCR returns structured JSON; staff review; **sell** decrements stock and creates a sale. Inventory catalog is a separate CRUD path.” |
| “SQLite in production?” | “**Local default** for DIY. **Render uses Postgres** (`DATABASE_URL`) so inventory and vectors share one DB.” |
| “FPDF for invoices?” | “Invoice PDF is **jsPDF in the React client** from the sell response. Backend returns invoice JSON.” |
| “The agent can update stock?” | “**Read-only.** Guarded SELECT / tools; no DML; `users`/`audit_logs` blocked.” |
| “Alternatives guarantee therapeutic substitution?” | “They are **semantic + inventory** suggestions (and fuzzy name fallback), not clinical decision support. Pharmacist still decides.” |

---

## 4. Prepared answers to common questions

### Q1. Walk me through: prescription upload → inventory / invoice data

**Answer structure:** clarify OCR ≠ add-to-catalog; then step the real path.

1. Cashier/pharmacist opens **OCR** page, uploads image (`POST /ocr/extract`, JWT).
2. API stores the file (`STORAGE_BACKEND=local` or **S3**) → `file_key`.
3. **Gemini** returns structured fields: patient, medicines[], doctor, clinic, date.
4. Names optionally filtered via **RxNorm** (invalid names dropped when RxNorm resolves).
5. UI shows lines + stock / **Find alternatives** (`POST /search/similar`) — human edits.
6. **Sell** (`POST /inventory/sell`): match by medicine `id` or case-insensitive name; **one transaction** decrements qty, writes `sales` + `sale_items`, audit; returns invoice JSON.
7. Client builds PDF (**jsPDF**) for download. Catalog add/update is a **separate** pharmacist flow (`/inventory/add`), which then background-indexes embeddings.

**If they insist “stored as inventory”:** “New SKUs are pharmacist CRUD; OCR feeds the **billing** path, not silent catalog inserts.”

---

### Q2. Why Gemini OCR instead of Tesseract? Tradeoffs?

**Why LLM/vision OCR here**

- Prescriptions are messy: handwriting, stamps, layouts — classic OCR needs heavy preprocess + brittle templates.
- We need **structured fields** (patient, drug list, doctor), not a raw text dump — Gemini returns JSON we contract on.
- Faster to ship a usable demo/MVP for placement than a full CV pipeline.

**Tradeoffs**

| Pros | Cons |
|------|------|
| Structure + language understanding | Cost / latency / API dependency |
| Better on varied Rx images | Non-determinism; need validation + UI review |
| Less hand-tuned CV | Privacy: images leave your network (mitigate with policy + S3 retention) |

**Tesseract** would be cheaper/offline but weaker on handwriting and still needs a second stage to parse fields. Hybrid (Tesseract + LLM cleanup) is a fair “what I’d do next” answer.

---

### Q3. Why FastAPI + SQLite instead of Flask + PostgreSQL?

**FastAPI**

- Native async-ready stack, first-class OpenAPI (`/docs`), Pydantic v2 validation — good for a typed API + React client.
- Dependency injection for JWT/roles (`Depends`) keeps routers thin.

**SQLite vs Postgres — not “SQLite forever”**

- **SQLite:** zero-ops local default so anyone can `uvicorn` + React without Docker.
- **Postgres:** production (`DATABASE_URL` on Render) and **required** for pgvector similar-search.
- Same SQLAlchemy models; app rewrites `postgres://` → `postgresql+psycopg://`.

So: SQLite = **prototyping / local DX**; Postgres = **real deploy + vectors**. Flask would work; FastAPI was chosen for OpenAPI + modern typing ergonomics, not because Flask can’t do JWT.

---

### Q4. Vector-based alternatives — how do we find “Paracetamol ≈ Crocin”?  
*(They may say ChromaDB + Sentence-Transformers — correct the stack.)*

**Actual mechanism**

1. On add/update (or reindex), fetch a **drug summary** (Wikipedia → PubChem → OpenFDA → Gemini).
2. Embed that text with **MiniLM 384-d** → store in `medicine_embeddings` (**pgvector**), keyed by `medicine_id`.
3. On `POST /search/similar`:
   - If the queried name is **in inventory** and already has an embedding (even qty 0 / low) → **reuse** that vector (no re-fetch/re-embed).
   - Else → summary/name → **fresh** embed.
4. Cosine distance against embeddings joined to medicines with **quantity > 0**, exclude self.
5. If empty → fuzzy **name** fallback on in-stock rows.

**Why Paracetamol and Crocin can rank close:** brand/generic often share indication/class language in summaries → nearby vectors. This is **not** a regulatory substitutability graph — say that out loud.

---

### Q5. OCR misreads a drug / dosage — what stops silent wrong invoice?

Layers (be honest about what’s automatic vs human):

1. **UI review** — OCR never auto-charges; staff edits lines before Charge.
2. **Stock badge / “not in inventory”** — sell resolves against catalog; unknown names fail with a clear error (not silent invent).
3. **Transactional sell** — multi-line sell validates all lines first; insufficient stock / missing med rolls back entirely.
4. **RxNorm filter** — drops names RxNorm doesn’t know (can over-filter; still not a full safety system).
5. **Alternatives** — if missing/low, suggest in-stock options; staff must click Use.
6. **Roles + audit** — sell logged; void restores stock.

**What we don’t claim:** automatic clinical verification of dose, interactions, or “always correct OCR.”

---

### Q6. Why FPDF / why not ReportLab or HTML→PDF?

**Correct product answer:** invoices are generated in the **browser with jsPDF** from the API invoice payload. No server-side FPDF/ReportLab in the React path.

**Why client PDF**

- Sell already returns the invoice JSON the UI shows — PDF is a view of that.
- No extra native deps on the API container; works offline once data is in the page.

**Tradeoffs vs HTML→PDF / ReportLab**

- jsPDF: simple tables, less “pretty print” than HTML/CSS templates.
- Server ReportLab: consistent branding, harder font/layout ops on Render.
- HTML→PDF (Playwright/Weasy): best layout, heavier ops.

“I’d move to a shared HTML template if pharmacies needed letterhead compliance.”

---

### Q7. Wikipedia + PubChem + OpenFDA — conflicting data?

**We don’t merge/reconcile fields.** `fetch_drug_summary` is a **priority fallback chain**:

1. Wikipedia summary  
2. else PubChem  
3. else OpenFDA  
4. else Gemini short clinical blurb  
5. else `"No data found."` (embed still may use the bare name at query time)

**Why that’s OK for this feature:** summaries are **embedding text for similarity**, not a displayed drug monograph that must be medically authoritative. First non-empty source wins → faster indexing, less conflict logic.

**Limitation to volunteer:** brand vs salt naming can skew neighbors; reindex after improving the summary strategy; never treat embeddings as clinical truth.

---

### Q8. Embedding pipeline — names only vs names + composition + description?

**Index-time:** we embed the **fetched drug summary** (description/indication-style text), stored with `medicine_id` + name. Not “name alone” when a summary exists.

**Query-time:** prefer **stored vector** if inventory row exists; else embed summary or typed name.

**Why it matters**

| Embed | Effect |
|-------|--------|
| Name only | “Crocin” vs “Paracetamol” may be far in string space / weak semantically |
| Summary / indication text | Shared class/use language pulls brands and generics closer |
| Full label dump | Noisy; can dominate with manufacturer boilerplate |

Choice: **short clinical/indication summary** balances signal vs noise for “what else in stock is like this.”

---

### Q9. Scale to a pharmacy chain — what breaks first?

Priority order (honest):

1. **SQLite** (if anyone still used it) — writer lock; we already move prod to Postgres.
2. **Synchronous Gemini on OCR / agent / cold summary path** — latency + rate limits under concurrent Rx.
3. **Background vector_sync on same web dyno** — better as a worker queue (RQ/Celery) + dedicated embed workers.
4. **`GET /inventory/all` / unbounded lists** — pagination is preferred; Billing should keep using paged/catalog merge carefully.
5. **Single-region Render + one DB** — need read replicas, connection pooling, multi-store tenancy (`pharmacy_id` missing today).
6. **Client-only PDF / no print service** — fine for one counter, weak for centralized compliance printing.
7. **Agent NL→SQL** — prompt injection / expensive plans under abuse → stricter quotas, caching, pre-agg dashboards.

**What scales reasonably already:** Postgres+pgvector for catalog-sized search; JWT stateless API; S3 for images.

---

### Q10. Hardest bug or design decision?

**Good true story (recent, concrete):**

**Billing “404 / not in inventory” while the stock badge showed the medicine.**

- Sell API returned **404 for “medicine not found”** (exact name match) — browser looked like a missing route.
- UI stock check was **case-insensitive**; sell was **exact case**.
- Later, a client guard only trusted **`/inventory/all`**, while the badge used the **paginated list** — false “Not in inventory: Aspirin.”
- Alternatives “Use” didn’t always bind **medicine_id**.

**Fix:** case-insensitive + id-based sell; alternatives return `medicine_id`; Charge resolves from **on-screen inventory first**, then merges catalogs; missing-med errors are **400** with a clear message.

**Design lesson:** don’t overload HTTP 404 for business “not found”; one source of truth for “what the UI already proved is in stock”; prefer stable ids over display strings at the boundary.

**Other strong design call:** SQL commit first, embeddings **best-effort background** — stock accuracy beats search freshness; repair via reindex.

---

## 5. Demo script (if they ask for a live walkthrough)

1. Login as pharmacist → add medicine → note background index.  
2. Login as cashier → Billing → sell in-stock item → PDF.  
3. Type missing/low name → Find alternatives → Use → Charge.  
4. OCR upload → edit lines → sell.  
5. Chat: “What’s low stock?” → show SQL transparency.  
6. Admin: audit shows `inventory.sell`.

---

## 6. Closing lines

**Strengths:** end-to-end staff workflow, clear layering, Postgres vectors, human-in-the-loop OCR, transactional sell, roles/audit, deployable on Render.

**If I had more time:** confirm-before-act agent writes, eval set for OCR+search, tenancy, embed worker queue, stronger Rx validation (dose/form), HTML invoice templates.

**Point them at:** [architecture.md](architecture.md), [vector-search.md](vector-search.md), [auth.md](auth.md), OpenAPI `/docs`.
