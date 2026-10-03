"""Tests for in-room QR guest hub and service requests."""


def _auth_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _first_room(client, headers: dict[str, str]):
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
    return room["outlet_id"], room


def test_public_room_hub_resolves_room(client):
    headers = _auth_headers(client)
    outlet_id, room = _first_room(client, headers)
    room_number = room["room_number"]

    hub = client.get(
        "/api/v1/pms/public/room-hub",
        params={"outlet_id": outlet_id, "room_number": room_number},
    )
    assert hub.status_code == 200
    body = hub.json()
    assert body["outlet_id"] == outlet_id
    assert body["room_number"].upper() == str(room_number).upper()
    assert body["menu_url_path"].startswith("/menu-card?")
    assert "room=" in body["menu_url_path"]
    assert isinstance(body["service_catalog"], list)
    assert len(body["service_catalog"]) >= 5
    assert "wifi" in body
    assert body["stay_unlocked"] is False
    assert "spa_url_path" in body
    assert body["spa_url_path"].startswith("/book-spa")
    assert "menu_url_path" in body


def test_public_room_hub_unknown_room(client):
    headers = _auth_headers(client)
    outlet_id, _room = _first_room(client, headers)
    hub = client.get(
        "/api/v1/pms/public/room-hub",
        params={"outlet_id": outlet_id, "room_number": "NO-SUCH-ROOM-9999"},
    )
    assert hub.status_code == 404


def test_service_request_towels_creates_hk_task(client):
    headers = _auth_headers(client)
    outlet_id, room = _first_room(client, headers)
    room_number = room["room_number"]

    created = client.post(
        "/api/v1/pms/public/service-requests",
        json={
            "outlet_id": outlet_id,
            "room_number": room_number,
            "category": "towels",
            "notes": "2 bath towels please",
        },
    )
    assert created.status_code == 201
    body = created.json()
    assert body["category"] == "towels"
    assert body["status"] == "open"
    assert body["room_number"].upper() == str(room_number).upper()

    staff = client.get(
        "/api/v1/pms/service-requests",
        headers=headers,
        params={"outlet_id": outlet_id, "status": "open"},
    )
    assert staff.status_code == 200
    rows = staff.json()
    match = next(r for r in rows if r["id"] == body["id"])
    assert match["linked_task_id"] is not None
    assert match["linked_ticket_id"] is None
    assert match["category"] == "towels"


def test_service_request_issue_creates_ticket_and_fulfill(client):
    headers = _auth_headers(client)
    outlet_id, room = _first_room(client, headers)
    room_number = room["room_number"]

    created = client.post(
        "/api/v1/pms/public/service-requests",
        json={
            "outlet_id": outlet_id,
            "room_number": room_number,
            "category": "maintenance_issue",
            "notes": "AC not cooling",
        },
    )
    assert created.status_code == 201
    body = created.json()
    request_id = body["id"]

    staff = client.get(
        "/api/v1/pms/service-requests",
        headers=headers,
        params={"outlet_id": outlet_id, "status": "open"},
    )
    assert staff.status_code == 200
    match = next(r for r in staff.json() if r["id"] == request_id)
    assert match["linked_ticket_id"] is not None
    assert match["linked_task_id"] is None

    fulfill = client.post(
        f"/api/v1/pms/service-requests/{request_id}/fulfill",
        headers=headers,
        json={"staff_reply": "AC reset — all good", "notify_guest": False},
    )
    assert fulfill.status_code == 200
    assert fulfill.json()["status"] == "fulfilled"
    assert fulfill.json()["staff_reply"] == "AC reset — all good"
    assert fulfill.json()["notified"] is False

    public_list = client.get(
        "/api/v1/pms/public/service-requests",
        params={"outlet_id": outlet_id, "room_number": room_number},
    )
    assert public_list.status_code == 200
    pub = next(r for r in public_list.json() if r["id"] == request_id)
    assert pub["status"] == "fulfilled"
    assert pub["staff_reply"] == "AC reset — all good"

    staff_after = client.get(
        "/api/v1/pms/service-requests",
        headers=headers,
        params={"outlet_id": outlet_id, "status": "open"},
    )
    assert all(r["id"] != request_id for r in staff_after.json())
