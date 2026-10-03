from __future__ import annotations

import logging

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="housekeeping.run_due_sweep_schedules", bind=True)
def run_due_sweep_schedules_task(self, force: bool = False) -> dict:
    """Run due housekeeping sweep schedules for all tenants (Celery Beat)."""
    from app.modules.housekeeping.service import run_due_sweep_schedules_all_tenants

    with task_db_session() as db:
        result = run_due_sweep_schedules_all_tenants(db, force=force)

    logger.info(
        "Housekeeping sweep job %s schedules_run=%s tasks_created=%s tenants=%s",
        self.request.id,
        result.schedules_run,
        result.tasks_created,
        result.tenants_processed,
    )

    return {
        "ok": True,
        "task_id": self.request.id,
        "message": result.message,
        "schedules_run": result.schedules_run,
        "tasks_created": result.tasks_created,
        "tenants_processed": result.tenants_processed,
    }
