"""Inventory NL agent: guarded NL→SQL with tool fallback.

Architecture follows the common NL-to-SQL evolution (tool agent → few-shot SQL
agent with safety gates). We never run freeform DML; only validated SELECT /
WITH queries against an allowlisted schema, with a hard row limit. If SQL
planning or validation fails, we fall back to structured ORM tools.
"""

from __future__ import annotations

import json
import os
import re
from datetime import date, datetime, timedelta
from typing import Any

from sqlalchemy import func, text
from sqlalchemy.orm import Session

from backend.db import models

ALLOWED_TOOLS = frozenset(
    {
        "low_stock",
        "expired",
        "expiring_soon",
        "search_medicines",
        "sales_summary",
        "inventory_overview",
        "help",
    }
)

ALLOWED_TABLES = frozenset({"medicines", "sales", "sale_items"})

_FORBIDDEN_SQL = re.compile(
    r"\b("
    r"insert|update|delete|drop|alter|create|truncate|replace|attach|detach|"
    r"pragma|grant|revoke|exec|execute|call|merge|copy|load|into|vacuum|"
    r"analyze|reindex|trigger|function|procedure|users|audit_logs"
    r")\b",
    re.IGNORECASE,
)

_SCHEMA_CARD = """
Tables (read-only):
1) medicines(id TEXT PK, name TEXT, dosage TEXT, quantity INT, price REAL, expiry_date DATE)
2) sales(id INT PK, user_id INT, patient_name TEXT, doctor_name TEXT, clinic_name TEXT,
         total REAL, status TEXT ['completed'|'cancelled'], cancelled_at DATETIME,
         cancelled_by_user_id INT, created_at DATETIME)
3) sale_items(id INT PK, sale_id INT FK->sales.id, medicine_id TEXT, medicine_name TEXT,
              quantity INT, unit_price REAL, subtotal REAL)

Dialect notes: use CURRENT_DATE for "today". SQLite and Postgres both accept it.
Always add LIMIT <= 50. Prefer ILIKE for name search (SQLite accepts ILIKE via SQLAlchemy).
Never query users or audit_logs.
""".strip()

_PLAN_PROMPT = f"""
You are a pharmacy inventory NL-to-SQL planner.

{_SCHEMA_CARD}

Return ONLY JSON in one of these shapes:
A) SQL mode (preferred for data questions):
{{"mode":"sql","sql":"SELECT ... LIMIT 20","rationale":"short"}}

B) Tool mode (when SQL is awkward or question is meta/help):
{{"mode":"tool","tool":"<name>","args":{{...}}}}

Tools for mode=tool:
- low_stock {{"threshold":10}}
- expired {{}}
- expiring_soon {{"days":30}}
- search_medicines {{"q":"...","limit":20}}
- sales_summary {{}}
- inventory_overview {{}}
- help {{}}

Few-shot examples:
Q: What's low stock?
A: {{"mode":"sql","sql":"SELECT name, quantity, expiry_date FROM medicines WHERE quantity <= 10 ORDER BY quantity ASC LIMIT 50","rationale":"low stock"}}

Q: Which medicines are expired?
A: {{"mode":"sql","sql":"SELECT name, quantity, expiry_date FROM medicines WHERE expiry_date < CURRENT_DATE ORDER BY expiry_date ASC LIMIT 50","rationale":"expired"}}

Q: What's expiring this month?
A: {{"mode":"sql","sql":"SELECT name, quantity, expiry_date FROM medicines WHERE expiry_date >= CURRENT_DATE AND expiry_date <= DATE(CURRENT_DATE, '+30 days') ORDER BY expiry_date ASC LIMIT 50","rationale":"expiring ~30d"}}

Q: Sales revenue today?
A: {{"mode":"sql","sql":"SELECT COUNT(*) AS sale_count, COALESCE(SUM(total),0) AS revenue FROM sales WHERE status = 'completed' AND created_at >= DATE(CURRENT_DATE) LIMIT 1","rationale":"today sales"}}

Q: Find aspirin
A: {{"mode":"sql","sql":"SELECT id, name, dosage, quantity, price, expiry_date FROM medicines WHERE name ILIKE '%aspirin%' ORDER BY name ASC LIMIT 20","rationale":"search"}}

Q: tell me a joke
A: {{"mode":"tool","tool":"help","args":{{}}}}

Rules: SELECT or WITH only. No DML/DDL. Only medicines, sales, sale_items.
""".strip()


