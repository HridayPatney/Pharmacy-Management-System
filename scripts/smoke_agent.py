"""Smoke POST /agent/query against a local API (keyword or Gemini planning)."""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
load_dotenv(ROOT / ".env")

API = os.getenv("API_URL", "http://127.0.0.1:8001").rstrip("/")
EMAIL = os.getenv("SMOKE_EMAIL") or os.getenv("BOOTSTRAP_ADMIN_EMAIL") or "admin@example.com"
PASSWORD = os.getenv("SMOKE_PASSWORD") or os.getenv("BOOTSTRAP_ADMIN_PASSWORD") or ""


def main() -> int:
    if not PASSWORD:
        print("FAIL: set BOOTSTRAP_ADMIN_PASSWORD or SMOKE_PASSWORD")
        return 1

    login = requests.post(
        f"{API}/auth/login",
        json={"email": EMAIL, "password": PASSWORD},
        timeout=30,
    )
    if login.status_code != 200:
        print(f"FAIL login {login.status_code}: {login.text[:300]}")
        return 1
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    questions = [
        "What's low stock?",
        "Which medicines are expired?",
        "What's expiring this month?",
        "Give an inventory overview",
    ]
    for q in questions:
        res = requests.post(
            f"{API}/agent/query",
            headers=headers,
            json={"question": q},
            timeout=60,
        )
        print(f"\n=== {q} ===")
        print(f"status={res.status_code}")
        if res.status_code != 200:
            print(res.text[:500])
            return 1
        body = res.json()
        print(f"tool={body.get('tool')} mode={body.get('mode')} rows={body.get('row_count')}")
        if body.get("sql"):
            print(f"sql={body['sql']}")
        answer = body.get("answer", "")
        print(answer[:800].encode("ascii", errors="replace").decode("ascii"))
    print("\nOK")
    return 0


if __name__ == "__main__":
    sys.exit(main())
