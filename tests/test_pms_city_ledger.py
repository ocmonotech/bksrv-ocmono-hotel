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
            "room_number": f"CL{date.today().strftime('%H%M%S')}",
            "floor": "6",
            "status": "vacant_clean",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_city_ledger_transfer_and_settle(client):
    headers = _auth_headers(client)
    room = _ensure_vacant_room(client, headers)
    outlet_id = room["outlet_id"]

    check_in = date.today()
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "City Ledger Guest",
            "guest_mobile": "+919555544433",
            "room_type_id": room["room_type_id"],
            "check_in_date": check_in.isoformat(),
            "check_out_date": (check_in + timedelta(days=1)).isoformat(),
            "rate_per_night": 4000,
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
    folio_balance = float(ci.json()["folio"]["balance"])
    assert folio_balance > 1000

    transfer_amt = 1500.0
    transfer = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/transfer-to-city-ledger",
        headers=headers,
        json={
            "amount": transfer_amt,
            "company_name": "Acme Corp",
            "notes": "Room + tax company share",
        },
    )
    assert transfer.status_code == 200, transfer.text
    body = transfer.json()
    assert float(body["folio"]["balance"]) == round(folio_balance - transfer_amt, 2)
    cl = body["city_ledger"]
    assert cl["company_name"] == "Acme Corp"
    assert float(cl["balance"]) == transfer_amt
    assert cl["status"] == "open"
    assert cl["reference"].startswith("CL-")

    detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert detail.status_code == 200
    entries = detail.json().get("city_ledger_entries") or []
    assert any(e["id"] == cl["id"] for e in entries)

    listed = client.get(
        "/api/v1/pms/city-ledger",
        headers=headers,
        params={"outlet_id": outlet_id, "status": "open"},
    )
    assert listed.status_code == 200
    assert any(e["id"] == cl["id"] for e in listed.json())

    settle = client.post(
        f"/api/v1/pms/city-ledger/{cl['id']}/settle",
        headers=headers,
        json={"amount": 500, "tender": "upi"},
    )
    assert settle.status_code == 200, settle.text
    assert settle.json()["status"] == "partial"
    assert float(settle.json()["balance"]) == 1000

    settle_rest = client.post(
        f"/api/v1/pms/city-ledger/{cl['id']}/settle",
        headers=headers,
        json={"tender": "card"},
    )
    assert settle_rest.status_code == 200, settle_rest.text
    assert settle_rest.json()["status"] == "settled"
    assert float(settle_rest.json()["balance"]) == 0
