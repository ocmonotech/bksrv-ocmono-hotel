from __future__ import annotations

import logging

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="pms.send_due_arrival_reminders", bind=True)
def send_due_pms_reminders_task(self, hours_before: int | None = None) -> dict:
    """Send pre-arrival reminders for confirmed guest stays (Celery Beat)."""
    from app.modules.pms.service import run_due_pms_reminders_all_tenants

    with task_db_session() as db:
        result = run_due_pms_reminders_all_tenants(db, hours_before=hours_before)

    logger.info(
        "PMS reminder job %s sent=%s checked=%s tenants=%s",
        self.request.id,
        result.reminders_sent,
        result.reservations_checked,
        result.tenants_processed,
    )

    return {
        "ok": True,
        "task_id": self.request.id,
        "message": result.message,
        "reminders_sent": result.reminders_sent,
        "reservations_checked": result.reservations_checked,
        "tenants_processed": result.tenants_processed,
    }


@celery_app.task(name="pms.run_night_audit", bind=True)
def run_night_audit_task(
    self,
    outlet_id: int | None = None,
    business_date: str | None = None,
) -> dict:
    """Run night audit for outlets with hotel rooms (yesterday by default)."""
    from datetime import date

    from app.modules.pms.service import run_night_audit_all_outlets

    parsed_date = date.fromisoformat(business_date) if business_date else None
    with task_db_session() as db:
        result = run_night_audit_all_outlets(
            db,
            business_date=parsed_date,
            outlet_id=outlet_id,
        )

    logger.info(
        "PMS night audit job %s date=%s outlets=%s",
        self.request.id,
        result.get("business_date"),
        result.get("outlets_processed"),
    )
    return {"ok": True, "task_id": self.request.id, **result}
