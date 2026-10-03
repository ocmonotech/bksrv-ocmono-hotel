from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_pms_dashboard_and_reservations(client):
    headers = _auth_headers(client)
    dash = client.get("/api/v1/pms/dashboard", headers=headers)
    assert dash.status_code == 200
    data = dash.json()
    assert "arrivals_today" in data
    assert "occupancy_rate" in data

    listing = client.get("/api/v1/pms/reservations", headers=headers)
    assert listing.status_code == 200
    payload = listing.json()
    assert payload["ok"] is True
    assert "items" in payload["data"]


def test_create_and_confirm_reservation(client):
    headers = _auth_headers(client)

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    assert room_types, "Expected housekeeping room types in seed"
    room_type_id = room_types[0]["id"]

    check_in = date.today() + timedelta(days=10)
    check_out = check_in + timedelta(days=2)

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Test Guest",
            "guest_mobile": "+919999999999",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3500,
            "auto_confirm": False,
        },
    )
    assert create.status_code == 201
    reservation = create.json()
    reservation_id = reservation["id"]
    assert reservation["status"] == "pending"

    confirm = client.post(f"/api/v1/pms/reservations/{reservation_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    detail = client.get(f"/api/v1/pms/reservations/{reservation_id}", headers=headers)
    assert detail.status_code == 200
    assert detail.json()["folio"] is not None


def test_in_house_guests_and_post_to_room(client):
    headers = _auth_headers(client)

    in_house = client.get("/api/v1/pms/in-house", headers=headers)
    assert in_house.status_code == 200
    guests = in_house.json()
    assert isinstance(guests, list)
    assert len(guests) >= 1
    guest = guests[0]
    reservation_id = guest["reservation_id"]

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    menu = client.get(f"/api/v1/menu/outlets/{outlet_id}/active-menu", headers=headers).json()
    menu_item_id = menu["categories"][0]["items"][0]["id"]

    order = client.post(
        "/api/v1/pos/orders",
        headers=headers,
        json={"outlet_id": outlet_id, "order_type": "dine_in"},
    )
    assert order.status_code == 201
    order_id = order.json()["id"]

    add_item = client.post(
        f"/api/v1/pos/orders/{order_id}/items",
        headers=headers,
        json={"menu_item_id": menu_item_id, "quantity": 2},
    )
    assert add_item.status_code == 200

    bill = client.post(f"/api/v1/pos/orders/{order_id}/bill", headers=headers)
    assert bill.status_code == 201
    bill_id = bill.json()["id"]
    bill_total = float(bill.json()["grand_total"])

    post = client.post(
        "/api/v1/pms/post-to-room",
        headers=headers,
        json={"bill_id": bill_id, "reservation_id": reservation_id},
    )
    assert post.status_code == 201
    payload = post.json()
    assert payload["amount"] == bill_total
    assert payload["folio"]["balance"] > 0

    folio_entries = [entry["entry_type"] for entry in payload["folio"]["entries"]]
    assert "pos_charge" in folio_entries

    bill_detail = client.get(f"/api/v1/pos/bills?outlet_id={outlet_id}", headers=headers)
    assert bill_detail.status_code == 200
    paid_bill = next(row for row in bill_detail.json() if row["id"] == bill_id)
    assert paid_bill["payment_status"] == "paid"

    duplicate = client.post(
        "/api/v1/pms/post-to-room",
        headers=headers,
        json={"bill_id": bill_id, "reservation_id": reservation_id},
    )
    assert duplicate.status_code == 409
