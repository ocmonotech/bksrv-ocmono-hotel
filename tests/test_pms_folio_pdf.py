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


def _create_reservation_with_email(client, headers, outlet_id: int, room_type_id: int) -> dict:
    check_in = date.today() + timedelta(days=55)
    check_out = check_in + timedelta(days=2)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Folio PDF Guest",
            "guest_email": "folio.guest@example.com",
            "guest_mobile": "+919444455566",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 4500,
            "deposit_amount": 1000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    return create.json()


def test_folio_pdf_download(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation_with_email(client, headers, outlet_id, room_type_id)

    response = client.get(
        f"/api/v1/pms/reservations/{reservation['id']}/folio/pdf",
        headers=headers,
    )
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/pdf")
    assert response.content[:4] == b"%PDF"
    assert "attachment" in response.headers.get("content-disposition", "")


def test_folio_email_statement(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation_with_email(client, headers, outlet_id, room_type_id)

    response = client.post(
        f"/api/v1/pms/reservations/{reservation['id']}/folio/email",
        headers=headers,
        json={"note": "Please review your charges"},
    )
    assert response.status_code == 200, response.text
    payload = response.json()
    assert payload["sent_to"] == "folio.guest@example.com"
    assert payload["folio_number"]
    assert "emailed" in payload["message"].lower()


def test_public_folio_pdf_download(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation_with_email(client, headers, outlet_id, room_type_id)

    ok = client.get(
        "/api/v1/pms/public/reservations/folio/pdf",
        params={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": reservation["guest_mobile"],
        },
    )
    assert ok.status_code == 200
    assert ok.headers["content-type"].startswith("application/pdf")
    assert ok.content[:4] == b"%PDF"

    bad = client.get(
        "/api/v1/pms/public/reservations/folio/pdf",
        params={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": "0000000000",
        },
    )
    assert bad.status_code == 404

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": reservation["guest_mobile"],
        },
    )
    assert lookup.status_code == 200
    assert lookup.json()["has_folio"] is True
    assert lookup.json()["folio_number"]
    assert lookup.json()["can_email_folio"] is True


def test_public_email_folio_statement(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    reservation = _create_reservation_with_email(client, headers, outlet_id, room_type_id)

    ok = client.post(
        "/api/v1/pms/public/reservations/folio/email",
        json={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": reservation["guest_mobile"],
        },
    )
    assert ok.status_code == 200
    payload = ok.json()
    assert payload["sent_to"] == reservation["guest_email"]
    assert payload["folio_number"]
    assert "emailed" in payload["message"].lower()

    bad = client.post(
        "/api/v1/pms/public/reservations/folio/email",
        json={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": "0000000000",
        },
    )
    assert bad.status_code == 404


def test_public_email_folio_requires_guest_email(client):
    headers = _auth_headers(client)
    outlet_id, room_type_id = _hotel_outlet_and_room_type(client, headers)
    check_in = date.today() + timedelta(days=20)
    check_out = check_in + timedelta(days=1)
    created = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "guest_name": "No Email Guest",
            "guest_mobile": "9123456780",
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 4500,
            "deposit_amount": 500,
            "auto_confirm": True,
        },
    )
    assert created.status_code == 201, created.text
    reservation = created.json()
    assert not reservation.get("guest_email")

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": reservation["guest_mobile"],
        },
    )
    assert lookup.status_code == 200
    assert lookup.json()["has_folio"] is True
    assert lookup.json()["can_email_folio"] is False

    conflict = client.post(
        "/api/v1/pms/public/reservations/folio/email",
        json={
            "confirmation_number": reservation["confirmation_number"],
            "guest_mobile": reservation["guest_mobile"],
        },
    )
    assert conflict.status_code == 409
