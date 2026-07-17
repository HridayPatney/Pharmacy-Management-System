"""Comprehensive live API smoke for local PharmaAssist.

Uses .env bootstrap admin. Does not print secrets.

  set API_BASE=http://127.0.0.1:8004
  python scripts/live_api_smoke.py
"""

from __future__ import annotations

import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API = os.getenv("API_BASE", "http://127.0.0.1:8004").rstrip("/")
FAILS = 0


def call(method: str, path: str, *, token: str | None = None, body: dict | None = None, timeout: int = 120):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as res:
            raw = res.read().decode() or "{}"
            return res.status, json.loads(raw) if raw.strip() else {}
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw[:300]}
        return exc.code, parsed
    except URLError as exc:
        return 0, {"error": str(exc)}


def expect(ok: bool, label: str, detail: object = "") -> None:
    global FAILS
    if ok:
        print(f"OK  {label} {detail}".rstrip())
    else:
        FAILS += 1
        print(f"FAIL {label} {detail}".rstrip())


def main() -> int:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        print("FAIL: BOOTSTRAP_ADMIN_EMAIL/PASSWORD missing in .env")
        return 1

    print(f"API_BASE={API}")

    status, body = call("GET", "/")
    expect(status == 200, "GET /", body)

    status, body = call("GET", "/health/live")
    expect(status == 200 and body.get("status") == "ok", "GET /health/live", body)

    status, body = call("GET", "/health/ready")
    expect(status in (200, 503), "GET /health/ready", f"status={body.get('status')}")

    status, body = call("POST", "/auth/login", body={"email": email, "password": password})
    expect(status == 200 and "access_token" in body, "POST /auth/login")
    if status != 200:
        return 1
    token = body["access_token"]

    status, body = call("GET", "/auth/me", token=token)
    expect(status == 200 and body.get("email"), "GET /auth/me", body.get("role"))

    status, body = call("GET", "/auth/users", token=token)
    expect(status == 200 and isinstance(body, list), "GET /auth/users", f"n={len(body) if isinstance(body, list) else body}")

    status, body = call("GET", "/auth/audit?limit=5", token=token)
    expect(status == 200 and isinstance(body, list), "GET /auth/audit", f"n={len(body) if isinstance(body, list) else body}")

    stamp = date.today().strftime("%Y%m%d%H%M%S")
    med_a = f"live-a-{stamp}"
    med_b = f"live-b-{stamp}"
    # Clean any leftover rows with these names from prior runs.
    status, listed = call("GET", "/inventory/?q=Aspirin&limit=50", token=token)
    if status == 200:
        for row in listed.get("items") or []:
            if row.get("name") in ("Aspirin", "Ibuprofen"):
                call("DELETE", f"/inventory/delete/{row['id']}", token=token)

    for mid in (med_a, med_b):
        call("DELETE", f"/inventory/delete/{mid}", token=token)

    payload_a = {
        "id": med_a,
        "name": "Aspirin",
        "dosage": "100mg",
        "quantity": 40,
        "price": 5.5,
        "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
    }
    payload_b = {
        "id": med_b,
        "name": "Ibuprofen",
        "dosage": "200mg",
        "quantity": 15,
        "price": 7.0,
        "expiry_date": (date.today() + timedelta(days=10)).isoformat(),
    }

    t0 = time.perf_counter()
    status, body = call("POST", "/inventory/add", token=token, body=payload_a, timeout=30)
    elapsed_a = time.perf_counter() - t0
    expect(status == 200 and body.get("id") == med_a, "POST /inventory/add A", f"{elapsed_a:.2f}s")
    # Background vector path should return quickly (< ~8s even with cold chroma;
    # previously often waited on Wikipedia/Gemini). Soft assertion logged.
    if elapsed_a > 8:
        print(f"WARN add A took {elapsed_a:.2f}s (expected faster with background sync)")

    t0 = time.perf_counter()
    status, body = call("POST", "/inventory/add", token=token, body=payload_b, timeout=30)
    elapsed_b = time.perf_counter() - t0
    expect(status == 200 and body.get("id") == med_b, "POST /inventory/add B", f"{elapsed_b:.2f}s")

    status, body = call("GET", f"/inventory/?q={payload_a['name']}&limit=5", token=token)
    expect(status == 200 and body.get("total", 0) >= 1, "GET /inventory/", f"total={body.get('total')}")

    status, body = call("GET", "/inventory/?expiry=soon&days=30&limit=20", token=token)
    expect(status == 200, "GET /inventory/?expiry=soon", f"total={body.get('total')}")

    status, body = call("GET", "/inventory/low-stock?threshold=20", token=token)
    expect(status == 200 and isinstance(body, list), "GET /inventory/low-stock", f"n={len(body) if isinstance(body, list) else body}")

    # Give background embedding time so similar search can use new vectors.
    time.sleep(8)
    status, body = call(
        "POST",
        "/search/similar",
        token=token,
        body={"medicine_name": "Aspirin", "top_k": 5},
        timeout=90,
    )
    expect(status == 200 and isinstance(body, list), "POST /search/similar", f"n={len(body) if isinstance(body, list) else body}")
    if isinstance(body, list) and body:
        print(f"     similar sample: {body[0]}")

    # Alternatives-style: brand not necessarily in inventory
    status, body = call(
        "POST",
        "/search/similar",
        token=token,
        body={"medicine_name": "Lipitor", "top_k": 5},
        timeout=90,
    )
    expect(status == 200 and isinstance(body, list), "POST /search/similar (Lipitor)", f"n={len(body) if isinstance(body, list) else body}")
    if isinstance(body, list):
        names = [r.get("name") for r in body]
        expect("Lipitor" not in names and "lipitor" not in [n.lower() for n in names if n], "similar excludes self/brand self")

    status, body = call(
        "POST",
        "/inventory/sell",
        token=token,
        body={
            "medicines": [{"name": payload_a["name"], "quantity": 2}],
            "patient": "Live Test",
        },
    )
    expect(status == 200 and body.get("invoice", {}).get("sale_id"), "POST /inventory/sell", body.get("invoice", {}).get("sale_id"))
    sale_id = body.get("invoice", {}).get("sale_id") if status == 200 else None

    status, body = call("GET", "/sales/summary", token=token)
    expect(status == 200 and "today_revenue" in body, "GET /sales/summary", body.get("today_sale_count"))

    status, body = call("GET", "/sales/?limit=5", token=token)
    expect(status == 200 and isinstance(body.get("items"), list), "GET /sales/", f"total={body.get('total')}")

    if sale_id:
        status, body = call("GET", f"/sales/{sale_id}", token=token)
        expect(status == 200 and body.get("id") == sale_id, "GET /sales/{id}")

        status, body = call("POST", f"/sales/{sale_id}/void", token=token)
        expect(status == 200 and body.get("status") == "cancelled", "POST /sales/{id}/void")

    status, body = call(
        "POST",
        "/agent/query",
        token=token,
        body={"question": "What's low stock?"},
        timeout=90,
    )
    expect(status == 200 and bool(body.get("answer")), "POST /agent/query", f"mode={body.get('mode')} tool={body.get('tool')}")

    status, body = call(
        "PUT",
        f"/inventory/update/{med_b}",
        token=token,
        body={**payload_b, "quantity": 12},
    )
    expect(status == 200 and body.get("quantity") == 12, "PUT /inventory/update")

    status, body = call("DELETE", f"/inventory/delete/{med_a}", token=token)
    expect(status == 200, "DELETE /inventory/delete A")
    status, body = call("DELETE", f"/inventory/delete/{med_b}", token=token)
    expect(status == 200, "DELETE /inventory/delete B")

    # Auth gate
    status, body = call("GET", "/inventory/")
    expect(status == 401, "GET /inventory/ unauth", status)

    print("---")
    if FAILS:
        print(f"LIVE_API: {FAILS} failure(s)")
        return 1
    print("LIVE_API: ALL OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
