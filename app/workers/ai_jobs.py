from __future__ import annotations

import logging
from datetime import datetime, timezone

from app.workers.celery_app import celery_app
from app.workers.utils import task_db_session

logger = logging.getLogger(__name__)


@celery_app.task(name="ai.generate_ai_insight_mock", bind=True)
def generate_ai_insight_mock(
    self,
    tenant_id: int,
    outlet_id: int | None = None,
    insight_type: str = "operations",
) -> dict:
    """
    Mock AI insight generation — no external LLM APIs.

    Returns a placeholder insight payload suitable for later persistence.
    """
    with task_db_session() as db:
        outlet_name = None
        if outlet_id is not None:
            from app.modules.outlets.models import Outlet

            outlet = (
                db.query(Outlet)
                .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id)
                .first()
            )
            outlet_name = outlet.name if outlet else None

        generated_at = datetime.now(timezone.utc).isoformat()
        scope = outlet_name or "all outlets"

        logger.info(
            "Mock AI insight job %s tenant_id=%s outlet_id=%s type=%s",
            self.request.id,
            tenant_id,
            outlet_id,
            insight_type,
        )

        return {
            "ok": True,
            "mock": True,
            "task_id": self.request.id,
            "tenant_id": tenant_id,
            "outlet_id": outlet_id,
            "insight_type": insight_type,
            "title": f"Mock {insight_type.replace('_', ' ').title()} Insight",
            "summary": f"Placeholder insight for {scope}. Connect a real AI provider later.",
            "recommendations": [
                "Review peak-hour staffing",
                "Follow up on inactive VIP customers",
                "Check low-stock raw materials",
            ],
            "generated_at": generated_at,
            "message": "Mock AI insight generated (no external API calls)",
        }
