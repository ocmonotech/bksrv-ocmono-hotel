"""Tests for banquet venue calendar endpoint."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_calendar_groups_bookings_by_venue(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    ballroom = next(row for row in venues if row["name"] == "Grand Ballroom")
    garden = next(row for row in venues if row["name"] == "Pool Deck Lawn")

    event_date = date.today() + timedelta(days=14)
    create_ballroom = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Calendar Ballroom Event",
            "event_type": "corporate",
            "event_date": event_date.isoformat(),
            "start_time": "10:00",
            "end_time": "14:00",
            "guest_count": 80,
            "contact_name": "Calendar Guest A",
            "contact_phone": "+91 97777 11111",
        },
    )
    assert create_ballroom.status_code == 201

    create_garden = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": garden["id"],
            "title": "Calendar Garden Event",
            "event_type": "wedding",
            "event_date": event_date.isoformat(),
            "start_time": "16:00",
            "end_time": "22:00",
            "guest_count": 150,
            "contact_name": "Calendar Guest B",
            "contact_phone": "+91 98888 22222",
        },
    )
    assert create_garden.status_code == 201

    calendar = client.get(
        "/api/v1/banquet/calendar",
        headers=headers,
        params={"outlet_id": outlet_id, "date": event_date.isoformat()},
    )
    assert calendar.status_code == 200
    body = calendar.json()
    assert body["outlet_id"] == outlet_id
    assert len(body["venues"]) >= 2

    ballroom_col = next(col for col in body["venues"] if col["venue_id"] == ballroom["id"])
    garden_col = next(col for col in body["venues"] if col["venue_id"] == garden["id"])
    assert any(row["title"] == "Calendar Ballroom Event" for row in ballroom_col["bookings"])
    assert any(row["title"] == "Calendar Garden Event" for row in garden_col["bookings"])
    assert all(row["title"] != "Calendar Garden Event" for row in ballroom_col["bookings"])
