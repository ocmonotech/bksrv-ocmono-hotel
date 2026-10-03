from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


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


def test_rate_inventory_calendar_shape(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    from_date = date.today()
    to_date = from_date + timedelta(days=6)

    response = client.get(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["outlet_id"] == outlet_id
    assert len(payload["dates"]) == 7
    assert payload["room_types"]
    assert any(rt["room_type_id"] == room_type_id for rt in payload["room_types"])
    assert payload["cells"]
    cell = next(c for c in payload["cells"] if c["room_type_id"] == room_type_id)
    assert cell["rate"] > 0
    assert cell["total_rooms"] >= 1
    assert cell["available"] >= 0


def test_rate_inventory_calendar_counts_sold(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    check_in = date.today() + timedelta(days=12)
    check_out = check_in + timedelta(days=2)

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Rate Cal Guest",
            "guest_mobile": "+919111122233",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 4200,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text

    response = client.get(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "from_date": check_in.isoformat(),
            "to_date": check_in.isoformat(),
        },
    )
    assert response.status_code == 200, response.text
    cell = next(
        c
        for c in response.json()["cells"]
        if c["room_type_id"] == room_type_id and c["date"] == check_in.isoformat()
    )
    assert cell["sold"] >= 1
    assert cell["available"] == max(cell["total_rooms"] - cell["sold"] - cell["blocked"], 0)


def test_rate_inventory_calendar_rejects_oversized_range(client):
    headers = _auth_headers(client)
    outlet_id, _ = _hotel_outlet_and_room_type(client, headers)
    from_date = date.today()
    to_date = from_date + timedelta(days=40)
    response = client.get(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "from_date": from_date.isoformat(),
            "to_date": to_date.isoformat(),
        },
    )
    assert response.status_code == 409
