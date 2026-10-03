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


def test_group_creates_master_folio_with_shared_deposit(client):
    headers = _auth_headers(client)
    outlet_id, _ = _hotel_outlet_and_room_type(client, headers)

    create = client.post(
        "/api/v1/pms/groups",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "name": "Wedding Block",
            "shared_deposit": 25000,
        },
    )
    assert create.status_code == 201, create.text
    payload = create.json()
    assert payload["master_folio"] is not None
    assert payload["master_folio"]["group_id"] == payload["id"]
    assert payload["master_folio"]["reservation_id"] is None
    assert float(payload["master_folio"]["balance"]) == -25000.0  # deposit reduces balance
    assert any(e["entry_type"] == "deposit" for e in payload["master_folio"]["entries"])


def test_group_master_charge_and_transfer(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)

    group = client.post(
        "/api/v1/pms/groups",
        headers=headers,
        json={"outlet_id": outlet_id, "name": "Conference Block", "shared_deposit": 0},
    ).json()
    group_id = group["id"]

    check_in = date.today() + timedelta(days=60)
    check_out = check_in + timedelta(days=2)
    rooming = client.post(
        f"/api/v1/pms/groups/{group_id}/reservations",
        headers=headers,
        json={
            "auto_confirm": True,
            "stays": [
                {
                    "guest_name": "Room Guest One",
                    "guest_mobile": "+919777788899",
                    "room_type_id": room_type_id,
                    "check_in_date": check_in.isoformat(),
                    "check_out_date": check_out.isoformat(),
                    "rate_per_night": 4000,
                }
            ],
        },
    )
    assert rooming.status_code == 200, rooming.text
    reservation_id = rooming.json()["reservations"][0]["id"]

    # Post a charge on the room folio first
    charge = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/folio/charges",
        headers=headers,
        json={"entry_type": "adjustment", "description": "Minibar", "amount": 500},
    )
    assert charge.status_code == 200

    master_charge = client.post(
        f"/api/v1/pms/groups/{group_id}/folio/charges",
        headers=headers,
        json={"entry_type": "banquet_charge", "description": "Hall rental", "amount": 15000},
    )
    assert master_charge.status_code == 200
    assert float(master_charge.json()["balance"]) == 15000.0

    transfer = client.post(
        f"/api/v1/pms/groups/{group_id}/folio/transfer-from-room",
        headers=headers,
        json={"reservation_id": reservation_id, "amount": 500},
    )
    assert transfer.status_code == 200, transfer.text
    master = transfer.json()["master_folio"]
    assert float(master["balance"]) == 15500.0

    room_detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert room_detail.status_code == 200
    # Room charge 500 then transfer payment 500 → balance 0
    assert float(room_detail.json()["folio"]["balance"]) == 0.0
