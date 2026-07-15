# Inventory chat / NL→SQL agent (staff)

Natural-language questions over inventory and sales.

## Architecture (placement-scale)

Inspired by common NL-to-SQL evolution (tool agent → few-shot SQL agent with gates):

1. **Planner (Gemini)** — returns either guarded SQL or a named tool.
2. **SQL safety gate** — `SELECT`/`WITH` only; allowlisted tables `medicines`, `sales`, `sale_items`; blocks DML/DDL and `users` / `audit_logs`; forces `LIMIT <= 50`.
3. **Execute** — SQLAlchemy `text()` with light dialect adapts (SQLite `LIKE`, Postgres date math).
4. **Tool fallback** — if SQL fails or Gemini is unavailable, keyword/ORM tools answer instead.
5. **Transparency** — response includes `mode`, `sql` (when used), `rows`, and a short answer for the UI.

This is **not** freeform Text-to-SQL against the whole database. Human-in-the-loop for us is “show the SQL to staff” rather than a separate approval step.

## API

`POST /agent/query` (Bearer, any staff role)

```json
{ "question": "What's low stock?" }
```

```json
{
  "answer": "...",
  "mode": "sql",
  "tool": "nl_sql",
  "sql": "SELECT ... LIMIT 50",
  "row_count": 2,
  "rows": [ ... ]
}
```

## UI

React **Chat** page (`/chat`) with suggestion chips.

## Local smoke

```bash
# API on 8002 (example)
set API_URL=http://127.0.0.1:8002
python scripts/smoke_agent.py
```
