from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_vacant_room(client, headers, outlet_id: int, room_type_id: int, suffix: str) -> dict:
    created = client.post(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "room_number": f"UG{suffix}",
            "floor": "8",
            "status": "vacant_clean",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_cross_type_room_upgrade_on_move(client):
    headers = _auth_headers(client)
    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    assert len(room_types) >= 2, "Expected at least two room types for upgrade test"
    type_a, type_b = room_types[0]["id"], room_types[1]["id"]
    stamp = date.today().strftime("%H%M%S")
    room_a = _create_vacant_room(client, headers, outlet_id, type_a, f"A{stamp}")
    room_b = _create_vacant_room(client, headers, outlet_id, type_b, f"B{stamp}")

    check_in = date.today()
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Upgrade Guest",
            "guest_mobile": "+919888877766",
            "room_type_id": type_a,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 2500,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]
    assert create.json()["room_type_id"] == type_a

    check_in_resp = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room_a["id"]},
    )
    assert check_in_resp.status_code == 200, check_in_resp.text
    assert check_in_resp.json()["room_type_id"] == type_a

    move = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/move-room",
        headers=headers,
        json={
            "room_id": room_b["id"],
            "rate_delta": 1500,
            "notes": "Complimentary suite upgrade",
        },
    )
    assert move.status_code == 200, move.text
    detail = move.json()
    assert detail["room_id"] == room_b["id"]
    assert detail["room_type_id"] == type_b

    folio = detail.get("folio") or {}
    entries = folio.get("entries") or []
    assert any(
        "rate adjustment" in (e.get("description") or "").lower()
        and float(e.get("amount") or 0) == 1500
        for e in entries
    ), entries
    assert "upgrade/change on move" in (detail.get("notes") or "").lower()
