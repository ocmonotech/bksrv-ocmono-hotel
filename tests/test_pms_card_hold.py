from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _hotel_outlet_and_room_type(client, headers) -> tuple[int, int]:
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 100},
    )
    assert rooms_resp.status_code == 200
    rooms = rooms_resp.json().get("data", rooms_resp.json()).get("items", [])
    assert rooms, "Expected hotel rooms in seed"
    room = next(
        (r for r in rooms if str(r.get("status", "")).lower() not in {"out_of_order", "maintenance"}),
        rooms[0],
    )
    return room["outlet_id"], room["room_type_id"]


def _create_reservation(client, headers, outlet_id: int, room_type_id: int) -> dict:
    check_in = date.today() + timedelta(days=50)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Card Hold Guest",
            "guest_mobile": "+919333344455",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 4000,
            "deposit_amount": 4000,
            "guarantee_type": "card_hold",
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    return create.json()


def test_card_hold_authorize_and_capture(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation(client, headers, outlet_id, room_type_id)
    reservation_id = reservation["id"]

    # Card-hold guarantee should not post deposit to folio on create
    detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert detail.status_code == 200
    folio_entries = detail.json().get("folio", {}).get("entries", [])
    assert not any(e.get("entry_type") == "deposit" for e in folio_entries)

    hold = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/payment/hold",
        headers=headers,
        json={"card_last4": "4242", "amount": 4000},
    )
    assert hold.status_code == 200, hold.text
    payload = hold.json()
    assert payload["deposit_status"] == "held"
    assert payload["guarantee_type"] == "card_hold"
    assert payload["card_last4"] == "4242"
    assert payload["payment_hold_ref"]
    assert payload["payment_auth_code"]
    assert payload["payment_provider"] == "mock"

    capture = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/deposit/capture",
        headers=headers,
        json={},
    )
    assert capture.status_code == 200
    assert capture.json()["deposit_status"] == "captured"

    detail_after = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    entries = detail_after.json()["folio"]["entries"]
    assert any(e.get("entry_type") == "payment" for e in entries)


def test_capture_hold_then_checkout_settlement(client):
    """Front-desk settlement path: hold → capture to folio → check-in/out."""
    headers = _auth_headers(client)
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 100},
    )
    assert rooms_resp.status_code == 200
    rooms = rooms_resp.json().get("data", rooms_resp.json()).get("items", [])
    room = next(
        (r for r in rooms if str(r.get("status", "")).lower() in {"vacant_clean", "vacant_dirty"}),
        None,
    )
    assert room, "Expected vacant room"
    outlet_id = room["outlet_id"]
    room_type_id = room["room_type_id"]

    check_in = date.today()
    check_out = check_in + timedelta(days=1)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Settle Hold Guest",
            "guest_mobile": "+919222233344",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 2500,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    hold = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/payment/hold",
        headers=headers,
        json={"card_last4": "4242", "amount": 2500},
    )
    assert hold.status_code == 200, hold.text
    assert hold.json()["deposit_status"] == "held"

    checkin = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert checkin.status_code == 200, checkin.text

    capture = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/deposit/capture",
        headers=headers,
        json={},
    )
    assert capture.status_code == 200
    assert capture.json()["deposit_status"] == "captured"

    detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert detail.status_code == 200
    assert any(e.get("entry_type") == "payment" for e in detail.json()["folio"]["entries"])

    checkout = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-out",
        headers=headers,
        json={"force_settle": True},
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["status"] == "checked_out"


def test_card_hold_decline_and_release(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation(client, headers, outlet_id, room_type_id)
    reservation_id = reservation["id"]

    declined = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/payment/hold",
        headers=headers,
        json={"card_last4": "0000"},
    )
    assert declined.status_code in {400, 409}

    hold = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/payment/hold",
        headers=headers,
        json={"card_last4": "1111"},
    )
    assert hold.status_code == 200
    assert hold.json()["deposit_status"] == "held"

    release = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/payment/release",
        headers=headers,
        json={"notes": "Guest cancelled"},
    )
    assert release.status_code == 200
    assert release.json()["deposit_status"] == "pending"
    assert release.json()["payment_hold_ref"] is None
