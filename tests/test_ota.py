from datetime import date, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _andheri_booking_com(client, headers: dict[str, str]) -> dict:
    integrations = client.get("/api/v1/ota/integrations?page=1&page_size=20", headers=headers)
    assert integrations.status_code == 200
    items = integrations.json()["data"]["items"]
    return next(
        row
        for row in items
        if row["platform"] == "booking_com"
        and (row.get("external_property_id") or "").startswith("BCOM-ANDHERI")
    )


def test_ota_platforms_integrations_and_simulate(client):
    headers = _auth_headers(client)

    platforms = client.get("/api/v1/ota/platforms", headers=headers)
    assert platforms.status_code == 200
    platform_list = platforms.json()
    assert len(platform_list) >= 3
    assert any(row["platform"] == "booking_com" for row in platform_list)

    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]
    assert booking_com["mapping_count"] >= 1

    mappings = client.get(
        f"/api/v1/ota/integrations/{integration_id}/room-mappings",
        headers=headers,
    )
    assert mappings.status_code == 200
    assert len(mappings.json()) >= 1

    check_in = date.today() + timedelta(days=14)
    check_out = check_in + timedelta(days=2)
    simulate = client.post(
        f"/api/v1/ota/integrations/{integration_id}/simulate-reservation",
        headers=headers,
        json={
            "guest_name": "OTA Webhook Guest",
            "guest_mobile": "+919911122233",
            "external_room_type_id": "STD",
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )
    assert simulate.status_code == 201
    reservation = simulate.json()
    assert reservation["guest_name"] == "OTA Webhook Guest"
    assert reservation["platform"] == "booking_com"
    assert reservation["reservation_status"] in {"confirmed", "pending"}

    listing = client.get("/api/v1/ota/reservations?page=1&page_size=20", headers=headers)
    assert listing.status_code == 200
    listed = listing.json()["data"]["items"]
    assert any(row["external_reservation_id"] == reservation["external_reservation_id"] for row in listed)

    pms_detail = client.get(
        f"/api/v1/pms/reservations/{reservation['guest_reservation_id']}",
        headers=headers,
    )
    assert pms_detail.status_code == 200
    assert pms_detail.json()["source"] == "ota_booking_com"


def test_ota_simulate_modify_and_cancel(client):
    headers = _auth_headers(client)
    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]

    check_in = date.today() + timedelta(days=21)
    check_out = check_in + timedelta(days=2)
    simulate = client.post(
        f"/api/v1/ota/integrations/{integration_id}/simulate-reservation",
        headers=headers,
        json={
            "guest_name": "OTA Modify Cancel Guest",
            "guest_mobile": "+919922233344",
            "external_room_type_id": "STD",
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
        },
    )
    assert simulate.status_code == 201
    reservation = simulate.json()
    external_id = reservation["external_reservation_id"]
    guest_reservation_id = reservation["guest_reservation_id"]

    new_checkout = (check_out + timedelta(days=1)).isoformat()
    modify = client.post(
        f"/api/v1/ota/integrations/{integration_id}/simulate-modify",
        headers=headers,
        json={
            "external_reservation_id": external_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": new_checkout,
            "notes": "pytest OTA modify",
        },
    )
    assert modify.status_code == 200
    modified = modify.json()
    assert modified["check_out_date"] == new_checkout
    assert modified["reservation_status"] in {"confirmed", "pending", "modified"}

    pms_after_modify = client.get(
        f"/api/v1/pms/reservations/{guest_reservation_id}",
        headers=headers,
    )
    assert pms_after_modify.status_code == 200
    assert pms_after_modify.json()["check_out_date"] == new_checkout

    cancel = client.post(
        f"/api/v1/ota/integrations/{integration_id}/simulate-cancel",
        headers=headers,
        json={
            "external_reservation_id": external_id,
            "notes": "pytest OTA cancel",
        },
    )
    assert cancel.status_code == 200
    assert cancel.json()["reservation_status"] == "cancelled"

    pms_after_cancel = client.get(
        f"/api/v1/pms/reservations/{guest_reservation_id}",
        headers=headers,
    )
    assert pms_after_cancel.status_code == 200
    assert pms_after_cancel.json()["status"] == "cancelled"


