"""API tests for persisted sales history and summary."""

from __future__ import annotations


def test_sell_persists_sale_and_summary(
    client, sample_medicine_payload, pharmacist_headers
):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)

    sold = client.post(
        "/inventory/sell",
        json={
            "medicines": [{"name": sample_medicine_payload["name"], "quantity": 2}],
            "patient": "Ada",
            "doctor": "Dr Who",
            "clinic": "Clinic A",
        },
        headers=pharmacist_headers,
    )
    assert sold.status_code == 200
    invoice = sold.json()["invoice"]
    assert invoice["sale_id"] is not None
    assert invoice["total"] == 11.0

    detail = client.get(f"/sales/{invoice['sale_id']}", headers=pharmacist_headers)
    assert detail.status_code == 200
    body = detail.json()
    assert body["patient_name"] == "Ada"
    assert body["doctor_name"] == "Dr Who"
    assert len(body["items"]) == 1
    assert body["items"][0]["medicine_name"] == sample_medicine_payload["name"]

    listed = client.get("/sales/?page=1&limit=10", headers=pharmacist_headers)
    assert listed.status_code == 200
    assert listed.json()["total"] >= 1
    assert listed.json()["items"][0]["id"] == invoice["sale_id"]

    summary = client.get("/sales/summary", headers=pharmacist_headers)
    assert summary.status_code == 200
    data = summary.json()
    assert data["sale_count"] >= 1
    assert data["total_revenue"] >= 11.0
    assert data["today_sale_count"] >= 1
    assert data["today_revenue"] >= 11.0


def test_sales_require_auth(client):
    assert client.get("/sales/summary").status_code == 401
    assert client.get("/sales/").status_code == 401
