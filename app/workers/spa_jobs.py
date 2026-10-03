from __future__ import annotations

import logging

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="spa.send_due_appointment_reminders", bind=True)
def send_due_spa_reminders_task(self, hours_before: int | None = None) -> dict:
    """Send spa appointment reminders for bookings due in ~24 hours (Celery Beat)."""
    from app.modules.spa.service import run_due_spa_reminders_all_tenants

    with task_db_session() as db:
        result = run_due_spa_reminders_all_tenants(db, hours_before=hours_before)

    logger.info(
        "Spa reminder job %s sent=%s checked=%s tenants=%s",
        self.request.id,
        result.reminders_sent,
        result.bookings_checked,
        result.tenants_processed,
    )

    return {
        "ok": True,
        "task_id": self.request.id,
        "message": result.message,
        "reminders_sent": result.reminders_sent,
        "bookings_checked": result.bookings_checked,
        "tenants_processed": result.tenants_processed,
    }
