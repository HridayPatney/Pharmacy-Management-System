"""Auth, roles, and audit coverage."""

from __future__ import annotations

from io import BytesIO


def test_login_and_me(client, admin_headers):
    me = client.get("/auth/me", headers=admin_headers)
    assert me.status_code == 200
    assert me.json()["email"] == "admin@test.com"
    assert me.json()["role"] == "admin"


def test_bad_login(client, admin_headers):
    # admin_headers ensures user exists
    bad = client.post(
        "/auth/login",
        json={"email": "admin@test.com", "password": "wrong-password"},
    )
    assert bad.status_code == 401


def test_cashier_cannot_add_or_delete(
    client, sample_medicine_payload, pharmacist_headers, cashier_headers
):
    assert (
        client.post(
            "/inventory/add", json=sample_medicine_payload, headers=cashier_headers
        ).status_code
        == 403
    )

    client.post(
        "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
    )
    assert (
        client.delete("/inventory/delete/med-1", headers=cashier_headers).status_code
        == 403
    )


def test_cashier_can_sell_and_read(
    client, sample_medicine_payload, pharmacist_headers, cashier_headers
):
    client.post(
        "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
    )
    listed = client.get("/inventory/all", headers=cashier_headers)
    assert listed.status_code == 200
    assert len(listed.json()) == 1

    sold = client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 1}]},
        headers=cashier_headers,
    )
    assert sold.status_code == 200


def test_sell_and_delete_write_audit(
    client, sample_medicine_payload, pharmacist_headers, admin_headers
):
    client.post(
        "/inventory/add", json=sample_medicine_payload, headers=pharmacist_headers
    )
    client.post(
        "/inventory/sell",
        json={"medicines": [{"name": "Aspirin", "quantity": 1}]},
        headers=pharmacist_headers,
    )
    client.delete("/inventory/delete/med-1", headers=pharmacist_headers)

    audit = client.get("/auth/audit", headers=admin_headers)
    assert audit.status_code == 200
    actions = {row["action"] for row in audit.json()}
    assert "inventory.sell" in actions
    assert "medicine.delete" in actions


def test_cashier_cannot_list_audit(client, cashier_headers):
    assert client.get("/auth/audit", headers=cashier_headers).status_code == 403


def test_admin_can_register_pharmacist(client, admin_headers):
    created = client.post(
        "/auth/register",
        json={
            "email": "newpharm@test.com",
            "password": "newpharm99",
            "role": "pharmacist",
        },
        headers=admin_headers,
    )
    assert created.status_code == 201
    assert created.json()["role"] == "pharmacist"

    listed = client.get("/auth/users", headers=admin_headers)
    assert listed.status_code == 200
    emails = {row["email"] for row in listed.json()}
    assert "newpharm@test.com" in emails

    audit = client.get("/auth/audit?action=auth.user.register", headers=admin_headers)
    assert audit.status_code == 200
    assert any(row["action"] == "auth.user.register" for row in audit.json())


def test_cashier_cannot_list_or_register_users(client, cashier_headers):
    assert client.get("/auth/users", headers=cashier_headers).status_code == 403
    assert (
        client.post(
            "/auth/register",
            json={"email": "x@test.com", "password": "password12", "role": "cashier"},
            headers=cashier_headers,
        ).status_code
        == 403
    )


def test_admin_can_update_user_role_and_active(client, admin_headers, cashier_headers):
    me = client.get("/auth/me", headers=cashier_headers).json()
    user_id = me["id"]

    updated = client.patch(
        f"/auth/users/{user_id}",
        json={"role": "pharmacist"},
        headers=admin_headers,
    )
    assert updated.status_code == 200
    assert updated.json()["role"] == "pharmacist"

    deactivated = client.patch(
        f"/auth/users/{user_id}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert deactivated.status_code == 200
    assert deactivated.json()["is_active"] is False

    assert (
        client.post(
            "/auth/login",
            json={"email": me["email"], "password": "cashpass1"},
        ).status_code
        == 401
    )


def test_cannot_deactivate_self_or_last_admin(client, admin_headers):
    admin = client.get("/auth/me", headers=admin_headers).json()
    assert (
        client.patch(
            f"/auth/users/{admin['id']}",
            json={"is_active": False},
            headers=admin_headers,
        ).status_code
        == 400
    )
    assert (
        client.patch(
            f"/auth/users/{admin['id']}",
            json={"role": "cashier"},
            headers=admin_headers,
        ).status_code
        == 400
    )


def test_ocr_requires_auth(client):
    assert (
        client.post(
            "/ocr/extract",
            files={"file": ("rx.png", BytesIO(b"x"), "image/png")},
        ).status_code
        == 401
    )


def test_ocr_works_for_cashier(client, cashier_headers):
    response = client.post(
        "/ocr/extract",
        files={"file": ("rx.png", BytesIO(b"fake"), "image/png")},
        headers=cashier_headers,
    )
    assert response.status_code == 200
    assert response.json()["Patient's Name"] == "Test"
