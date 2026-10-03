"""Tests for public guest spa self-booking portal."""

from datetime import date, datetime, timedelta


def _auth_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _spa_service_for_outlet(client, headers: dict[str, str]) -> tuple[int, dict]:
    outlets = client.get("/api/v1/outlets?page=1&page_size=20", headers=headers).json()["data"]["items"]
    for outlet in outlets:
        services = client.get(
            "/api/v1/spa/services",
            headers=headers,
            params={"outlet_id": outlet["id"], "page_size": 50},
        ).json()["data"]["items"]
        if services:
            return outlet["id"], services[0]
    raise AssertionError("No spa services seeded for any outlet")


def test_public_spa_booking_flow(client):
    headers = _auth_headers(client)
    outlet_id, service = _spa_service_for_outlet(client, headers)

    public_services = client.get("/api/v1/spa/public/services", params={"outlet_id": outlet_id})
    assert public_services.status_code == 200
    assert any(row["id"] == service["id"] for row in public_services.json())

    target_date = date.today() + timedelta(days=5)
    availability = client.get(
        f"/api/v1/spa/public/services/{service['id']}/availability",
        params={"outlet_id": outlet_id, "date": target_date.isoformat()},
    )
    assert availability.status_code == 200
    slot = next(row for row in availability.json()["slots"] if row["is_available"])
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
            "guest_name": "Online Guest",
            "guest_phone": "+91 91111 22222",
            "guest_email": "guest@example.com",
            "party_size": 1,
            "notes": "Prefer morning slot",
        },
    )
    assert booking.status_code == 201
    body = booking.json()
    assert body["status"] == "pending"
    assert body["paid"] is False
    assert body["booking_number"].startswith("SPA-")

    staff_list = client.get(
        "/api/v1/spa/bookings",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert staff_list.status_code == 200
    assert any(row["id"] == body["booking_id"] for row in staff_list.json()["data"]["items"])


def test_public_spa_booking_pay_now_confirms(client):
    headers = _auth_headers(client)
    outlet_id, service = _spa_service_for_outlet(client, headers)
    target_date = date.today() + timedelta(days=6)
    availability = client.get(
        f"/api/v1/spa/public/services/{service['id']}/availability",
        params={"outlet_id": outlet_id, "date": target_date.isoformat()},
    )
    slot = next(row for row in availability.json()["slots"] if row["is_available"])
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
            "guest_name": "Prepaid Guest",
            "guest_phone": "+91 93333 44444",
            "pay_now": True,
            "payment_provider": "razorpay",
            "card_last4": "4242",
            "payment_amount": float(service.get("price") or 100),
        },
    )
    assert booking.status_code == 201
    body = booking.json()
    assert body["status"] == "confirmed"
    assert body["paid"] is True
    assert body["payment_ref"]
    assert body["card_last4"] == "4242"

    declined = client.post(
        "/api/v1/spa/public/bookings",
        json={
            "outlet_id": outlet_id,
            "service_id": service["id"],
            "booked_at": booked_at,
            "guest_name": "Decline Guest",
            "guest_phone": "+91 95555 66666",
            "pay_now": True,
            "payment_provider": "cashfree",
            "card_last4": "0000",
        },
    )
    assert declined.status_code == 409


def test_public_online_gateways_list(client):
    headers = _auth_headers(client)
    outlet_id, _ = _spa_service_for_outlet(client, headers)
    response = client.get("/api/v1/payments/public/gateways", params={"outlet_id": outlet_id})
    assert response.status_code == 200
    providers = {row["provider"] for row in response.json()}
    assert "razorpay" in providers
    assert "cashfree" in providers
    assert "ccavenue" in providers
    assert "phonepe" in providers