def test_ota_ari_preview_and_push(client):
    headers = _auth_headers(client)

    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]

    preview = client.get(
        f"/api/v1/ota/integrations/{integration_id}/ari-preview?max_days=7",
        headers=headers,
    )
    assert preview.status_code == 200
    body = preview.json()
    assert body["integration_id"] == integration_id
    assert len(body["room_types"]) >= 1
    first_room = body["room_types"][0]
    assert len(first_room["days"]) == 7
    assert first_room["days"][0]["rate"] > 0

    push = client.post(
        f"/api/v1/ota/integrations/{integration_id}/push-ari",
        headers=headers,
        json={"max_days": 7},
    )
    assert push.status_code == 200
    push_body = push.json()
    assert push_body["success"] is True
    assert push_body["sync_log_id"] > 0
    assert push_body["external_reference"]

    logs = client.get(
        f"/api/v1/ota/integrations/{integration_id}/sync-logs?page=1&page_size=10",
        headers=headers,
    )
    assert logs.status_code == 200
    log_items = logs.json()["data"]["items"]
    assert any(row["id"] == push_body["sync_log_id"] for row in log_items)


def test_ota_ari_sends_structured_restrictions(client):
    """CTA / min-stay must not collapse into false stop-sell zero inventory."""
    headers = _auth_headers(client)
    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]
    outlet_id = booking_com["outlet_id"]

    mappings = client.get(
        f"/api/v1/ota/integrations/{integration_id}/room-mappings",
        headers=headers,
    )
    assert mappings.status_code == 200
    room_type_id = mappings.json()[0]["room_type_id"]
    target = date.today() + timedelta(days=5)

    override = client.patch(
        "/api/v1/pms/calendar/rates",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "room_type_id": room_type_id,
            "date": target.isoformat(),
            "cta": True,
            "min_stay": 2,
            "stop_sell": False,
        },
    )
    assert override.status_code == 200

    availability = client.get(
        "/api/v1/pms/availability",
        headers=headers,
        params={
            "outlet_id": outlet_id,
            "check_in_date": target.isoformat(),
            "check_out_date": (target + timedelta(days=1)).isoformat(),
        },
    )
    assert availability.status_code == 200
    avail_row = next(
        r for r in availability.json()["room_types"] if r["room_type_id"] == room_type_id
    )
    assert avail_row["available_rooms"] == 0

    preview = client.get(
        f"/api/v1/ota/integrations/{integration_id}/ari-preview",
        headers=headers,
        params={
            "start_date": target.isoformat(),
            "end_date": target.isoformat(),
            "max_days": 1,
        },
    )
    assert preview.status_code == 200
    room = next(
        r for r in preview.json()["room_types"] if r["room_type_id"] == room_type_id
    )
    assert len(room["days"]) == 1
    day = room["days"][0]
    assert day["cta"] is True
    assert day["min_stay"] == 2
    assert day["stop_sell"] is False
    assert day["available_rooms"] > 0


def test_ota_auto_ari_push(client):
    headers = _auth_headers(client)

    booking_com = _andheri_booking_com(client, headers)
    outlet_id = booking_com["outlet_id"]

    patch = client.patch(
        f"/api/v1/ota/integrations/{booking_com['id']}",
        headers=headers,
        json={"auto_push_availability": True},
    )
    assert patch.status_code == 200
    assert patch.json()["auto_push_availability"] is True

    push = client.post(
        "/api/v1/ota/push-auto-ari",
        headers=headers,
        params={"outlet_id": outlet_id, "max_days": 7},
    )
    assert push.status_code == 200
    body = push.json()
    assert body["integrations_pushed"] >= 1
    assert body["successes"] >= 1
    assert body["results"][0]["success"] is True


def test_ota_pull_reservations(client):
    headers = _auth_headers(client)

    booking_com = _andheri_booking_com(client, headers)
    integration_id = booking_com["id"]

    pull = client.post(
        f"/api/v1/ota/integrations/{integration_id}/pull-reservations",
        headers=headers,
    )
    assert pull.status_code == 200
    body = pull.json()
    if not body["success"]:
        raise AssertionError(body.get("results") or body["message"])
    assert body["pulled_count"] >= 1
    assert body["created_count"] >= 1
    assert body["sync_log_id"] > 0
    assert body["results"][0]["guest_reservation_id"] is not None

    logs = client.get(
        f"/api/v1/ota/integrations/{integration_id}/sync-logs?page=1&page_size=10",
        headers=headers,
    )
    assert logs.status_code == 200
    log_items = logs.json()["data"]["items"]
    assert any(
        row["id"] == body["sync_log_id"]
        and row["sync_type"] in {"reservation_pull", "RESERVATION_PULL"}
        for row in log_items
    )

    pull_again = client.post(
        f"/api/v1/ota/integrations/{integration_id}/pull-reservations",
        headers=headers,
    )
    assert pull_again.status_code == 200
    assert pull_again.json()["success"] is True
