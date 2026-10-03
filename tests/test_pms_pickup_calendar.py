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
    """Use an outlet that actually has hotel rooms (seed puts them on Andheri West)."""
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


def test_pickup_calendar_shape(client):
    headers = _auth_headers(client)
    outlet_id, _ = _hotel_outlet_and_room_type(client, headers)
    from_date = date.today()
    to_date = from_date + timedelta(days=6)

    response = client.get(
        f"/api/v1/pms/calendar/pickup?outlet_id={outlet_id}"
        f"&from_date={from_date.isoformat()}&to_date={to_date.isoformat()}",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outlet_id"] == outlet_id
    assert payload["total_rooms"] >= 1
    assert len(payload["days"]) == 7
    day = payload["days"][0]
    assert day["date"] == from_date.isoformat()
    for key in (
        "total_rooms",
        "sold",
        "blocked",
        "available",
        "occupancy_percent",
        "arrivals",
        "departures",
    ):
        assert key in day
    assert day["sold"] + day["blocked"] + day["available"] == day["total_rooms"]


def test_pickup_calendar_counts_reservation(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)

    check_in = date.today() + timedelta(days=45)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Pickup Calendar Guest",
            "guest_mobile": "+919111122233",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3500,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text

    response = client.get(
        f"/api/v1/pms/calendar/pickup?outlet_id={outlet_id}"
        f"&from_date={check_in.isoformat()}&to_date={check_out.isoformat()}",
        headers=headers,
    )
    assert response.status_code == 200
    days = {d["date"]: d for d in response.json()["days"]}
    assert days[check_in.isoformat()]["sold"] >= 1
    assert days[check_in.isoformat()]["arrivals"] >= 1
    assert days[check_out.isoformat()]["departures"] >= 1


def test_pickup_calendar_rejects_oversized_range(client):
    headers = _auth_headers(client)
    outlet_id, _ = _hotel_outlet_and_room_type(client, headers)
    from_date = date.today()
    to_date = from_date + timedelta(days=63)

    response = client.get(
        f"/api/v1/pms/calendar/pickup?outlet_id={outlet_id}"
        f"&from_date={from_date.isoformat()}&to_date={to_date.isoformat()}",
        headers=headers,
    )
    assert response.status_code in {400, 409}
