"""Tests for PMS guest reservation notifications."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_pms_confirm_with_notifications(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    room_types = client.get("/api/v1/pms/public/room-types", params={"outlet_id": outlet_id}).json()
    room_type = room_types[0]

    check_in = date.today() + timedelta(days=21)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Notify Guest",
            "guest_mobile": "+91 91111 66666",
            "guest_email": "pms-notify@example.com",
            "room_type_id": room_type["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 2,
            "children": 0,
            "rate_per_night": 0,
        },
    )
    assert create.status_code == 201
    reservation_id = create.json()["id"]

    confirm = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/confirm",
        headers=headers,
        json={"send_sms": True, "send_whatsapp": True, "send_email": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    reminder = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/send-notification",
        headers=headers,
        json={"kind": "reminder", "send_sms": True, "send_email": False, "send_whatsapp": False},
    )
    assert reminder.status_code == 200
    body = reminder.json()
    assert body["reservation_id"] == reservation_id
    assert "sms" in body["sent_channels"]
    assert "Reminder" in body["message_preview"]


def test_public_room_booking_sends_acknowledgment(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    room_types = client.get("/api/v1/pms/public/room-types", params={"outlet_id": outlet_id}).json()
    room_type = room_types[0]
    check_in = date.today() + timedelta(days=28)
    check_out = check_in + timedelta(days=2)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type["id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Online Notify Guest",
            "guest_mobile": "+91 92222 77777",
            "guest_email": "online-pms-notify@example.com",
            "adults": 2,
        },
    )
    assert booking.status_code == 201
    confirmation_number = booking.json()["confirmation_number"]

    sms_conversations = client.get(
        "/api/v1/communications/conversations",
        headers=headers,
        params={"page": 1, "page_size": 50, "channel": "sms"},
    ).json()["data"]["items"]
    assert any(confirmation_number in (row.get("last_message") or "") for row in sms_conversations)
