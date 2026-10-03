from __future__ import annotations

import logging
from typing import Any

from app.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


@celery_app.task(name="communications.process_inbound_whatsapp_mock", bind=True)
def process_inbound_whatsapp_mock(
    self,
    tenant_id: int,
    payload: dict[str, Any] | None = None,
) -> dict:
    """
    Mock inbound WhatsApp webhook processor — no external API calls.

    Accepts a webhook-like payload and returns a simulated processing result.
    """
    payload = payload or {}
    sender = payload.get("from") or payload.get("sender") or "mock-sender"
    message_text = payload.get("text") or payload.get("body") or ""

    logger.info(
        "Mock inbound WhatsApp job %s tenant_id=%s sender=%s",
        self.request.id,
        tenant_id,
        sender,
    )

    return {
        "ok": True,
        "mock": True,
        "task_id": self.request.id,
        "tenant_id": tenant_id,
        "sender": sender,
        "message_text": message_text,
        "conversation_status": "open",
        "auto_reply": "Thanks for your message. This is a mock auto-reply.",
        "message": "Mock inbound WhatsApp processed (no external API calls)",
    }
