from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _ensure_vacant_room(client, headers, *, room_type_id: int | None = None) -> dict:
    rooms_resp = client.get(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        params={"page_size": 100},
    )
    assert rooms_resp.status_code == 200
    payload = rooms_resp.json()
    rooms = payload.get("data", payload).get("items", [])
    for room in rooms:
        if room_type_id is not None and room.get("room_type_id") != room_type_id:
            continue
        if str(room.get("status", "")).lower() in {"vacant_clean", "vacant_dirty"}:
            return room

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    assert room_types, "Expected housekeeping room types in seed"
    target_type = room_type_id or room_types[0]["id"]
    # Prefer a type that fits 4 guests when creating for occupancy tests
    if room_type_id is None:
        target_type = next(
            (rt["id"] for rt in room_types if int(rt.get("max_occupancy") or 0) >= 4),
            room_types[0]["id"],
        )

    created = client.post(
        "/api/v1/housekeeping/rooms",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": target_type,
            "room_number": f"XP{date.today().strftime('%H%M%S')}",
            "floor": "9",
            "status": "vacant_clean",
        },
    )
    assert created.status_code == 201, created.text
    return created.json()


def test_extra_person_charges_on_check_in(client):
    headers = _auth_headers(client)
    room = _ensure_vacant_room(client, headers)
    outlet_id = room["outlet_id"]
    room_type_id = room["room_type_id"]

    # Ensure room type allows 4 guests
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    rt = next(r for r in room_types if r["id"] == room_type_id)
    if int(rt.get("max_occupancy") or 0) < 4:
        patch = client.patch(
            f"/api/v1/housekeeping/room-types/{room_type_id}",
            headers=headers,
            json={"max_occupancy": 4},
        )
        assert patch.status_code == 200, patch.text

    code = f"XP{date.today().strftime('%m%d%H%M%S')}"
    plan = client.post(
        "/api/v1/pms/rate-plans",
        headers=headers,
        json={
            "room_type_id": room_type_id,
            "name": "Extra Person Rack",
            "code": code,
            "rate_per_night": 2000,
            "is_default": False,
            "included_adults": 2,
            "included_children": 0,
            "extra_adult_rate": 500,
            "extra_child_rate": 250,
        },
    )
    assert plan.status_code == 201, plan.text
    plan_id = plan.json()["id"]
    assert float(plan.json()["extra_adult_rate"]) == 500

    check_in = date.today()
    check_out = check_in + timedelta(days=2)
    # 3 adults → 1 extra adult × ₹500 × 2 nights = ₹1000; 1 child × ₹250 × 2 = ₹500
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Extra Person Guest",
            "guest_mobile": "+919777766655",
            "room_type_id": room_type_id,
            "rate_plan_id": plan_id,
            "rate_per_night": 2000,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "adults": 3,
            "children": 1,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    body = create.json()
    assert float(body["total_amount"]) == 2000 * 2 + 1000 + 500
    assert "extra person" in (body.get("notes") or "").lower()

    check_in_resp = client.post(
        f"/api/v1/pms/reservations/{body['id']}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert check_in_resp.status_code == 200, check_in_resp.text
    folio = check_in_resp.json().get("folio") or {}
    entries = folio.get("entries") or []
    extras = [e for e in entries if "extra person" in (e.get("description") or "").lower()]
    assert len(extras) == 2
    assert sum(float(e["amount"]) for e in extras) == 1500
