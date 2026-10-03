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


def test_cta_ctd_min_max_stay_enforcement(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    arrival = date.today() + timedelta(days=14)
    departure = arrival + timedelta(days=1)

    # CTA on arrival blocks create
    patch = client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": arrival.isoformat(),
            "cta": True,
            "min_stay": 3,
        },
    )
    assert patch.status_code == 200, patch.text
    cell = next(
        c
        for c in patch.json()["cells"]
        if c["date"] == arrival.isoformat() and c["room_type_id"] == room_type_id
    )
    assert cell["cta"] is True
    assert cell["min_stay"] == 3

    blocked = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "CTA Guest",
            "guest_mobile": "+919111122233",
            "room_type_id": room_type_id,
            "check_in_date": arrival.isoformat(),
            "check_out_date": departure.isoformat(),
            "rate_per_night": 2000,
            "auto_confirm": True,
        },
    )
    assert blocked.status_code == 409, blocked.text
    detail = blocked.json().get("detail") or blocked.json().get("message") or blocked.text
    assert "closed to arrival" in str(detail).lower()

    # Clear CTA, keep min stay — 1-night still blocked
    client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": arrival.isoformat(),
            "cta": False,
            "min_stay": 3,
        },
    )
    short = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Min Stay Guest",
            "guest_mobile": "+919111122234",
            "room_type_id": room_type_id,
            "check_in_date": arrival.isoformat(),
            "check_out_date": departure.isoformat(),
            "rate_per_night": 2000,
            "auto_confirm": True,
        },
    )
    assert short.status_code == 409, short.text
    detail = short.json().get("detail") or short.json().get("message") or short.text
    assert "minimum stay" in str(detail).lower()

    # 3-night stay OK; CTD on intended checkout blocks
    long_out = arrival + timedelta(days=3)
    client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": long_out.isoformat(),
            "ctd": True,
        },
    )
    ctd_block = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "CTD Guest",
            "guest_mobile": "+919111122235",
            "room_type_id": room_type_id,
            "check_in_date": arrival.isoformat(),
            "check_out_date": long_out.isoformat(),
            "rate_per_night": 2000,
            "auto_confirm": True,
        },
    )
    assert ctd_block.status_code == 409, ctd_block.text
    detail = ctd_block.json().get("detail") or ctd_block.json().get("message") or ctd_block.text
    assert "closed to departure" in str(detail).lower()

    # Clear CTD + set max stay 2 — 3 nights blocked
    client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": long_out.isoformat(),
            "ctd": False,
        },
    )
    client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": arrival.isoformat(),
            "min_stay": 1,
            "max_stay": 2,
        },
    )
    max_block = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Max Stay Guest",
            "guest_mobile": "+919111122236",
            "room_type_id": room_type_id,
            "check_in_date": arrival.isoformat(),
            "check_out_date": long_out.isoformat(),
            "rate_per_night": 2000,
            "auto_confirm": True,
        },
    )
    assert max_block.status_code == 409, max_block.text
    detail = max_block.json().get("detail") or max_block.json().get("message") or max_block.text
    assert "maximum stay" in str(detail).lower()

    ok_out = arrival + timedelta(days=2)
    ok = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Stay Ok Guest",
            "guest_mobile": "+919111122237",
            "room_type_id": room_type_id,
            "check_in_date": arrival.isoformat(),
            "check_out_date": ok_out.isoformat(),
            "rate_per_night": 2000,
            "auto_confirm": True,
        },
    )
    assert ok.status_code == 201, ok.text
