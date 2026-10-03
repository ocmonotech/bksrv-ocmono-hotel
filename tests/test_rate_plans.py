from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_rate_plans_and_resolved_availability(client):
    headers = _auth_headers(client)

    plans = client.get("/api/v1/pms/rate-plans", headers=headers)
    assert plans.status_code == 200
    plan_list = plans.json()
    assert len(plan_list) >= 3
    rack = next(p for p in plan_list if p["code"].endswith("_RACK"))
    assert rack["is_default"] is True

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    room_type_id = room_types[0]["id"]

    check_in = date(date.today().year, 11, 10)
    check_out = check_in + timedelta(days=2)

    direct = client.get(
        "/api/v1/pms/availability",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "source": "direct",
        },
    )
    assert direct.status_code == 200
    direct_row = next(r for r in direct.json()["room_types"] if r["room_type_id"] == room_type_id)
    assert direct_row["resolved_rate"] == direct_row["base_rate"]

    ota = client.get(
        "/api/v1/pms/availability",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "source": "ota_booking_com",
        },
    )
    assert ota.status_code == 200
    ota_row = next(r for r in ota.json()["room_types"] if r["room_type_id"] == room_type_id)
    assert ota_row["resolved_rate"] < ota_row["base_rate"]
    assert ota_row["rate_plan_code"].endswith("_BCOM")

    create = client.post(
        "/api/v1/pms/rate-plans",
        headers=headers,
        json={
            "room_type_id": room_type_id,
            "name": "Test Weekend",
            "code": "TEST_WKND",
            "rate_per_night": 4999,
            "min_nights": 1,
        },
    )
    assert create.status_code == 201
    assert create.json()["code"] == "TEST_WKND"


def test_rate_plan_packages_and_resolved_rate(client):
    headers = _auth_headers(client)

    plans = client.get("/api/v1/pms/rate-plans", headers=headers)
    assert plans.status_code == 200
    plan_list = plans.json()
    bb_plan = next((p for p in plan_list if p["code"].endswith("_BB")), None)
    assert bb_plan is not None
    assert len(bb_plan["inclusions"]) >= 1
    assert bb_plan["effective_rate_per_night"] > bb_plan["rate_per_night"]

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]
    room_type_id = bb_plan["room_type_id"]

    check_in = date(date.today().year, 11, 10)
    check_out = check_in + timedelta(days=2)

    availability = client.get(
        "/api/v1/pms/availability",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "source": "direct",
        },
    )
    assert availability.status_code == 200
    row = next(r for r in availability.json()["room_types"] if r["room_type_id"] == room_type_id)
    assert row["resolved_rate"] == row["base_rate"]

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Package Guest",
            "guest_mobile": "+919900011122",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "source": "direct",
            "rate_plan_id": bb_plan["id"],
            "rate_per_night": 0,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201
    reservation = create.json()
    assert reservation["rate_plan_id"] == bb_plan["id"]
    assert reservation["rate_per_night"] == bb_plan["effective_rate_per_night"]
    assert len(reservation["package_inclusions"]) >= 1
    assert reservation["total_amount"] == reservation["rate_per_night"] * 2
