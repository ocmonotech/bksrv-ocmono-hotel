"""
Celery application for optional background jobs.

This module is only loaded by the Celery worker/beat CLI — not by FastAPI startup.
Importing it does not require Redis to be running; connections are opened when
the worker starts or a task is dispatched.
"""

from celery import Celery
from celery.schedules import crontab

from app.core.config import settings

celery_app = Celery(
    settings.celery_app_name,
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
    include=[
        "app.workers.campaign_jobs",
        "app.workers.communication_jobs",
        "app.workers.ai_jobs",
        "app.workers.report_jobs",
        "app.workers.housekeeping_jobs",
        "app.workers.ota_jobs",
        "app.workers.spa_jobs",
        "app.workers.banquet_jobs",
        "app.workers.pms_jobs",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone=settings.default_timezone,
    enable_utc=True,
    task_track_started=True,
    task_default_queue=settings.celery_default_queue,
    broker_connection_retry_on_startup=True,
    result_expires=3600,
)

# Placeholder beat schedule — enable Celery Beat and customize per tenant later.
celery_app.conf.beat_schedule = {
    "daily-sales-report-mock": {
        "task": "reports.daily_sales_report_mock",
        "schedule": 60 * 60 * 24,
        "kwargs": {},
    },
    "low-stock-alert-mock": {
        "task": "reports.low_stock_alert_mock",
        "schedule": 60 * 60 * 6,
        "kwargs": {},
    },
    "housekeeping-run-due-sweeps": {
        "task": "housekeeping.run_due_sweep_schedules",
        "schedule": crontab(minute="*/15"),
        "kwargs": {"force": False},
    },
    "ota-auto-ari-push-all": {
        "task": "ota.push_auto_ari_all",
        "schedule": crontab(minute="*/30"),
        "kwargs": {"max_days": 14},
    },
    "spa-send-due-reminders": {
        "task": "spa.send_due_appointment_reminders",
        "schedule": crontab(minute="*/15"),
        "kwargs": {},
    },
    "banquet-send-due-reminders": {
        "task": "banquet.send_due_event_reminders",
        "schedule": crontab(minute="*/15"),
        "kwargs": {},
    },
    "pms-send-due-reminders": {
        "task": "pms.send_due_arrival_reminders",
        "schedule": crontab(minute="*/15"),
        "kwargs": {},
    },
    "pms-run-night-audit": {
        "task": "pms.run_night_audit",
        "schedule": crontab(hour=2, minute=0),
        "kwargs": {},
    },
}
