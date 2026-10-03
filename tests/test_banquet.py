"""Tests for banquet hall and venue booking module."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_dashboard_venues_and_bookings(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    dashboard = client.get("/api/v1/banquet/dashboard", headers=headers, params={"outlet_id": outlet_id})
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_venues"] >= 3
    assert body["upcoming_bookings"] >= 1

    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert venues.status_code == 200
    venue_items = venues.json()["data"]["items"]
    ballroom = next(row for row in venue_items if row["name"] == "Grand Ballroom")

    event_date = date.today() + timedelta(days=30)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Anniversary Gala",
            "event_type": "social",
            "event_date": event_date.isoformat(),
            "start_time": "19:00",
            "end_time": "23:00",
            "guest_count": 120,
            "contact_name": "Test Banquet Guest",
            "contact_phone": "+91 95555 77777",
            "estimated_amount": 85000,
            "advance_paid": 20000,
        },
    )
    assert create.status_code == 201
    created = create.json()
    booking_id = created["id"]
    assert created["status"] == "inquiry"
    assert created["booking_number"].startswith("BQT-")

    confirm = client.post(f"/api/v1/banquet/bookings/{booking_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    overlap = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Overlap Event",
            "event_type": "corporate",
            "event_date": event_date.isoformat(),
            "start_time": "20:00",
            "end_time": "22:00",
            "guest_count": 100,
            "contact_name": "Overlap Guest",
        },
    )
    assert overlap.status_code == 409
