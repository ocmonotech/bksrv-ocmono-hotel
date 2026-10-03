"""Schedule ARI pushes when integrations have auto_push_availability enabled."""

from __future__ import annotations

import asyncio
import logging

from app.core.config import settings
from app.modules.ota.schemas import AriPushRequest

logger = logging.getLogger(__name__)

DEFAULT_MAX_DAYS = 14


async def _push_auto_ari_inline(tenant_id: int, outlet_id: int, max_days: int) -> None:
    from app.modules.ota import service as ota_service
    from app.workers.utils import task_db_session

    with task_db_session() as db:
        await ota_service.push_auto_ari_for_outlet(
            db,
            tenant_id,
            outlet_id,
            AriPushRequest(max_days=max_days),
        )


def schedule_auto_ari_push(
    tenant_id: int,
    outlet_id: int,
    *,
    max_days: int = DEFAULT_MAX_DAYS,
) -> None:
    """Enqueue or run inline auto ARI push after availability-changing PMS events."""
    if settings.celery_enabled:
        from app.workers.ota_jobs import push_auto_ari_outlet_task
        from app.workers.utils import enqueue_task

        enqueue_task(
            push_auto_ari_outlet_task,
            tenant_id=tenant_id,
            outlet_id=outlet_id,
            max_days=max_days,
        )
        return

    try:
        loop = asyncio.get_running_loop()
        loop.create_task(_push_auto_ari_inline(tenant_id, outlet_id, max_days))
        return
    except RuntimeError:
        pass

    try:
        asyncio.run(_push_auto_ari_inline(tenant_id, outlet_id, max_days))
    except Exception:
        logger.exception(
            "Inline auto ARI push failed for tenant=%s outlet=%s",
            tenant_id,
            outlet_id,
        )
