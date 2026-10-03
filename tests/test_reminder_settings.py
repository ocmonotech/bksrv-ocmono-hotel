"""Tests for per-outlet spa and banquet reminder settings."""

from datetime import date, datetime, timedelta

from app.modules.banquet.models import BanquetBooking
from app.modules.banquet.service import run_due_banquet_reminders_all_tenants
from app.modules.spa.models import SpaBooking
from app.modules.spa.service import run_due_spa_reminders_all_tenants


def _auth_headers(client) -> dict[str, str]:
    response = client.post(
        "/api/v1/auth/login",
        json={"email": "admin@example.com", "password": "Admin@123"},
    )
    assert response.status_code == 200
    return {"Authorization": f"Bearer {response.json()['access_token']}"}


def test_reminder_settings_defaults(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    response = client.get("/api/v1/settings/reminders", headers=headers, params={"outlet_id": outlet_id})
    assert response.status_code == 200
    body = response.json()
    assert body["outlet_id"] == outlet_id
    assert body["spa"]["enabled"] is True
    assert body["spa"]["hours_before"] == 24
    assert body["banquet"]["enabled"] is True
    assert body["banquet"]["send_email"] is True
    assert body["pms"]["enabled"] is True
    assert body["pms"]["hours_before"] == 24


def test_reminder_settings_update_and_persist(client):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    patch = client.patch(
        "/api/v1/settings/reminders",
        headers=headers,
        json={
            "outlet_id": outlet_id,
            "spa": {
                "enabled": False,
                "hours_before": 48,
                "window_minutes": 60,
                "send_sms": True,
                "send_email": False,
                "send_whatsapp": True,
            },
            "banquet": {
                "enabled": True,
                "hours_before": 12,
                "window_minutes": 45,
                "send_sms": False,
                "send_email": True,
                "send_whatsapp": False,
            },
        },
    )
    assert patch.status_code == 200
    assert patch.json()["spa"]["enabled"] is False
    assert patch.json()["spa"]["hours_before"] == 48
    assert patch.json()["banquet"]["hours_before"] == 12

    reload = client.get("/api/v1/settings/reminders", headers=headers, params={"outlet_id": outlet_id})
    assert reload.status_code == 200
    assert reload.json()["spa"]["enabled"] is False
    assert reload.json()["banquet"]["send_sms"] is False


def test_spa_reminder_skipped_when_disabled(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    assert (
        client.patch(
            "/api/v1/settings/reminders",
            headers=headers,
            json={
                "outlet_id": outlet_id,
                "spa": {
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
            "guest_name": "Disabled Reminder Guest",
            "guest_phone": "+91 95555 11111",
            "guest_email": "disabled-spa@example.com",
            "party_size": 1,
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]
    assert client.post(f"/api/v1/spa/bookings/{booking_id}/confirm", headers=headers, json={}).status_code == 200

    result = run_due_spa_reminders_all_tenants(db, hours_before=24, window_minutes=60)
    assert result.reminders_sent == 0

    booking = db.get(SpaBooking, booking_id)
    assert booking is not None
    assert booking.reminder_sent_at is None


def test_banquet_reminder_respects_custom_hours(client, db):
    headers = _auth_headers(client)
    outlet_id = client.get("/api/v1/outlets?page=1&page_size=5", headers=headers).json()["data"]["items"][0]["id"]

    assert (
        client.patch(
            "/api/v1/settings/reminders",
            headers=headers,
            json={
                "outlet_id": outlet_id,
                "banquet": {
                    "enabled": True,
                    "hours_before": 48,
                    "window_minutes": 60,
                    "send_sms": True,
                    "send_email": True,
                    "send_whatsapp": True,
                },
            },
        ).status_code
        == 200
    )

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
            "title": "Custom Hours Banquet",
            "event_type": "corporate",
            "event_date": event_at.date().isoformat(),
            "start_time": event_at.strftime("%H:%M"),
            "end_time": "23:00",
            "guest_count": 80,
            "contact_name": "Custom Hours Guest",
            "contact_phone": "+91 96666 22222",
            "contact_email": "custom-hours@example.com",
        },
    )
    assert create.status_code == 201
    booking_id = create.json()["id"]
    assert client.post(f"/api/v1/banquet/bookings/{booking_id}/confirm", headers=headers, json={}).status_code == 200

    result_24h = run_due_banquet_reminders_all_tenants(db)
    booking = db.get(BanquetBooking, booking_id)
    assert booking is not None
    assert booking.reminder_sent_at is None
    assert result_24h.reminders_sent == 0

    event_at_48 = datetime.utcnow() + timedelta(hours=48)
    event_at_48 = event_at_48.replace(minute=0, second=0, microsecond=0)
    booking.event_date = event_at_48.date()
    booking.start_time = event_at_48.strftime("%H:%M")
    db.commit()

    result_48h = run_due_banquet_reminders_all_tenants(db)
    assert result_48h.reminders_sent >= 1
    db.refresh(booking)
    assert booking.reminder_sent_at is not None
