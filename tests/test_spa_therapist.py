"""Tests for spa therapist roster and calendar."""

from datetime import date, datetime, timedelta


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_spa_therapists_calendar_and_assign(client):
    headers = _auth_headers(client)

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    therapists = client.get("/api/v1/spa/therapists", headers=headers, params={"outlet_id": outlet_id})
    assert therapists.status_code == 200
    roster = therapists.json()
    assert len(roster) >= 2
    therapist_user_id = roster[0]["user_id"]

    target_date = (date.today() + timedelta(days=1)).isoformat()
    calendar = client.get(
        "/api/v1/spa/calendar",
        headers=headers,
        params={"outlet_id": outlet_id, "date": target_date},
    )
    assert calendar.status_code == 200
    cal_body = calendar.json()
    assert len(cal_body["therapists"]) >= 2
    assert any(col["bookings"] for col in cal_body["therapists"])

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    facial = next(row for row in services if row["name"] == "Aromatherapy Facial")

    slot_date = date.today() + timedelta(days=4)
    availability = client.get(
        f"/api/v1/spa/services/{facial['id']}/availability",
        headers=headers,
        params={"date": slot_date.isoformat()},
    ).json()
    slot = next(row for row in availability["slots"] if row["is_available"])
    booked_at = datetime.combine(
        slot_date,
        datetime.strptime(slot["start_time"], "%H:%M").time(),
    ).isoformat()

    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": facial["id"],
            "booked_at": booked_at,
            "guest_name": "Calendar Test Guest",
            "assigned_staff_id": therapist_user_id,
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]
    assert create.json()["assigned_staff_name"]

    duplicate = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": facial["id"],
            "booked_at": booked_at,
            "guest_name": "Overlap Guest",
            "assigned_staff_id": therapist_user_id,
            "party_size": 1,
        },
    )
    assert duplicate.status_code == 409

    assign = client.post(
        f"/api/v1/spa/bookings/{booking_id}/assign",
        headers=headers,
        json={"assigned_staff_id": roster[1]["user_id"]},
    )
    assert assign.status_code == 200
    assert assign.json()["assigned_staff_id"] == roster[1]["user_id"]


def test_spa_therapist_roster_crud(client, db):
    headers = _auth_headers(client)

    outlets = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()
    outlet_id = outlets["data"]["items"][0]["id"]

    roster = client.get("/api/v1/spa/therapists", headers=headers, params={"outlet_id": outlet_id}).json()
    roster_user_ids = {row["user_id"] for row in roster}

    from app.modules.users.models import User

    candidate = (
        db.query(User)
        .filter(User.is_active.is_(True), ~User.id.in_(roster_user_ids) if roster_user_ids else True)
        .order_by(User.id.asc())
        .first()
    )
    assert candidate is not None

    create = client.post(
        "/api/v1/spa/therapists",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "user_id": candidate.id,
            "title": "Junior Therapist",
            "specialties": "Facials",
            "shift_start": "10:00",
            "shift_end": "19:00",
            "calendar_color": "#06b6d4",
        },
    )
    assert create.status_code == 201
    therapist_id = create.json()["id"]
    assert create.json()["title"] == "Junior Therapist"

    duplicate = client.post(
        "/api/v1/spa/therapists",
        headers=headers,
        json={"outlet_id": outlet_id, "user_id": candidate.id},
    )
    assert duplicate.status_code == 409

    update = client.patch(
        f"/api/v1/spa/therapists/{therapist_id}",
        headers=headers,
        json={"title": "Lead Facial Therapist", "shift_end": "20:00"},
    )
    assert update.status_code == 200
    assert update.json()["title"] == "Lead Facial Therapist"
    assert update.json()["shift_end"] == "20:00"

    deactivate = client.patch(
        f"/api/v1/spa/therapists/{therapist_id}",
        headers=headers,
        json={"is_active": False},
    )
    assert deactivate.status_code == 200
    assert deactivate.json()["is_active"] is False

    active_only = client.get(
        "/api/v1/spa/therapists",
        headers=headers,
        params={"outlet_id": outlet_id},
    ).json()
    assert all(row["id"] != therapist_id for row in active_only)

    with_inactive = client.get(
        "/api/v1/spa/therapists",
        headers=headers,
        params={"outlet_id": outlet_id, "include_inactive": True},
    ).json()
    assert any(row["id"] == therapist_id for row in with_inactive)
