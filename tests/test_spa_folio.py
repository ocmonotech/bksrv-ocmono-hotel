"""Tests for spa folio charge posting."""

from datetime import date, datetime, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_spa_complete_posts_charge_to_guest_folio(client):
    headers = _auth_headers(client)

    in_house = client.get("/api/v1/pms/in-house", headers=headers)
    assert in_house.status_code == 200
    guests = in_house.json()
    assert guests
    reservation_id = guests[0]["reservation_id"]

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    massage = next(row for row in services if row["name"] == "Swedish Massage")

    target_date = date.today() + timedelta(days=3)
    availability = client.get(
        f"/api/v1/spa/services/{massage['id']}/availability",
        headers=headers,
        params={"date": target_date.isoformat()},
    ).json()
    slot = next(row for row in availability["slots"] if row["is_available"])
    booked_at = datetime.combine(
        target_date,
        datetime.strptime(slot["start_time"], "%H:%M").time(),
    ).isoformat()

    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": massage["id"],
            "booked_at": booked_at,
            "guest_name": guests[0]["guest_name"],
            "guest_reservation_id": reservation_id,
            "charge_to_folio": True,
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    client.post(f"/api/v1/spa/bookings/{booking_id}/confirm", headers=headers)
    client.post(f"/api/v1/spa/bookings/{booking_id}/start", headers=headers)

    complete = client.post(
        f"/api/v1/spa/bookings/{booking_id}/complete",
        headers=headers,
        json={"post_to_folio": True},
    )
    assert complete.status_code == 200
    completed = complete.json()
    assert completed["status"] == "completed"
    assert completed["folio_posted_at"] is not None
    assert completed["folio_entry_id"] is not None

    folio = client.get(f"/api/v1/pms/reservations/{reservation_id}/folio", headers=headers)
    assert folio.status_code == 200
    entry_types = [entry["entry_type"] for entry in folio.json()["entries"]]
    assert "spa_charge" in entry_types

    duplicate = client.post(f"/api/v1/spa/bookings/{booking_id}/post-to-folio", headers=headers)
    assert duplicate.status_code == 409
