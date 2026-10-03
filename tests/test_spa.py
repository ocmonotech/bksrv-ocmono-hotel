"""Tests for spa and activities booking module."""

from datetime import date, datetime, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _first_outlet_id(client, headers: dict[str, str]) -> int:
    response = client.get("/api/v1/outlets", headers=headers)
    assert response.status_code == 200
    items = response.json()["data"]["items"]
    assert items
    return items[0]["id"]


def test_spa_dashboard_services_and_bookings(client):
    headers = _auth_headers(client)
    outlet_id = _first_outlet_id(client, headers)

    dashboard = client.get("/api/v1/spa/dashboard", headers=headers, params={"outlet_id": outlet_id})
    assert dashboard.status_code == 200
    body = dashboard.json()
    assert body["total_services"] >= 4
    assert body["today_bookings"] >= 0

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert services.status_code == 200
    service_items = services.json()["data"]["items"]
    assert len(service_items) >= 4
    massage = next(row for row in service_items if row["name"] == "Swedish Massage")

    tomorrow = date.today() + timedelta(days=2)
    availability = client.get(
        f"/api/v1/spa/services/{massage['id']}/availability",
        headers=headers,
        params={"date": tomorrow.isoformat()},
    )
    assert availability.status_code == 200
    slots = availability.json()["slots"]
    assert len(slots) >= 1
    first_open = next(slot for slot in slots if slot["is_available"])

    booked_at = datetime.combine(tomorrow, datetime.strptime(first_open["start_time"], "%H:%M").time())
    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": massage["id"],
            "booked_at": booked_at.isoformat(),
            "guest_name": "Test Spa Guest",
            "guest_phone": "+91 90000 00099",
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    created = create.json()
    booking_id = created["id"]
    assert created["status"] == "pending"
    assert created["booking_number"].startswith("SPA-")

    confirm = client.post(f"/api/v1/spa/bookings/{booking_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    start = client.post(f"/api/v1/spa/bookings/{booking_id}/start", headers=headers)
    assert start.status_code == 200
    assert start.json()["status"] == "in_progress"

    complete = client.post(f"/api/v1/spa/bookings/{booking_id}/complete", headers=headers)
    assert complete.status_code == 200
    assert complete.json()["status"] == "completed"

    list_response = client.get(
        "/api/v1/spa/bookings",
        headers=headers,
        params={"outlet_id": outlet_id, "status": "completed"},
    )
    assert list_response.status_code == 200
    assert any(row["id"] == booking_id for row in list_response.json()["data"]["items"])


def test_spa_create_service(client):
    headers = _auth_headers(client)
    outlet_id = _first_outlet_id(client, headers)

    response = client.post(
        "/api/v1/spa/services",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "name": "Hot Stone Therapy",
            "category": "spa",
            "duration_minutes": 75,
            "price": 3200,
            "max_capacity": 1,
        },
    )
    assert response.status_code == 201
    body = response.json()
    assert body["name"] == "Hot Stone Therapy"
    assert body["category"] == "spa"
