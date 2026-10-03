"""Tests for banquet bookings linked to guest reservations."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_bookings_filter_by_guest_reservation(client):
    headers = _auth_headers(client)

    in_house = client.get("/api/v1/pms/in-house", headers=headers)
    assert in_house.status_code == 200
    guests = in_house.json()
    assert guests
    reservation_id = guests[0]["reservation_id"]

    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]
    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    ballroom = next(row for row in venues if row["name"] == "Grand Ballroom")

    event_date = date.today() + timedelta(days=42)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Linked Guest Reception",
            "event_type": "reception",
            "event_date": event_date.isoformat(),
            "start_time": "19:00",
            "end_time": "23:00",
            "guest_count": 80,
            "contact_name": guests[0]["guest_name"],
            "guest_reservation_id": reservation_id,
            "estimated_amount": 120000,
            "advance_paid": 30000,
        },
    )
    assert create.status_code == 201
    created_id = create.json()["id"]

    linked = client.get(
        "/api/v1/banquet/bookings",
        headers=headers,
        params={"guest_reservation_id": reservation_id, "page_size": 50},
    )
    assert linked.status_code == 200
    items = linked.json()["data"]["items"]
    assert any(row["id"] == created_id for row in items)
    match = next(row for row in items if row["id"] == created_id)
    assert match["guest_reservation_id"] == reservation_id
    assert match["title"] == "Linked Guest Reception"
