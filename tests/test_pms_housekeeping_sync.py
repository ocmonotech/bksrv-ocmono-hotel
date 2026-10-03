"""PMS ↔ housekeeping task sync: check-in/out + night-audit stayover cleans."""

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
    """Return a vacant room, creating one if the seed has none for the first outlet."""
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
    assert room_types, "Expected housekeeping room types in seed"
    room_type_id = room_types[0]["id"]

    created = client.post(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "room_number": f"T{date.today().strftime('%H%M%S')}",
            "floor": "1",
            "status": "vacant_clean",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def _list_tasks(client, headers, outlet_id: int, room_id: int) -> list[dict]:
    resp = client.get(
        "/api/v1/housekeeping/tasks",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 100},
    )
    assert resp.status_code == 200
    payload = resp.json()
    items = payload.get("data", payload).get("items", [])
    return [t for t in items if t.get("room_id") == room_id]


def test_checkout_creates_departure_task_and_checkin_sets_occupied(client):
    headers = _auth_headers(client)
    room = _ensure_vacant_room(client, headers)
    outlet_id = room["outlet_id"]
    room_type_id = room["room_type_id"]

    check_in = date.today()
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "HK Sync Guest",
            "guest_mobile": "+919111122222",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
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
    assert ci.json()["status"] == "checked_in"

    room_after_ci = client.get(f"/api/v1/housekeeping/rooms/{room['id']}", headers=headers)
    assert room_after_ci.status_code == 200
    assert room_after_ci.json()["status"] == "occupied"

    co = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-out",
        headers=headers,
        json={"force_settle": True},
    )
    assert co.status_code == 200, co.text
    assert co.json()["status"] == "checked_out"

    room_after_co = client.get(f"/api/v1/housekeeping/rooms/{room['id']}", headers=headers)
    assert room_after_co.status_code == 200
    assert room_after_co.json()["status"] == "checkout_pending"

    tasks = _list_tasks(client, headers, outlet_id, room["id"])
    checkout_tasks = [
        t
        for t in tasks
        if t.get("task_type") == "checkout" and t.get("status") in {"pending", "in_progress"}
    ]
    assert checkout_tasks, "Expected a pending checkout/departure housekeeping task"


def test_night_audit_creates_stayover_daily_tasks(client):
    headers = _auth_headers(client)
    room = _ensure_vacant_room(client, headers)
    outlet_id = room["outlet_id"]
    room_type_id = room["room_type_id"]

    check_in = date.today() - timedelta(days=1)
    check_out = date.today() + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Stayover Guest",
            "guest_mobile": "+919333344444",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3200,
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

    business_date = date.today()
    audit = client.post(
        "/api/v1/pms/night-audit/run",
        headers=headers,
        json={"outlet_id": outlet_id, "business_date": business_date.isoformat(), "force": True},
    )
    assert audit.status_code == 200, audit.text
    body = audit.json()
    assert body.get("daily_tasks_created", 0) >= 1

    tasks = _list_tasks(client, headers, outlet_id, room["id"])
    daily = [
        t
        for t in tasks
        if t.get("task_type") == "daily" and t.get("status") in {"pending", "in_progress"}
    ]
    assert daily, "Expected a stayover daily cleaning task after night audit"

    audit2 = client.post(
        "/api/v1/pms/night-audit/run",
        headers=headers,
        json={"outlet_id": outlet_id, "business_date": business_date.isoformat(), "force": True},
    )
    assert audit2.status_code == 200, audit2.text
    assert audit2.json()["daily_tasks_created"] == 0
