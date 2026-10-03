"""Tests for PMS scheduled pre-arrival reminders."""

from datetime import date, datetime, time, timedelta

from app.modules.pms.models import GuestReservation
from app.modules.pms.service import run_due_pms_reminders_all_tenants


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def _create_confirmed_reservation(
    client,
    *,
    check_in: date,
    check_out: date,
    guest_mobile: str = "+919888877777",
    guest_email: str = "pms-reminder@example.com",
) -> int:
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]
    room_types = client.get("/api/v1/housekeeping/room-types", headers=headers).json()
    room_type_id = room_types[0]["id"]

    create = client.post(
        "/api/v1/pms/reservations",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "guest_name": "Reminder Guest",
            "guest_mobile": guest_mobile,
            "guest_email": guest_email,
            "room_type_id": room_type_id,
            "check_in_date": check_in.isoformat(),
            "check_out_date": check_out.isoformat(),
            "rate_per_night": 3500,
            "auto_confirm": False,
        },
    )
    assert create.status_code == 201
    reservation_id = create.json()["id"]
    confirm = client.post(f"/api/v1/pms/reservations/{reservation_id}/confirm", headers=headers)
    assert confirm.status_code == 200
    return reservation_id


def _due_check_in_dates() -> tuple[date, date]:
    """Pick dates so 2:00 PM check-in falls in the 24h ± 60min reminder window."""
    now = datetime.utcnow()
    window_start = now + timedelta(hours=24) - timedelta(minutes=60)
    window_end = now + timedelta(hours=24) + timedelta(minutes=60)
    check_in = (now + timedelta(hours=24)).date()
    target = datetime.combine(check_in, time(14, 0))
    while target < window_start:
        check_in += timedelta(days=1)
        target = datetime.combine(check_in, time(14, 0))
    while target > window_end:
        check_in -= timedelta(days=1)
        target = datetime.combine(check_in, time(14, 0))
    return check_in, check_in + timedelta(days=2)


def test_pms_reminder_job_sends_for_due_reservation(client, db):
    check_in, check_out = _due_check_in_dates()

    reservation_id = _create_confirmed_reservation(client, check_in=check_in, check_out=check_out)

    result = run_due_pms_reminders_all_tenants(db, hours_before=24, window_minutes=60)
    assert result.reminders_sent >= 1

    reservation = db.get(GuestReservation, reservation_id)
    assert reservation is not None
    assert reservation.reminder_sent_at is not None


def test_pms_reminder_skipped_when_disabled(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    assert (
        client.patch(
            "/api/v1/settings/reminders",
            headers=headers,
            json={
                "outlet_id": outlet_id,
                "pms": {
                    "enabled": False,
                    "hours_before": 24,
                    "window_minutes": 60,
                    "send_sms": True,
                    "send_email": True,
                    "send_whatsapp": True,
                },
            },
        ).status_code
        == 200
    )

    check_in, check_out = _due_check_in_dates()

    reservation_id = _create_confirmed_reservation(client, check_in=check_in, check_out=check_out)

    result = run_due_pms_reminders_all_tenants(db, hours_before=24, window_minutes=60)
    assert result.reminders_sent == 0

    reservation = db.get(GuestReservation, reservation_id)
    assert reservation is not None
    assert reservation.reminder_sent_at is None
