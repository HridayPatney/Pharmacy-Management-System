"""Tests for embedding reindex and prescription storage retrieval."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO


def test_reindex_queues_embeddings_for_all_medicines(
    client, pharmacist_headers, cashier_headers, vector_mocks
):
    today = date.today()
    base = {
        "dosage": "10mg",
        "price": 4.0,
        "expiry_date": (today + timedelta(days=200)).isoformat(),
    }
    for med_id, name in (("a1", "Aspirin"), ("i1", "Ibuprofen")):
        assert (
            client.post(
                "/inventory/add",
                json={"id": med_id, "name": name, "quantity": 5, **base},
                headers=pharmacist_headers,
            ).status_code
            == 200
        )

    vector_mocks.add_medicine_to_vector_db.reset_mock()
    denied = client.post("/search/reindex", headers=cashier_headers)
    assert denied.status_code == 403

    res = client.post("/search/reindex", headers=pharmacist_headers)
    assert res.status_code == 200
    body = res.json()
    assert body["scheduled"] == 2
    assert vector_mocks.add_medicine_to_vector_db.call_count == 2


def test_ocr_prescription_linked_to_sale_and_retrievable(
    client, cashier_headers, pharmacist_headers
):
    today = date.today()
    assert (
        client.post(
            "/inventory/add",
            json={
                "id": "asp-rx",
                "name": "Aspirin",
                "dosage": "100mg",
                "quantity": 20,
                "price": 2.5,
                "expiry_date": (today + timedelta(days=100)).isoformat(),
            },
            headers=pharmacist_headers,
        ).status_code
        == 200
    )

    ocr = client.post(
        "/ocr/extract",
        files={"file": ("rx.png", BytesIO(b"fake-rx-bytes"), "image/png")},
        headers=cashier_headers,
    )
    assert ocr.status_code == 200
    file_key = ocr.json()["file_key"]
    assert file_key.startswith("prescriptions/")

    fetched = client.get(
        "/ocr/prescription",
        params={"key": file_key},
        headers=cashier_headers,
    )
    assert fetched.status_code == 200
    assert fetched.content == b"fake-rx-bytes"
    assert "image" in (fetched.headers.get("content-type") or "")

    sell = client.post(
        "/inventory/sell",
        json={
            "medicines": [{"name": "Aspirin", "quantity": 1}],
            "patient": "Pat",
            "prescription_file_key": file_key,
        },
        headers=cashier_headers,
    )
    assert sell.status_code == 200
    sale_id = sell.json()["invoice"]["sale_id"]

    detail = client.get(f"/sales/{sale_id}", headers=cashier_headers)
    assert detail.status_code == 200
    assert detail.json()["prescription_file_key"] == file_key

    bad = client.get(
        "/ocr/prescription",
        params={"key": "../secrets.txt"},
        headers=cashier_headers,
    )
    assert bad.status_code == 400
