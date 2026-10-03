"""Notify OTA channels when lodging availability changes."""

from __future__ import annotations

from app.modules.ota.auto_push import schedule_auto_ari_push


def notify_lodging_availability_changed(tenant_id: int, outlet_id: int) -> None:
    schedule_auto_ari_push(tenant_id, outlet_id)
