"""Health, error envelope, pagination, storage, and end-to-end API contract tests."""

from __future__ import annotations

from datetime import date, timedelta
from io import BytesIO
from pathlib import Path


def test_health_live(client):
    response = client.get("/health/live")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_health_ready_db_ok(client):
    response = client.get("/health/ready")
    assert response.status_code == 200
    body = response.json()
    assert body["status"] in ("ok", "degraded")
    assert body["checks"]["db"]["status"] == "ok"
    assert "chroma" in body["checks"]


def test_error_envelope_on_unauthorized(client):
    response = client.get("/inventory/all")
    assert response.status_code == 401
    err = response.json()["error"]
    assert err["code"] == "UNAUTHORIZED"
    assert "message" in err


def test_error_envelope_on_validation(client, pharmacist_headers):
    response = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 0}]},
        headers=pharmacist_headers,
    )
    assert response.status_code == 422
    err = response.json()["error"]
    assert err["code"] == "VALIDATION_ERROR"
    assert err["details"]


def test_inventory_pagination_filter_sort(
    client, pharmacist_headers, sample_medicine_payload
):
    other = {
        **sample_medicine_payload,
        "id": "med-2",
        "name": "Ibuprofen",
        "quantity": 3,
        "expiry_date": (date.today() + timedelta(days=30)).isoformat(),
    }
    client.post("/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers)
    client.post("/inventory/add", json=other, headers=pharmacist_headers)

    page1 = client.get(
        "/inventory/?page=1&limit=1&sort=name&order=asc",
        headers=pharmacist_headers,
    )
    assert page1.status_code == 200
    body = page1.json()
    assert body["total"] == 2
    assert body["page"] == 1
    assert body["limit"] == 1
    assert len(body["items"]) == 1

    low = client.get("/inventory/?low_stock=5", headers=pharmacist_headers)
    assert low.status_code == 200
    assert low.json()["total"] == 1
    assert low.json()["items"][0]["name"] == "Ibuprofen"

    search = client.get("/inventory/?q=asp", headers=pharmacist_headers)
    assert search.status_code == 200
    assert search.json()["total"] == 1
    assert search.json()["items"][0]["name"] == "Aspirin"


def test_ocr_stores_file_and_returns_file_key(client, cashier_headers, tmp_path, monkeypatch):
    upload_root = tmp_path / "uploads"
    monkeypatch.setenv("STORAGE_BACKEND", "local")
    monkeypatch.setenv("UPLOAD_DIR", str(upload_root))

    response = client.post(
        "/ocr/extract",
        files={"file": ("rx.png", BytesIO(b"fake-image-bytes"), "image/png")},
        headers=cashier_headers,
    )
    assert response.status_code == 200
    data = response.json()
    assert data["Patient's Name"] == "Test"
    assert "file_key" in data
    assert data["file_key"].startswith("prescriptions/")
    stored = upload_root / data["file_key"]
    assert stored.exists()
    assert stored.read_bytes() == b"fake-image-bytes"


def test_full_api_contract(client, admin_headers, pharmacist_headers, cashier_headers, sample_medicine_payload):
    """Exercise every public product route once with correct auth."""
    assert client.get("/").status_code == 200
    assert client.get("/health/live").status_code == 200
    assert client.get("/health/ready").status_code == 200

    me = client.get("/auth/me", headers=admin_headers)
    assert me.status_code == 200

    reg = client.post(
        "/auth/register",
        json={"email": "extra@test.com", "password": "extrapass1", "role": "cashier"},
        headers=admin_headers,
    )
    assert reg.status_code == 201

    assert (
        client.post(
            "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
        ).status_code
        == 200
    )
    assert client.get("/inventory/all", headers=cashier_headers).status_code == 200
    assert client.get("/inventory/?page=1&limit=10", headers=cashier_headers).status_code == 200
    assert client.get("/inventory/low-stock?threshold=50", headers=cashier_headers).status_code == 200

    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 1}]},
        headers=cashier_headers,
    )
    assert sold.status_code == 200
    assert "invoice" in sold.json()

    search = client.post(
        "/search/similar",
        json={"medicine_name": "Aspirin", "top_k": 3},
        headers=cashier_headers,
    )
    assert search.status_code == 200

    ocr = client.post(
        "/ocr/extract",
        files={"file": ("rx.png", BytesIO(b"x"), "image/png")},
        headers=cashier_headers,
    )
    assert ocr.status_code == 200
    assert "file_key" in ocr.json()

    updated = {
        **sample_medicine_payload,
        "quantity": 50,
    }
    assert (
        client.put(
            "/inventory/update/med-1", json=updated, headers=pharmacist_headers
        ).status_code
        == 200
    )

    assert client.delete("/inventory/delete/med-1", headers=pharmacist_headers).status_code == 200
    audit = client.get("/auth/audit", headers=admin_headers)
    assert audit.status_code == 200
    assert len(audit.json()) >= 1
