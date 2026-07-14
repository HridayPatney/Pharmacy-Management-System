"""API tests for inventory CRUD, sell integrity, and Chroma sync failures."""

from __future__ import annotations


def test_health(client):
    response = client.get("/")
    assert response.status_code == 200
    assert response.json()["message"] == "PharmaAssist API is running."


def test_inventory_requires_auth(client, sample_medicine_payload):
    assert client.get("/inventory/all").status_code == 401
    assert client.post("/inventory/add", json=sample_medicine_payload).status_code == 401


def test_add_list_delete(client, sample_medicine_payload, vector_mocks, pharmacist_headers):
    assert client.get("/inventory/all", headers=pharmacist_headers).json() == []

    added = client.post(
        "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
    )
    assert added.status_code == 200
    assert added.json()["name"] == "Aspirin"
    vector_mocks.add_medicine_to_vector_db.assert_called_once()

    assert len(client.get("/inventory/all", headers=pharmacist_headers).json()) == 1

    deleted = client.delete("/inventory/delete/med-1", headers=pharmacist_headers)
    assert deleted.status_code == 200
    vector_mocks.delete_medicine_from_vector_db.assert_called_once_with("med-1")
    assert client.get("/inventory/all", headers=pharmacist_headers).json() == []


def test_sell_invoice_shape(client, sample_medicine_payload, pharmacist_headers):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)

    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 2}]},
        headers=pharmacist_headers,
    )
    assert sold.status_code == 200
    invoice = sold.json()["invoice"]
    assert invoice["total"] == 11.0
    assert len(invoice["items"]) == 1
    assert invoice["items"][0]["unit_price"] == 5.5
    assert "timestamp" in invoice

    remaining = client.get("/inventory/all", headers=pharmacist_headers).json()[0]["quantity"]
    assert remaining == 18


def test_sell_strips_name_whitespace(client, sample_medicine_payload, pharmacist_headers):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "  Aspirin  ", "quantity": 1}]},
        headers=pharmacist_headers,
    )
    assert sold.status_code == 200


def test_sell_rolls_back_when_second_item_missing(
    client, sample_medicine_payload, pharmacist_headers
):
    """Multi-item sell must not commit the first line if a later line fails."""
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)

    failed = client.post(
        "/inventory/sell",
        json={
            "medicines": [
                {"name": "Aspirin", "quantity": 2},
                {"name": "DoesNotExist", "quantity": 1},
            ]
        },
        headers=pharmacist_headers,
    )
    assert failed.status_code == 404

    remaining = client.get("/inventory/all", headers=pharmacist_headers).json()[0]["quantity"]
    assert remaining == 20


def test_sell_rolls_back_when_insufficient_stock(
    client, sample_medicine_payload, pharmacist_headers
):
    other = {
        **sample_medicine_payload,
        "id": "med-2",
        "name": "Ibuprofen",
        "quantity": 5,
    }
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    client.post("/inventory/add", json=other, headers=pharmacist_headers)

    failed = client.post(
        "/inventory/sell",
        json={
            "medicines": [
                {"name": "Aspirin", "quantity": 3},
                {"name": "Ibuprofen", "quantity": 99},
            ]
        },
        headers=pharmacist_headers,
    )
    assert failed.status_code == 400

    by_name = {
        m["name"]: m["quantity"]
        for m in client.get("/inventory/all", headers=pharmacist_headers).json()
    }
    assert by_name["Aspirin"] == 20
    assert by_name["Ibuprofen"] == 5


def test_low_stock(client, sample_medicine_payload, pharmacist_headers):
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    low = client.get("/inventory/low-stock?threshold=25", headers=pharmacist_headers)
    assert low.status_code == 200
    assert len(low.json()) == 1


def test_add_returns_503_when_chroma_sync_fails_but_row_persists(
    client, sample_medicine_payload, vector_mocks, pharmacist_headers
):
    vector_mocks.add_medicine_to_vector_db.side_effect = RuntimeError("chroma down")

    response = client.post(
        "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
    )
    assert response.status_code == 503
    assert "vector index" in response.json()["error"]["message"].lower()

    rows = client.get("/inventory/all", headers=pharmacist_headers).json()
    assert len(rows) == 1
    assert rows[0]["id"] == "med-1"
