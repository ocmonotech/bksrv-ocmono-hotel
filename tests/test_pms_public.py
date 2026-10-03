"""Tests for public guest room self-booking portal."""

from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    login = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert login.status_code == 200
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


def _bookable_outlet_and_room(client, headers: dict[str, str], check_in: date, check_out: date):
    outlets = client.get("/api/v1/outlets?page=1&page_size=20", headers=headers).json()["data"]["items"]
    for outlet in outlets:
        outlet_id = outlet["id"]
        room_types = client.get("/api/v1/pms/public/room-types", params={"outlet_id": outlet_id})
        if room_types.status_code != 200 or not room_types.json():
            continue
        availability = client.get(
            "/api/v1/pms/public/availability",
            params={
                "outlet_id": outlet_id,
                "check_in_date": check_in.isoformat(),
                "check_out_date": check_out.isoformat(),
            },
        )
        if availability.status_code != 200:
            continue
        for row in availability.json()["room_types"]:
            if row["available_rooms"] >= 1:
                return outlet_id, row["room_type_id"]
    raise AssertionError("No bookable outlet/room type found in seed data")


def test_public_room_booking_flow(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=14)
    check_out = check_in + timedelta(days=2)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Online Guest",
            "guest_mobile": "+91 90000 11111",
            "guest_email": "room.guest@example.com",
            "adults": 2,
            "children": 0,
            "notes": "Late arrival expected",
            "card_last4": "4242",
            "hold_amount": 1500,
        },
    )
    assert booking.status_code == 201
    body = booking.json()
    assert body["status"] == "confirmed"
    assert body["confirmation_number"].startswith("RES-")
    assert body["nights"] == 2
    assert body["total_amount"] > 0
    assert body["payment_hold_ref"]
    assert body["card_last4"] == "4242"
    assert body["deposit_status"] == "held"
    assert float(body["deposit_amount"]) == 1500.0
    assert "confirmed" in body["message"].lower()

    staff_list = client.get(
        "/api/v1/pms/reservations",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert staff_list.status_code == 200
    assert any(row["id"] == body["reservation_id"] for row in staff_list.json()["data"]["items"])

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={
            "confirmation_number": body["confirmation_number"],
            "guest_mobile": "9000011111",
        },
    )
    assert lookup.status_code == 200
    status_body = lookup.json()
    assert status_body["confirmation_number"] == body["confirmation_number"]
    assert status_body["guest_name"] == "Online Guest"
    assert status_body["can_place_hold"] is False
    assert status_body["payment_hold_ref"] == body["payment_hold_ref"]


def test_public_room_booking_card_hold_decline(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=20)
    check_out = check_in + timedelta(days=1)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Declined Guest",
            "guest_mobile": "+91 90000 22222",
            "card_last4": "0000",
            "hold_amount": 500,
        },
    )
    assert booking.status_code == 409
    detail = booking.json().get("detail") or booking.json().get("message") or ""
    assert "declined" in str(detail).lower()


def test_public_lookup_and_late_card_hold(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=25)
    check_out = check_in + timedelta(days=2)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Later Pay Guest",
            "guest_mobile": "+91 98888 77777",
            "notes": "Will pay later",
        },
    )
    assert booking.status_code == 201
    conf = booking.json()["confirmation_number"]

    bad = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": "0000000000"},
    )
    assert bad.status_code == 404

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": "+91 98888 77777"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["can_place_hold"] is True

    hold = client.post(
        "/api/v1/pms/public/reservations/payment/hold",
        json={
            "confirmation_number": conf,
            "guest_mobile": "9888877777",
            "card_last4": "1111",
            "hold_amount": 800,
        },
    )
    assert hold.status_code == 200
    hold_body = hold.json()
    assert hold_body["payment_hold_ref"]
    assert hold_body["deposit_status"] == "held"
    assert hold_body["status"] == "confirmed"
    assert hold_body["can_place_hold"] is False
    assert hold_body["can_cancel"] is True
    assert "confirmed" in hold_body["message"].lower()

    cancelled = client.post(
        "/api/v1/pms/public/reservations/cancel",
        json={
            "confirmation_number": conf,
            "guest_mobile": "+91 98888 77777",
            "reason": "Changed plans",
        },
    )
    assert cancelled.status_code == 200
    cancel_body = cancelled.json()
    assert cancel_body["status"] == "cancelled"
    assert cancel_body["can_cancel"] is False
    assert cancel_body["payment_hold_ref"] is None


