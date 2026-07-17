"""Tests for inventory-filtered similar-medicine search."""

from __future__ import annotations

from datetime import date, timedelta


def test_similar_excludes_self_and_requires_stock(
    client, pharmacist_headers, cashier_headers, vector_mocks
):
    today = date.today()
    base = {
        "dosage": "10mg",
        "price": 4.0,
        "expiry_date": (today + timedelta(days=200)).isoformat(),
    }
    assert (
        client.post(
            "/inventory/add",
            json={"id": "lip-1", "name": "Lipitor", "quantity": 5, **base},
            headers=pharmacist_headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/inventory/add",
            json={"id": "ato-1", "name": "Atorvastatin", "quantity": 12, **base},
            headers=pharmacist_headers,
        ).status_code
        == 200
    )
    assert (
        client.post(
            "/inventory/add",
            json={"id": "out-1", "name": "Simvastatin", "quantity": 0, **base},
            headers=pharmacist_headers,
        ).status_code
        == 200
    )

    vector_mocks.search_similar_medicines.return_value = [
        {"name": "Lipitor", "score": 0.01},
        {"name": "Simvastatin", "score": 0.1},
        {"name": "Atorvastatin", "score": 0.15},
    ]

    res = client.post(
        "/search/similar",
        json={"medicine_name": "Liptor", "top_k": 5},
        headers=cashier_headers,
    )
    assert res.status_code == 200
    body = res.json()
    names = [r["name"] for r in body]
    assert "Lipitor" not in names  # typo-close to query / same brand
    assert "Simvastatin" not in names  # zero stock
    assert names == ["Atorvastatin"]
    assert body[0]["quantity"] == 12


def test_similar_falls_back_when_drug_summary_missing(
    client, pharmacist_headers, vector_mocks, monkeypatch
):
    today = date.today()
    base = {
        "dosage": "10mg",
        "price": 4.0,
        "expiry_date": (today + timedelta(days=200)).isoformat(),
    }
    client.post(
        "/inventory/add",
        json={"id": "ato-2", "name": "Atorvastatin", "quantity": 8, **base},
        headers=pharmacist_headers,
    )
    monkeypatch.setattr(
        "backend.api.search.fetch_drug_summary",
        lambda _name: "No data found.",
    )
    vector_mocks.search_similar_medicines.return_value = [
        {"name": "Atorvastatin", "score": 0.2},
    ]

    res = client.post(
        "/search/similar",
        json={"medicine_name": "Lipitor", "top_k": 5},
        headers=pharmacist_headers,
    )
    assert res.status_code == 200
    assert res.json()[0]["name"] == "Atorvastatin"
