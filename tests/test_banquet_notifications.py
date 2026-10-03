"""Tests for banquet booking guest notifications."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_confirm_with_notifications(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    ballroom = next(row for row in venues if row["name"] == "Grand Ballroom")

    event_date = date.today() + timedelta(days=35)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Notify Banquet Event",
            "event_type": "wedding",
            "event_date": event_date.isoformat(),
            "start_time": "18:00",
            "end_time": "23:00",
            "guest_count": 150,
            "contact_name": "Notify Guest",
            "contact_phone": "+91 91111 55555",
            "contact_email": "banquet-notify@example.com",
            "estimated_amount": 150000,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    confirm = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/confirm",
        headers=headers,
        json={"send_sms": True, "send_whatsapp": True, "send_email": True},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    reminder = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/send-notification",
        headers=headers,
        json={"kind": "reminder", "send_sms": True, "send_email": False, "send_whatsapp": False},
    )
    assert reminder.status_code == 200
    body = reminder.json()
    assert body["booking_id"] == booking_id
    assert "sms" in body["sent_channels"]
    assert "Reminder" in body["message_preview"]


def test_public_banquet_inquiry_sends_acknowledgment(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    venues = client.get("/api/v1/banquet/public/venues", params={"outlet_id": outlet_id}).json()
    venue = next(row for row in venues if row["name"] == "Summit Conference Hall")
    target_date = date.today() + timedelta(days=50)
    availability = client.get(
        f"/api/v1/banquet/public/venues/{venue['id']}/availability",
        params={"outlet_id": outlet_id, "date": target_date.isoformat()},
    ).json()
    slot = next(row for row in availability["slots"] if row["is_available"])

    inquiry = client.post(
        "/api/v1/banquet/public/inquiries",
        json={
            "outlet_id": outlet_id,
            "venue_id": venue["id"],
            "title": "Online Notify Conference",
            "event_type": "conference",
            "event_date": target_date.isoformat(),
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "guest_count": 60,
            "contact_name": "Online Notify Guest",
            "contact_phone": "+91 92222 66666",
            "contact_email": "online-banquet-notify@example.com",
        },
    )
    assert inquiry.status_code == 201
    booking_number = inquiry.json()["booking_number"]

    sms_conversations = client.get(
        "/api/v1/communications/conversations",
        headers=headers,
        params={"page": 1, "page_size": 50, "channel": "sms"},
    ).json()["data"]["items"]
    assert any(booking_number in (row.get("last_message") or "") for row in sms_conversations)
