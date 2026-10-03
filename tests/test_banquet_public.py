"""Tests for public guest banquet inquiry portal."""

from datetime import date, timedelta


def test_public_banquet_inquiry_flow(client):
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    venues = client.get("/api/v1/banquet/public/venues", params={"outlet_id": outlet_id})
    assert venues.status_code == 200
    venue_items = venues.json()
    assert len(venue_items) >= 1
    venue = next(row for row in venue_items if row["name"] == "Summit Conference Hall")

    target_date = date.today() + timedelta(days=45)
    availability = client.get(
        f"/api/v1/banquet/public/venues/{venue['id']}/availability",
        params={"outlet_id": outlet_id, "date": target_date.isoformat()},
    )
    assert availability.status_code == 200
    slot = next(row for row in availability.json()["slots"] if row["is_available"])

    inquiry = client.post(
        "/api/v1/banquet/public/inquiries",
        json={
            "outlet_id": outlet_id,
            "venue_id": venue["id"],
            "title": "Annual Sales Meet",
            "event_type": "corporate",
            "event_date": target_date.isoformat(),
            "start_time": slot["start_time"],
            "end_time": slot["end_time"],
            "guest_count": 60,
            "contact_name": "Online Banquet Guest",
            "contact_phone": "+91 91111 33333",
            "contact_email": "banquet.guest@example.com",
            "notes": "Need projector and lunch setup",
        },
    )
    assert inquiry.status_code == 201
    body = inquiry.json()
    assert body["status"] == "inquiry"
    assert body["booking_number"].startswith("BQT-")

    staff_list = client.get(
        "/api/v1/banquet/bookings",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert staff_list.status_code == 200
    assert any(row["id"] == body["booking_id"] for row in staff_list.json()["data"]["items"])
