"""Tests for HTTP OTA production adapters."""

from datetime import date, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import httpx


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _andheri_booking_com(client, headers: dict[str, str]) -> dict:
    integrations = client.get("/api/v1/ota/integrations?page=1&page_size=20", headers=headers)
    assert integrations.status_code == 200
    return next(
        row
        for row in integrations.json()["data"]["items"]
        if row["platform"] == "booking_com"
        and (row.get("external_property_id") or "").startswith("BCOM-ANDHERI")
    )


def test_http_adapter_connection_and_ari_push(client):
    headers = _auth_headers(client)

    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]

    patch_response = client.patch(
        f"/api/v1/ota/integrations/{integration_id}",
        headers=headers,
        json={
            "config": {"adapter_mode": "http", "api_base_url": "https://ota.test/v1"},
            "api_key": "test-api-key-12345",
        },
    )
    assert patch_response.status_code == 200

    property_request = httpx.Request("GET", "https://ota.test/v1/properties/test")
    property_response = httpx.Response(
        200,
        json={"property_name": "Test Hotel Andheri", "status": "active"},
        request=property_request,
    )
    ari_request = httpx.Request("POST", "https://ota.test/v1/properties/test/ari")
    ari_response = httpx.Response(
        200,
        json={"success": True, "reference": "HTTP-ARI-TEST-001", "message": "ARI accepted"},
        request=ari_request,
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=property_response)
    mock_client.post = AsyncMock(return_value=ari_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.modules.ota.providers.http_base.httpx.AsyncClient", return_value=mock_client):
        test = client.post(f"/api/v1/ota/integrations/{integration_id}/test", headers=headers)
        assert test.status_code == 200
        assert test.json()["status"] == "active"

        push = client.post(
            f"/api/v1/ota/integrations/{integration_id}/push-ari",
            headers=headers,
            json={"max_days": 3},
        )
        assert push.status_code == 200
        push_body = push.json()
        assert push_body["success"] is True
        assert push_body["external_reference"] == "HTTP-ARI-TEST-001"

    assert mock_client.get.await_count == 1
    assert mock_client.post.await_count == 1
    posted = mock_client.post.await_args.kwargs["json"]
    assert posted["property_id"] == booking_com["external_property_id"]
    assert len(posted["room_types"]) >= 1


def test_platforms_include_adapter_modes(client):
    headers = _auth_headers(client)
    platforms = client.get("/api/v1/ota/platforms", headers=headers)
    assert platforms.status_code == 200
    row = platforms.json()[0]
    assert "mock" in row["supported_adapter_modes"]
    assert "http" in row["supported_adapter_modes"]


def test_http_adapter_reservation_pull(client):
    headers = _auth_headers(client)

    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]

    patch_response = client.patch(
        f"/api/v1/ota/integrations/{integration_id}",
        headers=headers,
        json={
            "config": {"adapter_mode": "http", "api_base_url": "https://ota.test/v1"},
            "api_key": "test-api-key-12345",
        },
    )
    assert patch_response.status_code == 200

    check_in = (date.today() + timedelta(days=21)).isoformat()
    check_out = (date.today() + timedelta(days=23)).isoformat()
    pull_request = httpx.Request("GET", "https://ota.test/v1/properties/test/reservations")
    pull_response = httpx.Response(
        200,
        json={
            "reference": "HTTP-PULL-001",
            "reservations": [
                {
                    "external_reservation_id": "HTTP-RES-PULL-001",
                    "guest_name": "HTTP Pull Guest",
                    "guest_mobile": "+919811122233",
                    "external_room_type_id": "STD",
                    "check_in_date": check_in,
                    "check_out_date": check_out,
                    "adults": 2,
                    "children": 0,
                }
            ],
        },
        request=pull_request,
    )

    mock_client = MagicMock()
    mock_client.get = AsyncMock(return_value=pull_response)
    mock_client.__aenter__ = AsyncMock(return_value=mock_client)
    mock_client.__aexit__ = AsyncMock(return_value=None)

    with patch("app.modules.ota.providers.http_base.httpx.AsyncClient", return_value=mock_client):
        pull = client.post(
            f"/api/v1/ota/integrations/{integration_id}/pull-reservations",
            headers=headers,
        )
        assert pull.status_code == 200
        body = pull.json()
        assert body["success"] is True, body.get("results") or body
        assert body["created_count"] == 1
        assert body["external_reference"] == "HTTP-PULL-001"
        assert body["results"][0]["external_reservation_id"] == "HTTP-RES-PULL-001"

    assert mock_client.get.await_count == 1
