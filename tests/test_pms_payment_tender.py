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


def test_folio_payment_tender_and_reports_mix(client):
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
            "guest_name": "Tender Mix Guest",
            "guest_mobile": "+919555544433",
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

    cash = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/payments",
        headers=headers,
        json={"amount": 1000, "tender": "cash"},
    )
    assert cash.status_code == 200, cash.text
    assert any("Cash" in e["description"] for e in cash.json()["entries"] if e["entry_type"] == "payment")

    upi = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/payments",
        headers=headers,
        json={"amount": 500, "tender": "upi", "description": "Partial settle"},
    )
    assert upi.status_code == 200, upi.text
    assert any(
        e["entry_type"] == "payment" and "UPI" in e["description"] and "Partial settle" in e["description"]
        for e in upi.json()["entries"]
    )

    reports = client.get(
        "/api/v1/pms/reports/summary",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "from_date": check_in.isoformat(),
            "to_date": check_in.isoformat(),
        },
    )
    assert reports.status_code == 200, reports.text
    body = reports.json()
    assert body["payments_collected"] >= 1500
    assert body["tender_mix"]["cash"] >= 1000
    assert body["tender_mix"]["upi"] >= 500
