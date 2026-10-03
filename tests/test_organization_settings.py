def test_me_includes_business_type(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert login.status_code == 200
    token = login.json()["access_token"]

    response = client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["business_type"] == "resort"


def test_organization_settings_read_and_update(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    token = login.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    read_response = client.get("/api/v1/settings/organization", headers=headers)
    assert read_response.status_code == 200
    assert read_response.json()["business_type"] == "resort"

    patch_response = client.patch(
        "/api/v1/settings/organization",
        headers=headers,
        json={"business_type": "multichain"},
    )
    assert patch_response.status_code == 200
    assert patch_response.json()["business_type"] == "multichain"

    me_response = client.get("/api/v1/auth/me", headers=headers)
    assert me_response.json()["business_type"] == "multichain"
