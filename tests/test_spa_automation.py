"""Tests for spa automation triggers and scheduled reminders."""

from datetime import datetime, timedelta

from app.modules.automation.models import AutomationRule, AutomationRun, AutomationTriggerType
from app.modules.spa.models import SpaBooking
from app.modules.spa.service import run_due_spa_reminders_all_tenants


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    token = response.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_spa_confirm_dispatches_automation(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    before_runs = (
        db.query(AutomationRun)
        .join(AutomationRule)
        .filter(AutomationRule.trigger_type == AutomationTriggerType.SPA_BOOKING_CONFIRMED)
        .count()
    )

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    massage = next(row for row in services if row["name"] == "Swedish Massage")

    booked_at = datetime.utcnow() + timedelta(days=3)
    booked_at = booked_at.replace(hour=11, minute=0, second=0, microsecond=0)
    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": massage["id"],
            "booked_at": booked_at.isoformat(),
            "guest_name": "Automation Guest",
            "guest_phone": "+91 93333 55555",
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]

    confirm = client.post(f"/api/v1/spa/bookings/{booking_id}/confirm", headers=headers, json={})
    assert confirm.status_code == 200

    after_runs = (
        db.query(AutomationRun)
        .join(AutomationRule)
        .filter(AutomationRule.trigger_type == AutomationTriggerType.SPA_BOOKING_CONFIRMED)
        .count()
    )
    assert after_runs > before_runs


def test_spa_reminder_job_sends_for_due_booking(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    services = client.get(
        "/api/v1/spa/services",
        headers=headers,
        params={"outlet_id": outlet_id, "page_size": 50},
    ).json()["data"]["items"]
    massage = next(row for row in services if row["name"] == "Swedish Massage")

    booked_at = datetime.utcnow() + timedelta(hours=24)
    booked_at = booked_at.replace(minute=0, second=0, microsecond=0)
    create = client.post(
        "/api/v1/spa/bookings",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "service_id": massage["id"],
            "booked_at": booked_at.isoformat(),
            "guest_name": "Reminder Guest",
            "guest_phone": "+91 94444 66666",
            "guest_email": "reminder-guest@example.com",
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]
    assert client.post(f"/api/v1/spa/bookings/{booking_id}/confirm", headers=headers, json={}).status_code == 200

    result = run_due_spa_reminders_all_tenants(db, hours_before=24, window_minutes=60)
    assert result.reminders_sent >= 1

    booking = db.get(SpaBooking, booking_id)
    assert booking is not None
    assert booking.reminder_sent_at is not None
