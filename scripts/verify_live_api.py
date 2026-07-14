"""Hit live API endpoints end-to-end (auth → inventory → OCR stub path checks).

Uses ``.env`` bootstrap admin + ``API_BASE`` (default http://127.0.0.1:8001).
Does not print secrets.

  python scripts/verify_live_api.py
"""

from __future__ import annotations

import json
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

API = os.getenv("API_BASE", "http://127.0.0.1:8001").rstrip("/")


def call(method: str, path: str, *, token: str | None = None, body: dict | None = None):
    data = None if body is None else json.dumps(body).encode()
    headers = {"Content-Type": "application/json"}
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{API}{path}", data=data, headers=headers, method=method)
    try:
        with urlopen(req, timeout=120) as res:
            raw = res.read().decode() or "{}"
            return res.status, json.loads(raw) if raw.strip() else {}
    except HTTPError as exc:
        raw = exc.read().decode()
        try:
            parsed = json.loads(raw) if raw else {}
        except json.JSONDecodeError:
            parsed = {"raw": raw}
        return exc.code, parsed


def main() -> int:
    email = os.getenv("BOOTSTRAP_ADMIN_EMAIL", "").strip()
    password = os.getenv("BOOTSTRAP_ADMIN_PASSWORD", "").strip()
    if not email or not password:
        print("FAIL: BOOTSTRAP_ADMIN_EMAIL/PASSWORD missing in .env")
        return 1

    print(f"API_BASE={API}")

    status, body = call("GET", "/health/live")
    print(f"GET /health/live -> {status} {body}")
    if status != 200:
        return 1

    status, body = call("GET", "/health/ready")
    print(f"GET /health/ready -> {status} status={body.get('status')} checks={body.get('checks')}")
    if status != 200 or body.get("checks", {}).get("chroma", {}).get("status") != "ok":
        print("FAIL: chroma not ready (install ML deps / restart API)")
        return 1

    status, body = call("POST", "/auth/login", body={"email": email, "password": password})
    print(f"POST /auth/login -> {status}")
    if status != 200 or "access_token" not in body:
        print("FAIL: login", body)
        return 1
    token = body["access_token"]

    med_id = f"live-{date.today().isoformat()}"
    payload = {
        "id": med_id,
        "name": "Paracetamol",
        "dosage": "500mg",
        "quantity": 25,
        "price": 3.5,
        "expiry_date": (date.today() + timedelta(days=400)).isoformat(),
    }

    # Clean previous run if present
    call("DELETE", f"/inventory/delete/{med_id}", token=token)

    status, body = call("POST", "/inventory/add", token=token, body=payload)
    print(f"POST /inventory/add -> {status}")
    if status != 200:
        print("FAIL: add", body)
        return 1

    status, body = call("GET", "/inventory/?q=Paracetamol&limit=5", token=token)
    print(f"GET /inventory/ -> {status} total={body.get('total')}")
    if status != 200 or body.get("total", 0) < 1:
        print("FAIL: list", body)
        return 1

    status, body = call(
        "POST",
        "/search/similar",
        token=token,
        body={"medicine_name": "Paracetamol", "top_k": 3},
    )
    print(f"POST /search/similar -> {status} results={len(body) if isinstance(body, list) else body}")
    if status != 200:
        print("FAIL: search", body)
        return 1

    status, body = call(
        "POST",
        "/inventory/sell",
        token=token,
        body={"medicines": [{"name": "Paracetamol", "quantity": 1}]},
    )
    print(f"POST /inventory/sell -> {status} total={body.get('invoice', {}).get('total')}")
    if status != 200:
        print("FAIL: sell", body)
        return 1

    status, body = call("DELETE", f"/inventory/delete/{med_id}", token=token)
    print(f"DELETE /inventory/delete -> {status}")
    if status != 200:
        print("FAIL: delete", body)
        return 1

    print("LIVE_API: OK")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