def test_public_booking_staff_confirm(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=28)
    check_out = check_in + timedelta(days=1)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Confirm Me Guest",
            "guest_mobile": "+91 97777 66666",
            "guest_email": "confirm.me@example.com",
            "notes": "online booking",
        },
    )
    assert booking.status_code == 201
    assert booking.json()["status"] == "pending"
    res_id = booking.json()["reservation_id"]
    conf = booking.json()["confirmation_number"]

    confirm = client.post(
        f"/api/v1/pms/reservations/{res_id}/confirm",
        headers=headers,
        json={"send_sms": False, "send_email": False, "send_whatsapp": False},
    )
    assert confirm.status_code == 200
    assert confirm.json()["status"] == "confirmed"

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": "9777766666"},
    )
    assert lookup.status_code == 200
    assert lookup.json()["status"] == "confirmed"
    assert lookup.json()["can_cancel"] is True
    assert lookup.json()["can_modify_stay"] is True


def test_public_modify_stay(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=40)
    check_out = check_in + timedelta(days=2)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Modify Stay Guest",
            "guest_mobile": "+91 95555 44444",
            "guest_email": "modify.stay@example.com",
            "adults": 2,
            "children": 0,
            "card_last4": "4242",
            "hold_amount": 1000,
        },
    )
    assert booking.status_code == 201, booking.text
    conf = booking.json()["confirmation_number"]
    mobile = "9555544444"
    original_total = float(booking.json()["total_amount"])

    new_out = check_in + timedelta(days=3)
    modified = client.post(
        "/api/v1/pms/public/reservations/modify",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "check_out_date": new_out.isoformat(),
            "adults": 3,
            "note": "Extending one night",
        },
    )
    assert modified.status_code == 200, modified.text
    body = modified.json()
    assert body["check_out_date"] == new_out.isoformat()
    assert body["nights"] == 3
    assert body["adults"] == 3
    assert float(body["total_amount"]) > original_total
    assert body["can_modify_stay"] is True
    assert "updated" in body["message"].lower()

    bad = client.post(
        "/api/v1/pms/public/reservations/modify",
        json={
            "confirmation_number": conf,
            "guest_mobile": "0000000000",
            "check_out_date": new_out.isoformat(),
        },
    )
    assert bad.status_code == 404

    empty = client.post(
        "/api/v1/pms/public/reservations/modify",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
        },
    )
    assert empty.status_code == 409


def test_public_stay_modifiers(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=50)
    check_out = check_in + timedelta(days=2)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Stay Mods Guest",
            "guest_mobile": "+91 93333 22222",
            "guest_email": "stay.mods@example.com",
            "adults": 2,
            "children": 0,
            "card_last4": "4242",
            "hold_amount": 1000,
        },
    )
    assert booking.status_code == 201, booking.text
    conf = booking.json()["confirmation_number"]
    mobile = "9333322222"

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": mobile},
    )
    assert lookup.status_code == 200
    assert lookup.json()["can_request_early_check_in"] is True
    assert lookup.json()["can_request_late_check_out"] is True
    assert lookup.json()["early_check_in"] is False

    early = client.post(
        "/api/v1/pms/public/reservations/stay-modifiers",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "early_check_in": True,
        },
    )
    assert early.status_code == 200, early.text
    assert early.json()["early_check_in"] is True
    assert early.json()["can_request_early_check_in"] is False

    late = client.post(
        "/api/v1/pms/public/reservations/stay-modifiers",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "late_check_out": True,
        },
    )
    assert late.status_code == 200, late.text
    assert late.json()["late_check_out"] is True
    assert late.json()["can_request_late_check_out"] is False
    assert late.json()["early_check_in"] is True

    again = client.post(
        "/api/v1/pms/public/reservations/stay-modifiers",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "early_check_in": True,
        },
    )
    assert again.status_code == 409

    empty = client.post(
        "/api/v1/pms/public/reservations/stay-modifiers",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
        },
    )
    assert empty.status_code == 409


