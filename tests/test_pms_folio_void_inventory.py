from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _outlet_and_room_type(client, headers):
    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    assert room_types, "Expected housekeeping room types in seed"
    return outlet_id, room_types[0]["id"]


def _vacant_room(client, headers, outlet_id: int, room_type_id: int) -> dict:
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 100},
    )
    assert rooms_resp.status_code == 200
    payload = rooms_resp.json()
    rooms = payload.get("data", payload).get("items", payload if isinstance(payload, list) else [])
    for room in rooms:
        if room.get("room_type_id") == room_type_id and str(room.get("status", "")).lower() in {
            "vacant_clean",
            "vacant_dirty",
        }:
            return room
    assert rooms, "Expected hotel rooms in seed"
    return rooms[0]


def test_void_folio_entry_and_inventory_override(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)
    room = _vacant_room(client, headers, outlet_id, room_type_id)

    check_in = date.today()
    check_out = check_in + timedelta(days=1)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Void Folio Guest",
            "guest_mobile": "+919444433322",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    check_in_resp = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert check_in_resp.status_code == 200, check_in_resp.text

    charge = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/charges",
        headers=headers,
        json={"entry_type": "adjustment", "description": "Mistaken minibar", "amount": 350},
    )
    assert charge.status_code == 200, charge.text
    folio = charge.json()
    entry = next(e for e in folio["entries"] if e["description"] == "Mistaken minibar")
    balance_before = float(folio["balance"])

    voided = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/entries/{entry['id']}/void",
        headers=headers,
        json={"reason": "posted in error"},
    )
    assert voided.status_code == 200, voided.text
    body = voided.json()
    assert float(body["balance"]) == balance_before - 350
    assert any("[VOIDED]" in e["description"] for e in body["entries"] if e["id"] == entry["id"])
    assert any(e["description"].startswith(f"VOID #{entry['id']}:") for e in body["entries"])

    target = (date.today() + timedelta(days=3)).isoformat()
    override = client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": target,
            "stop_sell": True,
            "rate": 9999,
        },
    )
    assert override.status_code == 200, override.text
    cell = override.json()["cells"][0]
    assert cell["stop_sell"] is True
    assert cell["available"] == 0
    assert float(cell["rate"]) == 9999
    assert cell["rate_overridden"] is True


def test_fulfill_special_requests(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)

    check_in = date.today() + timedelta(days=4)
    check_out = check_in + timedelta(days=1)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Request Fulfill Guest",
            "guest_mobile": "+919333322211",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 2800,
            "notes": "Guest special request: Extra pillows\nGuest special request: Late dinner",
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    fulfill = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/special-requests/fulfill",
        headers=headers,
    )
    assert fulfill.status_code == 200, fulfill.text
    assert fulfill.json()["fulfilled_count"] == 2

    detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert detail.status_code == 200
    notes = detail.json()["notes"]
    assert "Fulfilled special request: Extra pillows" in notes
    assert "Guest special request:" not in notes


def test_stop_sell_blocks_booking_and_availability(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)

    target_in = date.today() + timedelta(days=8)
    target_out = target_in + timedelta(days=1)

    override = client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": target_in.isoformat(),
            "stop_sell": True,
            "rate": 7777,
        },
    )
    assert override.status_code == 200, override.text

    availability = client.get(
        "/api/v1/pms/availability",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "check_in_date": target_in.isoformat(),
            "check_out_date": target_out.isoformat(),
        },
    )
    assert availability.status_code == 200, availability.text
    room = next(
        row for row in availability.json()["room_types"] if row["room_type_id"] == room_type_id
    )
    assert room["available_rooms"] == 0
    assert float(room["resolved_rate"]) == 7777

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Stop Sell Guest",
            "guest_mobile": "+919222211100",
            "room_type_id": room_type_id,
            "check_in_date": target_in.isoformat(),
            "check_out_date": target_out.isoformat(),
            "rate_per_night": 3000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 409, create.text
    assert "stop-sold" in create.json().get("message", "").lower() or "stop-sold" in str(
        create.json()
    ).lower()
