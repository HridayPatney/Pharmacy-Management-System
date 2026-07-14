"""Tests for void sale, expiry filters, and audit filters."""

from __future__ import annotations

from datetime import date, timedelta


def test_void_sale_restores_stock_and_updates_summary(
    client, sample_medicine_payload, pharmacist_headers
):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": sample_medicine_payload["name"], "quantity": 2}]},
        headers=pharmacist_headers,
    )
    assert sold.status_code == 200
    sale_id = sold.json()["invoice"]["sale_id"]

    listed = client.get("/inventory/?q=" + sample_medicine_payload["name"], headers=pharmacist_headers)
    qty_after_sell = listed.json()["items"][0]["quantity"]

    voided = client.post(f"/sales/{sale_id}/void", headers=pharmacist_headers)
    assert voided.status_code == 200
    assert voided.json()["status"] == "cancelled"

    listed2 = client.get("/inventory/?q=" + sample_medicine_payload["name"], headers=pharmacist_headers)
    assert listed2.json()["items"][0]["quantity"] == qty_after_sell + 2

    summary = client.get("/sales/summary", headers=pharmacist_headers)
    assert summary.status_code == 200
    # Cancelled sales must not inflate completed revenue.
    assert summary.json()["sale_count"] == 0

    again = client.post(f"/sales/{sale_id}/void", headers=pharmacist_headers)
    assert again.status_code == 409


def test_expiry_filters(client, pharmacist_headers, sample_medicine_payload):
    today = date.today()
    expired = {
        **sample_medicine_payload,
        "id": "exp-1",
        "name": "ExpiredMed",
        "expiry_date": (today - timedelta(days=5)).isoformat(),
    }
    soon = {
        **sample_medicine_payload,
        "id": "soon-1",
        "name": "SoonMed",
        "expiry_date": (today + timedelta(days=10)).isoformat(),
    }
    later = {
        **sample_medicine_payload,
        "id": "ok-1",
        "name": "LaterMed",
        "expiry_date": (today + timedelta(days=120)).isoformat(),
    }
    for med in (expired, soon, later):
        assert client.post("/inventory/add", json=med, headers=pharmacist_headers).status_code == 200

    exp = client.get("/inventory/?expiry=expired", headers=pharmacist_headers)
    assert exp.status_code == 200
    assert any(i["name"] == "ExpiredMed" for i in exp.json()["items"])
    assert all(i["name"] != "LaterMed" for i in exp.json()["items"])

    soon_res = client.get("/inventory/?expiry=soon&days=30", headers=pharmacist_headers)
    assert soon_res.status_code == 200
    names = {i["name"] for i in soon_res.json()["items"]}
    assert "SoonMed" in names
    assert "ExpiredMed" not in names


def test_audit_filters_by_action(client, sample_medicine_payload, pharmacist_headers, admin_headers):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    client.post(
        "/inventory/sell",
        json={"medicines": [{"name": sample_medicine_payload["name"], "quantity": 1}]},
        headers=pharmacist_headers,
    )
    rows = client.get("/auth/audit?action=inventory.sell", headers=admin_headers)
    assert rows.status_code == 200
    assert len(rows.json()) >= 1
    assert all(r["action"] == "inventory.sell" for r in rows.json())
    assert rows.json()[0].get("user_email")
