from __future__ import annotations

import asyncio
import logging

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="ota.push_auto_ari_outlet", bind=True)
def push_auto_ari_outlet_task(
    self,
    tenant_id: int,
    outlet_id: int,
    max_days: int = 14,
) -> dict:
    from app.modules.ota import service as ota_service
    from app.modules.ota.schemas import AriPushRequest

    with task_db_session() as db:
        summary = asyncio.run(
            ota_service.push_auto_ari_for_outlet(
                db,
                tenant_id,
                outlet_id,
                AriPushRequest(max_days=max_days),
            )
        )

    logger.info(
        "Auto ARI push outlet tenant=%s outlet=%s pushed=%s success=%s failed=%s task=%s",
        tenant_id,
        outlet_id,
        summary.integrations_pushed,
        summary.successes,
        summary.failures,
        self.request.id,
    )

    return {
        "ok": True,
        "task_id": self.request.id,
        "outlet_id": outlet_id,
        "integrations_pushed": summary.integrations_pushed,
        "successes": summary.successes,
        "failures": summary.failures,
    }


@celery_app.task(name="ota.push_auto_ari_all", bind=True)
def push_auto_ari_all_task(self, max_days: int = 14) -> dict:
    from app.modules.ota import service as ota_service
    from app.modules.ota.schemas import AriPushRequest

    with task_db_session() as db:
        summary = asyncio.run(
            ota_service.push_auto_ari_all_tenants(db, AriPushRequest(max_days=max_days))
        )

    logger.info(
        "Auto ARI push all tenants pushed=%s success=%s failed=%s task=%s",
        summary.integrations_pushed,
        summary.successes,
        summary.failures,
        self.request.id,
    )

    return {
        "ok": True,
        "task_id": self.request.id,
        "integrations_pushed": summary.integrations_pushed,
        "successes": summary.successes,
        "failures": summary.failures,
    }
