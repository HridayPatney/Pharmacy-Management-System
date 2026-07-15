"""Tests for inventory NL agent (SQL guard + tool fallback + HTTP)."""

from __future__ import annotations

from datetime import date, timedelta

import pytest

from backend.services.inventory_agent import keyword_plan, validate_and_prepare_sql


def test_sql_guard_allows_select():
    sql = validate_and_prepare_sql(
        "SELECT name, quantity FROM medicines WHERE quantity <= 10 ORDER BY quantity"
    )
    assert sql.upper().startswith("SELECT")
    assert "LIMIT 50" in sql.upper()


def test_sql_guard_blocks_writes_and_users():
    with pytest.raises(ValueError):
        validate_and_prepare_sql("DELETE FROM medicines")
    with pytest.raises(ValueError):
        validate_and_prepare_sql("SELECT * FROM users")
    with pytest.raises(ValueError):
        validate_and_prepare_sql("SELECT * FROM medicines; DROP TABLE medicines")


def test_agent_requires_auth(client):
    assert (
        client.post("/agent/query", json={"question": "what's low stock?"}).status_code
        == 401
    )


def test_agent_sql_mode(client, sample_medicine_payload, pharmacist_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.services.inventory_agent.plan_with_gemini",
        lambda q: {
            "mode": "sql",
            "sql": "SELECT name, quantity FROM medicines WHERE quantity <= 10 ORDER BY quantity ASC LIMIT 50",
        },
    )
    low = {**sample_medicine_payload, "id": "low-1", "name": "LowMed", "quantity": 3}
    ok = {**sample_medicine_payload, "id": "ok-1", "name": "PlentyMed", "quantity": 100}
    assert client.post("/inventory/add", json=low, headers=pharmacist_headers).status_code in (
        200,
        201,
    )
    assert client.post("/inventory/add", json=ok, headers=pharmacist_headers).status_code in (
        200,
        201,
    )

    res = client.post(
        "/agent/query",
        json={"question": "what's low stock?"},
        headers=pharmacist_headers,
    )
    assert res.status_code == 200
    body = res.json()
    assert body["mode"] == "sql"
    assert body["tool"] == "nl_sql"
    assert body["sql"] and "medicines" in body["sql"].lower()
    assert body["row_count"] == 1
    assert body["rows"][0]["name"] == "LowMed"


def test_agent_expired_tool_fallback(
    client, sample_medicine_payload, pharmacist_headers, monkeypatch
):
    monkeypatch.setattr(
        "backend.services.inventory_agent.plan_with_gemini",
        lambda q: {"mode": "tool", "tool": "expired", "args": {}},
    )
    expired = {
        **sample_medicine_payload,
        "id": "exp-1",
        "name": "OldPill",
        "expiry_date": (date.today() - timedelta(days=5)).isoformat(),
    }
    client.post("/inventory/add", json=expired, headers=pharmacist_headers)
    res = client.post(
        "/agent/query",
        json={"question": "which medicines are expired?"},
        headers=pharmacist_headers,
    )
    assert res.status_code == 200
    assert res.json()["tool"] == "expired"
    assert res.json()["row_count"] == 1


def test_agent_keyword_fallback_maps_expiring():
    tool, args = keyword_plan("what is expiring this month?")
    assert tool == "expiring_soon"
    assert args.get("days") == 30


def test_agent_help(client, cashier_headers, monkeypatch):
    monkeypatch.setattr(
        "backend.services.inventory_agent.plan_with_gemini",
        lambda q: {"mode": "tool", "tool": "help", "args": {}},
    )
    res = client.post(
        "/agent/query",
        json={"question": "tell me a joke"},
        headers=cashier_headers,
    )
    assert res.status_code == 200
    assert res.json()["tool"] == "help"
