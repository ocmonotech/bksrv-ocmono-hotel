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


def test_day_use_prices_at_half_night_by_default(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    check_in = date.today() + timedelta(days=40)

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Day Use Guest",
            "guest_mobile": "+919555566677",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_in.isoformat(),  # same-day allowed for day use
            "rate_per_night": 4000,
            "day_use": True,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    payload = create.json()
    assert payload["day_use"] is True
    assert payload["nights"] == 0
    assert payload["check_out_date"] == (check_in + timedelta(days=1)).isoformat()
    assert float(payload["total_amount"]) == 2000.0  # 50% default
    assert payload["late_check_out"] is False


def test_day_use_rejects_late_checkout_combo(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    check_in = date.today() + timedelta(days=41)

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Bad Combo Guest",
            "guest_mobile": "+919555566688",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "rate_per_night": 3000,
            "day_use": True,
            "late_check_out": True,
            "auto_confirm": True,
        },
    )
    assert create.status_code in {400, 409, 422}


def test_day_use_rate_plan_percent(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)

    plan = client.post(
        "/api/v1/pms/rate-plans",
        headers=headers,
        json={
            "room_type_id": room_type_id,
            "name": "Day Use Rack",
            "code": f"DU{date.today().strftime('%H%M%S')}",
            "rate_per_night": 5000,
            "allows_day_use": True,
            "day_use_rate_percent": 60,
            "default_guarantee": "none",
        },
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert plan.json()["allows_day_use"] is True
    assert float(plan.json()["day_use_rate_percent"]) == 60

    check_in = date.today() + timedelta(days=42)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Plan Day Use Guest",
            "guest_mobile": "+919555566699",
            "room_type_id": room_type_id,
            "rate_plan_id": plan_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "rate_per_night": 0,
            "day_use": True,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    assert float(create.json()["total_amount"]) == 3000.0  # 60% of 5000
