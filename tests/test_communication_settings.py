"""Tests for communication settings and provider credential wiring."""

from app.modules.communications.models import CommunicationProvider, MessageChannel, ProviderName


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_communication_settings_defaults(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    response = client.get(
        "/api/v1/settings/communication",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["whatsapp"]["enabled"] is True
    assert body["sms"]["provider"] == "mock"
    assert body["email"]["enabled"] is True


def test_communication_settings_update_and_persist(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    patch = client.patch(
        "/api/v1/settings/communication",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "whatsapp": {
                "enabled": True,
                "provider": "meta_cloud_api",
                "sender_id": "1234567890",
                "webhook_url": "https://example.com/webhook",
            },
            "sms": {
                "enabled": False,
                "provider": "twilio",
                "sender_id": "+15551234567",
                "dlt_template_required": True,
            },
            "email": {
                "enabled": True,
                "provider": "sendgrid",
                "from_name": "RestroChain",
                "from_email": "noreply@example.com",
                "reply_to": "support@example.com",
            },
        },
    )
    assert patch.status_code == 200
    assert patch.json()["sms"]["enabled"] is False
    assert patch.json()["whatsapp"]["sender_id"] == "1234567890"

    reload = client.get(
        "/api/v1/settings/communication",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert reload.status_code == 200
    assert reload.json()["email"]["from_email"] == "noreply@example.com"


def test_create_provider_and_test_mock(client, db):
    headers = _auth_headers(client)

    create = client.post(
        "/api/v1/communications/providers",
        headers=headers,
        json={
            "channel": "sms",
            "provider_name": "mock",
            "status": "active",
            "config": {},
            "api_key": "test-secret-key-1234",
            "is_default": True,
        },
    )
    assert create.status_code == 201
    provider_id = create.json()["id"]
    assert create.json()["api_key_last4"] == "1234"

    test = client.post(f"/api/v1/communications/providers/{provider_id}/test", headers=headers)
    assert test.status_code == 200
    assert test.json()["success"] is True
    assert test.json()["mock"] is True

    provider = db.get(CommunicationProvider, provider_id)
    assert provider is not None
    assert provider.channel == MessageChannel.SMS
    assert provider.provider_name == ProviderName.MOCK


def test_send_respects_disabled_sms_channel(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    assert (
        client.patch(
            "/api/v1/settings/communication",
            headers=headers,
            json={
                "outlet_id": outlet_id,
                "sms": {
                    "enabled": False,
                    "provider": "mock",
                    "sender_id": "MOCKSMS",
                    "dlt_template_required": True,
                },
            },
        ).status_code
        == 200
    )

    send = client.post(
        "/api/v1/communications/sms/send",
        headers=headers,
        json={
            "receiver": "+91 90000 11111",
            "message_text": "Disabled channel test",
            "outlet_id": outlet_id,
        },
    )
    assert send.status_code == 409
