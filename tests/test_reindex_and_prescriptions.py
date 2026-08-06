"""Tests for embedding reindex endpoint."""

from __future__ import annotations

from datetime import date, timedelta


def test_reindex_queues_embeddings_for_all_medicines(
    client, pharmacist_headers, cashier_headers, vector_mocks, sample_medicine_payload
):
    base = {
        "dosage": "10mg",
        "price": 4.0,
        "expiry_date": (date.today() + timedelta(days=200)).isoformat(),
    }
    client.post(
        "/inventory/add",
        json={"id": "r1", "name": "MedA", "quantity": 3, **base},
        headers=pharmacist_headers,
    )
    client.post(
        "/inventory/add",
        json={"id": "r2", "name": "MedB", "quantity": 5, **base},
        headers=pharmacist_headers,
    )
    vector_mocks.add_medicine_to_vector_db.reset_mock()

    denied = client.post("/search/reindex", headers=cashier_headers)
    assert denied.status_code == 403

    res = client.post("/search/reindex", headers=pharmacist_headers)
    assert res.status_code == 200
    assert res.json()["scheduled"] == 2
    assert vector_mocks.add_medicine_to_vector_db.call_count == 2
