"""Tests for banquet folio deposit and charge posting."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_deposit_and_charge_post_to_guest_folio(client):
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

    event_date = date.today() + timedelta(days=40)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "In-House Wedding Dinner",
            "event_type": "wedding",
            "event_date": event_date.isoformat(),
            "start_time": "19:00",
            "end_time": "23:00",
            "guest_count": 120,
            "contact_name": guests[0]["guest_name"],
            "guest_reservation_id": reservation_id,
            "charge_to_folio": True,
            "estimated_amount": 150000,
            "advance_paid": 50000,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    deposit = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/post-deposit-to-folio",
        headers=headers,
    )
    assert deposit.status_code == 200
    deposited = deposit.json()
    assert deposited["deposit_folio_posted_at"] is not None
    assert deposited["deposit_folio_entry_id"] is not None

    folio_after_deposit = client.get(
        f"/api/v1/pms/reservations/{reservation_id}/folio",
        headers=headers,
    )
    assert folio_after_deposit.status_code == 200
    deposit_types = [entry["entry_type"] for entry in folio_after_deposit.json()["entries"]]
    assert "deposit" in deposit_types

    duplicate_deposit = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/post-deposit-to-folio",
        headers=headers,
    )
    assert duplicate_deposit.status_code == 409

    client.post(f"/api/v1/banquet/bookings/{booking_id}/confirm", headers=headers)
    complete = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/complete",
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
    assert "banquet_charge" in entry_types

    duplicate_charge = client.post(
        f"/api/v1/banquet/bookings/{booking_id}/post-to-folio",
        headers=headers,
    )
    assert duplicate_charge.status_code == 409
