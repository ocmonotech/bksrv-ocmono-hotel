"""Tests for banquet automation triggers and scheduled reminders."""

from datetime import date, datetime, timedelta

from app.modules.automation.models import AutomationRule, AutomationRun, AutomationTriggerType
from app.modules.banquet.models import BanquetBooking
from app.modules.banquet.service import run_due_banquet_reminders_all_tenants


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_banquet_confirm_dispatches_automation(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    before_runs = (
        db.query(AutomationRun)
        .join(AutomationRule)
        .filter(AutomationRule.trigger_type == AutomationTriggerType.BANQUET_BOOKING_CONFIRMED)
        .count()
    )

    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    ballroom = next(row for row in venues if row["name"] == "Grand Ballroom")

    event_date = date.today() + timedelta(days=10)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Automation Banquet Event",
            "event_type": "corporate",
            "event_date": event_date.isoformat(),
            "start_time": "18:00",
            "end_time": "23:00",
            "guest_count": 100,
            "contact_name": "Automation Guest",
            "contact_phone": "+91 93333 77777",
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    confirm = client.post(f"/api/v1/banquet/bookings/{booking_id}/confirm", headers=headers, json={})
    assert confirm.status_code == 200

    after_runs = (
        db.query(AutomationRun)
        .join(AutomationRule)
        .filter(AutomationRule.trigger_type == AutomationTriggerType.BANQUET_BOOKING_CONFIRMED)
        .count()
    )
    assert after_runs > before_runs


def test_banquet_reminder_job_sends_for_due_booking(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    venues = client.get(
        "/api/v1/banquet/venues",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    ballroom = next(row for row in venues if row["name"] == "Grand Ballroom")

    event_at = datetime.utcnow() + timedelta(hours=24)
    event_at = event_at.replace(minute=0, second=0, microsecond=0)
    create = client.post(
        "/api/v1/banquet/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "venue_id": ballroom["id"],
            "title": "Reminder Banquet Event",
            "event_type": "wedding",
            "event_date": event_at.date().isoformat(),
            "start_time": event_at.strftime("%H:%M"),
            "end_time": "23:00",
            "guest_count": 120,
            "contact_name": "Reminder Guest",
            "contact_phone": "+91 94444 88888",
            "contact_email": "banquet-reminder@example.com",
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]
    assert client.post(f"/api/v1/banquet/bookings/{booking_id}/confirm", headers=headers, json={}).status_code == 200

    result = run_due_banquet_reminders_all_tenants(db, hours_before=24, window_minutes=60)
    assert result.reminders_sent >= 1

    booking = db.get(BanquetBooking, booking_id)
    assert booking is not None
    assert booking.reminder_sent_at is not None
