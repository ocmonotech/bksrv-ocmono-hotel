from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ensure_vacant_room(client, headers) -> dict:
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 100},
    )
    assert rooms_resp.status_code == 200
    payload = rooms_resp.json()
    rooms = payload.get("data", payload).get("items", [])
    for room in rooms:
        if str(room.get("status", "")).lower() in {"vacant_clean", "vacant_dirty"}:
            return room

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    created = client.post(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_types[0]["id"],
            "room_number": f"CS{date.today().strftime('%H%M%S')}",
            "floor": "7",
            "status": "vacant_clean",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_cashier_shift_open_collect_close(client):
    headers = _auth_headers(client)
    room = _ensure_vacant_room(client, headers)
    outlet_id = room["outlet_id"]

    current = client.get(
        "/api/v1/pms/cashier/shifts/current",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert current.status_code == 200
    assert current.json() is None

    opened = client.post(
        "/api/v1/pms/cashier/shifts/open",
        headers=headers,
        json={"outlet_id": outlet_id, "opening_float": 2000},
    )
    assert opened.status_code == 201, opened.text
    shift = opened.json()
    assert shift["status"] == "open"
    assert float(shift["opening_float"]) == 2000
    assert float(shift["expected_cash_live"]) == 2000

    dup = client.post(
        "/api/v1/pms/cashier/shifts/open",
        headers=headers,
        json={"outlet_id": outlet_id, "opening_float": 100},
    )
    assert dup.status_code == 409

    check_in = date.today()
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Cashier Guest",
            "guest_mobile": "+919666655544",
            "room_type_id": room["room_type_id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "rate_per_night": 3000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    ci = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert ci.status_code == 200, ci.text

    pay = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/payments",
        headers=headers,
        json={"amount": 1500, "tender": "cash"},
    )
    assert pay.status_code == 200, pay.text

    live = client.get(
        "/api/v1/pms/cashier/shifts/current",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert live.status_code == 200
    live_body = live.json()
    assert float(live_body["tender_mix"]["cash"]) == 1500
    assert float(live_body["expected_cash_live"]) == 3500

    closed = client.post(
        f"/api/v1/pms/cashier/shifts/{shift['id']}/close",
        headers=headers,
        json={"declared_cash": 3500, "notes": "Balanced"},
    )
    assert closed.status_code == 200, closed.text
    body = closed.json()
    assert body["status"] == "closed"
    assert float(body["declared_cash"]) == 3500
    assert float(body["expected_cash"]) == 3500
    assert float(body["cash_variance"]) == 0
    assert float(body["tender_cash"]) == 1500

    after = client.get(
        "/api/v1/pms/cashier/shifts/current",
        headers=headers,
        params={"outlet_id": outlet_id},
    )
    assert after.status_code == 200
    assert after.json() is None
