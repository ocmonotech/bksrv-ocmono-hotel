"""Tests for outlet-scoped PMS tax / checkout settings."""


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_pms_tax_settings_defaults(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    response = client.get("/api/v1/settings/pms-tax", headers=headers, params={"outlet_id": outlet_id})
    assert response.status_code == 200
    body = response.json()
    assert body["outlet_id"] == outlet_id
    assert body["tax_percent"] == 12.0
    assert body["tax_label"] == "GST"
    assert body["require_zero_balance_checkout"] is False


def test_pms_tax_settings_update_and_persist(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    patch = client.patch(
        "/api/v1/settings/pms-tax",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "tax_percent": 18.0,
            "tax_label": "IGST",
            "require_zero_balance_checkout": True,
        },
    )
    assert patch.status_code == 200
    assert patch.json()["tax_percent"] == 18.0
    assert patch.json()["tax_label"] == "IGST"
    assert patch.json()["require_zero_balance_checkout"] is True

    reload = client.get("/api/v1/settings/pms-tax", headers=headers, params={"outlet_id": outlet_id})
    assert reload.status_code == 200
    assert reload.json()["tax_percent"] == 18.0
    assert reload.json()["tax_label"] == "IGST"
    assert reload.json()["require_zero_balance_checkout"] is True
