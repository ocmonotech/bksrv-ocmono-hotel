"""Tests for spa booking guest notifications."""

from datetime import date, datetime, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_spa_confirm_with_notifications(client):
    headers = _auth_headers(client)

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    massage = next(row for row in services if row["name"] == "Swedish Massage")

    slot_date = date.today() + timedelta(days=6)
    availability = client.get(
        f"/api/v1/spa/services/{massage['id']}/availability",
        headers=headers,
        params={"date": slot_date.isoformat()},
    ).json()
    slot = next(row for row in availability["slots"] if row["is_available"])
    booked_at = datetime.combine(
        slot_date,
        datetime.strptime(slot["start_time"], "%H:%M").time(),
    ).isoformat()

    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": massage["id"],
            "booked_at": booked_at,
            "guest_name": "Notify Guest",
            "guest_phone": "+91 91111 33333",
            "guest_email": "notify-guest@example.com",
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    confirm = client.post(
        f"/api/v1/spa/bookings/{booking_id}/confirm",
        headers=headers,
        json={"send_sms": True, "send_whatsapp": True, "send_email": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    reminder = client.post(
        f"/api/v1/spa/bookings/{booking_id}/send-notification",
        headers=headers,
        json={"kind": "reminder", "send_sms": True, "send_email": False, "send_whatsapp": False},
    )
    assert reminder.status_code == 200
    body = reminder.json()
    assert body["booking_id"] == booking_id
    assert "sms" in body["sent_channels"]
    assert "Reminder" in body["message_preview"]


def test_public_spa_booking_sends_acknowledgment(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    services = client.get("/api/v1/spa/public/services", params={"outlet_id": outlet_id}).json()
    service = services[0]

    target_date = date.today() + timedelta(days=7)
    availability = client.get(
        f"/api/v1/spa/public/services/{service['id']}/availability",
        params={"outlet_id": outlet_id, "date": target_date.isoformat()},
    ).json()
    slot = next(row for row in availability["slots"] if row["is_available"])
    booked_at = datetime.combine(
        target_date,
        datetime.strptime(slot["start_time"], "%H:%M").time(),
    ).isoformat()

    booking = client.post(
        "/api/v1/spa/public/bookings",
        json={
            "outlet_id": outlet_id,
            "service_id": service["id"],
            "booked_at": booked_at,
            "guest_name": "Online Notify Guest",
            "guest_phone": "+91 92222 44444",
            "guest_email": "online-notify@example.com",
            "party_size": 1,
        },
    )
    assert booking.status_code == 201
    booking_number = booking.json()["booking_number"]

    sms_conversations = client.get(
        "/api/v1/communications/conversations",
        headers=headers,
        params={"page": 1, "page_size": 50, "channel": "sms"},
    ).json()["data"]["items"]
    assert any(booking_number in (row.get("last_message") or "") for row in sms_conversations)
