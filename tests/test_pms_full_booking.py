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


def test_staff_amend_reservation(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)

    check_in = date.today() + timedelta(days=25)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Amend Stay Guest",
            "guest_mobile": "+919666655554",
            "guest_email": "amend@example.com",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 2,
            "children": 0,
            "rate_per_night": 4000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    new_checkout = (check_out + timedelta(days=1)).isoformat()
    amend = client.patch(
        f"/api/v1/pms/reservations/{reservation_id}",
        headers=headers,
        json={
            "guest_name": "Amended Stay Guest",
            "guest_mobile": "+919666655555",
            "guest_email": "amended@example.com",
            "check_out_date": new_checkout,
            "adults": 3,
            "children": 1,
            "rate_per_night": 4500,
            "guest_id_document": "AADHAAR-998877",
            "notes": "Staff amend from desk",
        },
    )
    assert amend.status_code == 200, amend.text
    body = amend.json()
    assert body["guest_name"] == "Amended Stay Guest"
    assert body["guest_mobile"] == "+919666655555"
    assert body["guest_email"] == "amended@example.com"
    assert body["check_out_date"] == new_checkout
    assert body["adults"] == 3
    assert body["children"] == 1
    assert float(body["rate_per_night"]) == 4500
    assert body["guest_id_document"] == "AADHAAR-998877"
    assert body["nights"] == 3
    assert float(body["total_amount"]) == 13500

    closed = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/cancel",
        headers=headers,
        json={"reason": "cleanup"},
    )
    assert closed.status_code == 200
    blocked = client.patch(
        f"/api/v1/pms/reservations/{reservation_id}",
        headers=headers,
        json={"guest_name": "Should Fail"},
    )
    assert blocked.status_code == 409


def test_assign_room(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)
    room = _vacant_room(client, headers, outlet_id, room_type_id)

    check_in = date.today() + timedelta(days=20)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Assign Room Guest",
            "guest_mobile": "+919888877777",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 4000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201
    reservation_id = create.json()["id"]

    assign = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/assign-room",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert assign.status_code == 200
    assert assign.json()["room_id"] == room["id"]
    assert assign.json()["status"] == "confirmed"


def test_front_desk_arrival_assign_checkin_checkout(client):
    """Mirrors front-desk board quick actions for same-day arrivals/departures."""
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
            "guest_name": "Front Desk Arrival",
            "guest_mobile": "+919777766665",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3500,
            "auto_confirm": False,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]
    assert create.json()["status"] == "pending"

    assign = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/assign-room",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert assign.status_code == 200, assign.text
    assert assign.json()["room_id"] == room["id"]

    checkin = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert checkin.status_code == 200, checkin.text
    assert checkin.json()["status"] == "checked_in"
    assert checkin.json()["room_id"] == room["id"]

    checkout = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-out",
        headers=headers,
        json={"force_settle": True},
    )
    assert checkout.status_code == 200, checkout.text
    assert checkout.json()["status"] == "checked_out"


def test_tape_chart_returns_rooms(client):
    headers = _auth_headers(client)
    outlet_id, _ = _outlet_and_room_type(client, headers)
    from_date = date.today()
    to_date = from_date + timedelta(days=7)

    response = client.get(
        f"/api/v1/pms/calendar/tape-chart?outlet_id={outlet_id}"
        f"&from_date={from_date.isoformat()}&to_date={to_date.isoformat()}",
        headers=headers,
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["outlet_id"] == outlet_id
    assert isinstance(payload["rooms"], list)
    assert len(payload["rooms"]) >= 1
    assert "hk_status" in payload["rooms"][0]


def test_room_block_blocks_availability(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)
    room = _vacant_room(client, headers, outlet_id, room_type_id)

    start = date.today() + timedelta(days=30)
    end = start + timedelta(days=3)

    block = client.post(
        "/api/v1/pms/room-blocks",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_id": room["id"],
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "block_type": "maintenance",
            "reason": "AC repair",
        },
    )
    assert block.status_code == 201

    conflict = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Blocked Guest",
            "guest_mobile": "+919777766666",
            "room_type_id": room_type_id,
            "room_id": room["id"],
            "check_in_date": start.isoformat(),
            "check_out_date": (start + timedelta(days=1)).isoformat(),
            "rate_per_night": 3500,
            "auto_confirm": True,
        },
    )
    assert conflict.status_code == 409


def test_night_audit_idempotency(client):
    headers = _auth_headers(client)
    outlet_id, _ = _outlet_and_room_type(client, headers)
    business_date = date.today() - timedelta(days=1)

    first = client.post(
        "/api/v1/pms/night-audit/run",
        headers=headers,
        json={"outlet_id": outlet_id, "business_date": business_date.isoformat()},
    )
    assert first.status_code == 200

    second = client.post(
        "/api/v1/pms/night-audit/run",
        headers=headers,
        json={"outlet_id": outlet_id, "business_date": business_date.isoformat()},
    )
    assert second.status_code == 409


def test_cancel_fee_posting(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _outlet_and_room_type(client, headers)

    plan = client.post(
        "/api/v1/pms/rate-plans",
        headers=headers,
        json={
            "room_type_id": room_type_id,
            "name": "Cancel Fee Plan",
            "code": f"CFEE{date.today().strftime('%H%M%S')}",
            "rate_per_night": 5000,
            "cancellation_fee_percent": 50,
            "no_show_fee_percent": 100,
            "default_guarantee": "deposit",
        },
    )
    assert plan.status_code == 201
    plan_id = plan.json()["id"]

    check_in = date.today() + timedelta(days=40)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Fee Guest",
            "guest_mobile": "+919666655555",
            "room_type_id": room_type_id,
            "rate_plan_id": plan_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 0,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201
    reservation_id = create.json()["id"]
    total_amount = float(create.json()["total_amount"])

    cancel = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/cancel",
        headers=headers,
        json={"reason": "Guest cancelled"},
    )
    assert cancel.status_code == 200
    assert cancel.json()["status"] == "cancelled"

    folio = client.get(f"/api/v1/pms/reservations/{reservation_id}/folio", headers=headers)
    assert folio.status_code == 200
    entries = folio.json()["entries"]
    fee_entries = [e for e in entries if e["entry_type"] == "adjustment"]
    assert fee_entries
    assert float(fee_entries[-1]["amount"]) == round(total_amount * 0.5, 2)


def test_front_desk_readiness(client):
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
            "guest_name": "Readiness Guest",
            "guest_mobile": "+919555544443",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 2800,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]

    empty_assign = client.get(
        "/api/v1/pms/front-desk/readiness",
        headers=headers,
        params={"outlet_id": outlet_id, "business_date": check_in.isoformat()},
    )
    assert empty_assign.status_code == 200, empty_assign.text
    payload = empty_assign.json()
    assert payload["arrivals_total"] >= 1
    row = next(i for i in payload["items"] if i["reservation_id"] == reservation_id)
    assert row["readiness"] == "unassigned"

    assign = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/assign-room",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert assign.status_code == 200, assign.text

    ready = client.get(
        "/api/v1/pms/front-desk/readiness",
        headers=headers,
        params={"outlet_id": outlet_id, "business_date": check_in.isoformat()},
    )
    assert ready.status_code == 200
    row = next(i for i in ready.json()["items"] if i["reservation_id"] == reservation_id)
    if str(room.get("status", "")).lower() == "vacant_clean":
        assert row["readiness"] == "ready"
        assert ready.json()["ready_count"] >= 1
    else:
        assert row["readiness"] == "not_ready"