def _medicine_row(med: models.Medicine) -> dict[str, Any]:
    return {
        "id": med.id,
        "name": med.name,
        "dosage": med.dosage,
        "quantity": med.quantity,
        "price": med.price,
        "expiry_date": med.expiry_date.isoformat() if med.expiry_date else None,
    }


def execute_tool(
    db: Session, tool: str, args: dict[str, Any] | None = None
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Run a read-only ORM tool. Returns (rows, meta)."""
    args = dict(args or {})
    today = date.today()

    if tool == "low_stock":
        threshold = max(0, min(int(args.get("threshold", 10)), 10_000))
        rows = (
            db.query(models.Medicine)
            .filter(models.Medicine.quantity <= threshold)
            .order_by(models.Medicine.quantity.asc(), models.Medicine.name.asc())
            .limit(50)
            .all()
        )
        return [_medicine_row(m) for m in rows], {"threshold": threshold}

    if tool == "expired":
        rows = (
            db.query(models.Medicine)
            .filter(models.Medicine.expiry_date < today)
            .order_by(models.Medicine.expiry_date.asc())
            .limit(50)
            .all()
        )
        return [_medicine_row(m) for m in rows], {}

    if tool == "expiring_soon":
        days = max(1, min(int(args.get("days", 30)), 365))
        until = today + timedelta(days=days)
        rows = (
            db.query(models.Medicine)
            .filter(models.Medicine.expiry_date >= today, models.Medicine.expiry_date <= until)
            .order_by(models.Medicine.expiry_date.asc())
            .limit(50)
            .all()
        )
        return [_medicine_row(m) for m in rows], {"days": days}

    if tool == "search_medicines":
        q = str(args.get("q", "")).strip()
        limit = max(1, min(int(args.get("limit", 20)), 50))
        if not q:
            return [], {"q": q}
        pattern = f"%{q}%"
        rows = (
            db.query(models.Medicine)
            .filter(
                (models.Medicine.name.ilike(pattern)) | (models.Medicine.id.ilike(pattern))
            )
            .order_by(models.Medicine.name.asc())
            .limit(limit)
            .all()
        )
        return [_medicine_row(m) for m in rows], {"q": q, "limit": limit}

    if tool == "sales_summary":
        completed = models.Sale.status == "completed"
        sale_count = db.query(func.count(models.Sale.id)).filter(completed).scalar() or 0
        total_revenue = (
            db.query(func.coalesce(func.sum(models.Sale.total), 0.0)).filter(completed).scalar()
            or 0.0
        )
        day_start = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        today_count = (
            db.query(func.count(models.Sale.id))
            .filter(completed, models.Sale.created_at >= day_start)
            .scalar()
            or 0
        )
        today_revenue = (
            db.query(func.coalesce(func.sum(models.Sale.total), 0.0))
            .filter(completed, models.Sale.created_at >= day_start)
            .scalar()
            or 0.0
        )
        return [
            {
                "sale_count": int(sale_count),
                "total_revenue": float(total_revenue),
                "today_sale_count": int(today_count),
                "today_revenue": float(today_revenue),
            }
        ], {}

    if tool == "inventory_overview":
        total = db.query(func.count(models.Medicine.id)).scalar() or 0
        qty_sum = db.query(func.coalesce(func.sum(models.Medicine.quantity), 0)).scalar() or 0
        value = (
            db.query(
                func.coalesce(func.sum(models.Medicine.quantity * models.Medicine.price), 0.0)
            ).scalar()
            or 0.0
        )
        low = (
            db.query(func.count(models.Medicine.id))
            .filter(models.Medicine.quantity <= 10)
            .scalar()
            or 0
        )
        expired = (
            db.query(func.count(models.Medicine.id))
            .filter(models.Medicine.expiry_date < today)
            .scalar()
            or 0
        )
        soon = (
            db.query(func.count(models.Medicine.id))
            .filter(
                models.Medicine.expiry_date >= today,
                models.Medicine.expiry_date <= today + timedelta(days=30),
            )
            .scalar()
            or 0
        )
        return [
            {
                "medicine_count": int(total),
                "total_units": int(qty_sum),
                "inventory_value": float(value),
                "low_stock_count": int(low),
                "expired_count": int(expired),
                "expiring_30d_count": int(soon),
            }
        ], {}

    if tool == "help":
        return [], {}

    raise ValueError(f"Unknown tool: {tool}")


def format_tool_answer(
    tool: str, rows: list[dict[str, Any]], meta: dict[str, Any], question: str
) -> str:
    if tool == "help":
        return (
            "I answer inventory and sales questions with guarded SQL / read-only tools.\n"
            "Try: What's low stock? Which medicines are expired? What's expiring this month?\n"
            "Find aspirin. What's our sales revenue today? Give an inventory overview."
        )
    if tool == "low_stock":
        threshold = meta.get("threshold", 10)
        if not rows:
            return f"No medicines at or below quantity {threshold}."
        lines = [f"Found {len(rows)} medicine(s) with quantity <= {threshold}:"]
        lines.extend(
            f"- {r['name']} — qty {r['quantity']} (expires {r['expiry_date']})" for r in rows[:25]
        )
        return "\n".join(lines)
    if tool == "expired":
        if not rows:
            return "No expired medicines in inventory."
        lines = [f"Found {len(rows)} expired medicine(s):"]
        lines.extend(
            f"- {r['name']} — expired {r['expiry_date']} (qty {r['quantity']})" for r in rows[:25]
        )
        return "\n".join(lines)
    if tool == "expiring_soon":
        days = meta.get("days", 30)
        if not rows:
            return f"No medicines expiring within {days} days."
        lines = [f"Found {len(rows)} medicine(s) expiring within {days} days:"]
        lines.extend(
            f"- {r['name']} — {r['expiry_date']} (qty {r['quantity']})" for r in rows[:25]
        )
        return "\n".join(lines)
    if tool == "search_medicines":
        q = meta.get("q", "")
        if not rows:
            return f'No medicines matched "{q}".'
        lines = [f'Found {len(rows)} match(es) for "{q}":']
        lines.extend(
            f"- {r['name']} — qty {r['quantity']}, price {r['price']}, expires {r['expiry_date']}"
            for r in rows
        )
        return "\n".join(lines)
    if tool == "sales_summary" and rows:
        s = rows[0]
        return (
            "Sales summary (completed only):\n"
            f"- Today: {s['today_sale_count']} sale(s), revenue {s['today_revenue']:.2f}\n"
            f"- All time: {s['sale_count']} sale(s), revenue {s['total_revenue']:.2f}"
        )
    if tool == "inventory_overview" and rows:
        o = rows[0]
        return (
            "Inventory overview:\n"
            f"- {o['medicine_count']} SKUs, {o['total_units']} units on hand\n"
            f"- Stock value ~ {o['inventory_value']:.2f}\n"
            f"- Low stock (<=10): {o['low_stock_count']}\n"
            f"- Expired: {o['expired_count']}\n"
            f"- Expiring in 30 days: {o['expiring_30d_count']}"
        )
    return f"Handled “{question}” with tool `{tool}` ({len(rows)} row(s))."


def format_sql_answer(rows: list[dict[str, Any]], sql: str, question: str) -> str:
    if not rows:
        return f'No rows for “{question}”.\nSQL: {sql}'
    preview = rows[:8]
    cols = list(preview[0].keys())
    lines = [f"Returned {len(rows)} row(s) for “{question}”:"]
    for row in preview:
        bits = ", ".join(f"{k}={row.get(k)}" for k in cols[:6])
        lines.append(f"- {bits}")
    if len(rows) > 8:
        lines.append(f"...and {len(rows) - 8} more.")
    return "\n".join(lines)


def keyword_plan(question: str) -> tuple[str, dict[str, Any]]:
    q = question.lower()
    if re.search(r"\b(help|what can you|how do i)\b", q):
        return "help", {}
    if re.search(r"\b(sale|revenue|billing|turnover)\b", q):
        return "sales_summary", {}
    if re.search(r"\b(overview|summary|how many|stock value|inventory value)\b", q):
        return "inventory_overview", {}
    if re.search(r"\b(expired|past expiry)\b", q) and not re.search(
        r"\b(expiring|soon|within|next)\b", q
    ):
        return "expired", {}
    if re.search(r"\b(expir\w*|soon|this month|within)\b", q):
        days = 30
        m = re.search(r"(\d+)\s*day", q)
        if m:
            days = int(m.group(1))
        elif "week" in q:
            days = 14
        elif "month" in q:
            days = 30
        return "expiring_soon", {"days": days}
    if re.search(r"\b(low\s*stock|running low|out of stock|reorder)\b", q):
        return "low_stock", {"threshold": 10}
    m = re.search(r"\b(?:find|search|look up|where is)\s+(.+)$", q)
    if m:
        return "search_medicines", {"q": m.group(1).strip(" ?."), "limit": 20}
    return "inventory_overview", {}


def _normalize_sql_dates(sql: str) -> str:
    """Rewrite Postgres-ish date arithmetic that breaks on SQLite few-shots."""
    # DATE(CURRENT_DATE, '+30 days') is SQLite; leave it.
    # INTERVAL '30 days' → SQLite date modifier if present
    sql = re.sub(
        r"CURRENT_DATE\s*\+\s*INTERVAL\s+'(\d+)\s+days?'",
        r"DATE(CURRENT_DATE, '+\1 days')",
        sql,
        flags=re.IGNORECASE,
    )
    return sql


def validate_and_prepare_sql(sql: str) -> str:
    """Allow only single-statement SELECT/WITH over allowlisted tables."""
    cleaned = sql.strip().rstrip(";").strip()
    if not cleaned or len(cleaned) > 2000:
        raise ValueError("SQL empty or too long")
    if ";" in cleaned:
        raise ValueError("Multiple SQL statements are not allowed")
    if _FORBIDDEN_SQL.search(cleaned):
        raise ValueError("SQL contains forbidden keywords or tables")
    head = cleaned.lstrip().split(None, 1)[0].upper()
    if head not in {"SELECT", "WITH"}:
        raise ValueError("Only SELECT/WITH queries are allowed")

    referenced = set(
        t.lower()
        for t in re.findall(r"\b(?:from|join)\s+([a-zA-Z_][\w]*)", cleaned, flags=re.IGNORECASE)
    )
    if not referenced:
        raise ValueError("Could not detect queried tables")
    unknown = referenced - ALLOWED_TABLES
    if unknown:
        raise ValueError(f"Tables not allowed: {sorted(unknown)}")

    cleaned = _normalize_sql_dates(cleaned)
    if not re.search(r"\blimit\s+\d+\b", cleaned, flags=re.IGNORECASE):
        cleaned = f"{cleaned} LIMIT 50"
    else:
        cleaned = re.sub(
            r"\blimit\s+(\d+)\b",
            lambda m: f"LIMIT {min(int(m.group(1)), 50)}",
            cleaned,
            count=1,
            flags=re.IGNORECASE,
        )
    return cleaned


def execute_sql(db: Session, sql: str) -> list[dict[str, Any]]:
    safe = validate_and_prepare_sql(sql)
    bind = db.get_bind()
    dialect = bind.dialect.name if bind is not None else "sqlite"
    if dialect == "sqlite":
        safe = re.sub(r"\bilike\b", "LIKE", safe, flags=re.IGNORECASE)
    elif dialect.startswith("postgres"):
        safe = re.sub(
            r"DATE\(\s*CURRENT_DATE\s*,\s*'\+(\d+)\s+days?'\s*\)",
            r"(CURRENT_DATE + INTERVAL '\1 days')",
            safe,
            flags=re.IGNORECASE,
        )
    result = db.execute(text(safe))
    rows = result.mappings().all()
    out: list[dict[str, Any]] = []
    for row in rows[:50]:
        item: dict[str, Any] = {}
        for k, v in dict(row).items():
            if hasattr(v, "isoformat"):
                item[k] = v.isoformat()
            else:
                item[k] = v
        out.append(item)
    return out


def plan_with_gemini(question: str) -> dict[str, Any]:
    """Ask Gemini for SQL or tool plan; return dict with mode."""
    try:
        from google import genai
        from google.genai import types

        from backend.core.config import get_gemini_api_key

        model = (
            os.getenv("GEMINI_AGENT_MODEL")
            or os.getenv("GEMINI_OCR_MODEL")
            or "gemini-3-flash-preview"
        ).strip() or "gemini-3-flash-preview"

        client = genai.Client(api_key=get_gemini_api_key())
        response = client.models.generate_content(
            model=model,
            contents=question,
            config=types.GenerateContentConfig(
                temperature=0,
                max_output_tokens=512,
                response_mime_type="application/json",
                system_instruction=_PLAN_PROMPT,
            ),
        )
        data = json.loads((response.text or "").strip())
        if not isinstance(data, dict):
            raise ValueError("bad plan")
        mode = str(data.get("mode", "")).strip().lower()
        if mode == "sql" and data.get("sql"):
            return {"mode": "sql", "sql": str(data["sql"]), "rationale": data.get("rationale")}
        tool = str(data.get("tool", "")).strip()
        args = data.get("args") if isinstance(data.get("args"), dict) else {}
        if tool in ALLOWED_TOOLS:
            return {"mode": "tool", "tool": tool, "args": args}
        raise ValueError("unsupported plan")
    except Exception:
        tool, args = keyword_plan(question)
        return {"mode": "tool", "tool": tool, "args": args, "fallback": True}


def answer_question(db: Session, question: str) -> dict[str, Any]:
    """NL → (guarded SQL | tool) → answer. Always read-only."""
    q = question.strip()
    plan = plan_with_gemini(q)

    if plan.get("mode") == "sql":
        try:
            sql = validate_and_prepare_sql(str(plan["sql"]))
            rows = execute_sql(db, sql)
            return {
                "answer": format_sql_answer(rows, sql, q),
                "tool": "nl_sql",
                "args": {"rationale": plan.get("rationale")},
                "sql": sql,
                "mode": "sql",
                "row_count": len(rows),
                "rows": rows[:50],
            }
        except Exception as exc:
            # Soft-fallback to tools (Architecture 1) if SQL path fails.
            tool, args = keyword_plan(q)
            rows, meta = execute_tool(db, tool, args)
            return {
                "answer": format_tool_answer(tool, rows, meta, q)
                + f"\n\n(Note: SQL path skipped — {exc})",
                "tool": tool,
                "args": {**args, **meta},
                "sql": None,
                "mode": "tool",
                "row_count": len(rows),
                "rows": rows[:50],
            }

    tool = str(plan.get("tool") or "help")
    if tool not in ALLOWED_TOOLS:
        tool = "help"
    args = plan.get("args") if isinstance(plan.get("args"), dict) else {}
    rows, meta = execute_tool(db, tool, args)
    return {
        "answer": format_tool_answer(tool, rows, meta, q),
        "tool": tool,
        "args": {**args, **meta},
        "sql": None,
        "mode": "tool",
        "row_count": len(rows),
        "rows": rows[:50],
    }