def test_public_special_request(client):
    headers = _auth_headers(client)
    check_in = date.today() + timedelta(days=55)
    check_out = check_in + timedelta(days=2)
    outlet_id, room_type_id = _bookable_outlet_and_room(client, headers, check_in, check_out)

    booking = client.post(
        "/api/v1/pms/public/reservations",
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "guest_name": "Special Req Guest",
            "guest_mobile": "+91 92222 11111",
            "guest_email": "special.req@example.com",
            "adults": 2,
            "children": 0,
            "card_last4": "4242",
            "hold_amount": 1000,
        },
    )
    assert booking.status_code == 201, booking.text
    conf = booking.json()["confirmation_number"]
    mobile = "9222211111"

    lookup = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": mobile},
    )
    assert lookup.status_code == 200
    assert lookup.json()["can_add_special_request"] is True
    assert lookup.json()["special_requests"] == []

    added = client.post(
        "/api/v1/pms/public/reservations/special-request",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "request": "High floor near the elevator",
        },
    )
    assert added.status_code == 200, added.text
    assert added.json()["special_requests"] == ["High floor near the elevator"]
    assert "noted" in added.json()["message"].lower()

    dup = client.post(
        "/api/v1/pms/public/reservations/special-request",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "request": "high floor near the elevator",
        },
    )
    assert dup.status_code == 409

    staff = client.get(
        "/api/v1/pms/reservations",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    )
    assert staff.status_code == 200
    row = next(r for r in staff.json()["data"]["items"] if r["confirmation_number"] == conf)
    assert "Guest special request: High floor near the elevator" in (row.get("notes") or "")


def test_public_stay_feedback_after_checkout(client):
    headers = _auth_headers(client)
    rooms_resp = client.get("/api/v1/housekeeping/rooms", headers=headers, params={"page_size": 100})
    assert rooms_resp.status_code == 200
    rooms = rooms_resp.json().get("data", rooms_resp.json()).get("items", [])
    room = next(
        (r for r in rooms if str(r.get("status", "")).lower() in {"vacant_clean", "vacant_dirty"}),
        None,
    )
    assert room, "Expected a vacant hotel room"
    outlet_id = room["outlet_id"]
    room_type_id = room["room_type_id"]

    check_in = date.today()
    check_out = check_in + timedelta(days=1)
    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Feedback Guest",
            "guest_mobile": "+919100011122",
            "guest_email": "feedback.guest@example.com",
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3000,
            "auto_confirm": True,
        },
    )
    assert create.status_code == 201, create.text
    reservation_id = create.json()["id"]
    conf = create.json()["confirmation_number"]
    mobile = "9100011122"

    before = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": mobile},
    )
    assert before.status_code == 200
    assert before.json()["can_submit_feedback"] is False

    checkin = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-in",
        headers=headers,
        json={"room_id": room["id"]},
    )
    assert checkin.status_code == 200, checkin.text

    checkout = client.post(
        f"/api/v1/pms/reservations/{reservation_id}/check-out",
        headers=headers,
        json={"force_settle": True},
    )
    assert checkout.status_code == 200, checkout.text

    ready = client.get(
        "/api/v1/pms/public/reservations/lookup",
        params={"confirmation_number": conf, "guest_mobile": mobile},
    )
    assert ready.status_code == 200
    assert ready.json()["status"] == "checked_out"
    assert ready.json()["can_submit_feedback"] is True

    feedback = client.post(
        "/api/v1/pms/public/reservations/feedback",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "rating": 5,
            "comment": "Lovely stay",
        },
    )
    assert feedback.status_code == 200, feedback.text
    assert feedback.json()["feedback_rating"] == 5
    assert feedback.json()["feedback_comment"] == "Lovely stay"
    assert feedback.json()["can_submit_feedback"] is False

    again = client.post(
        "/api/v1/pms/public/reservations/feedback",
        json={
            "confirmation_number": conf,
            "guest_mobile": mobile,
            "rating": 4,
        },
    )
    assert again.status_code == 409
