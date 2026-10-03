from __future__ import annotations

import json
from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.common.pagination import paginate_query
from app.modules.audit.models import AuditLog
from app.modules.audit.schemas import AuditLogRead

SENSITIVE_FIELDS = frozenset(
    {"api_key", "encrypted_api_key", "hashed_password", "password", "config_json"}
)


def sanitize_audit_data(data: dict[str, Any] | None) -> dict[str, Any] | None:
    if data is None:
        return None
    sanitized: dict[str, Any] = {}
    for key, value in data.items():
        if key in SENSITIVE_FIELDS:
            sanitized[key] = "***"
        elif isinstance(value, dict):
            sanitized[key] = sanitize_audit_data(value)
        else:
            sanitized[key] = value
    return sanitized


def _dump_audit_data(data: dict[str, Any] | None) -> str | None:
    if data is None:
        return None
    return json.dumps(sanitize_audit_data(data), default=str)


def log_audit(
    db: Session,
    *,
    tenant_id: int,
    action: str,
    module_name: str,
    record_type: str,
    record_id: int | None = None,
    brand_id: int | None = None,
    outlet_id: int | None = None,
    user_id: int | None = None,
    old_data: dict[str, Any] | None = None,
    new_data: dict[str, Any] | None = None,
    ip_address: str | None = None,
    user_agent: str | None = None,
) -> AuditLog:
    entry = AuditLog(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=outlet_id,
        user_id=user_id,
        action=action,
        module_name=module_name,
        record_type=record_type,
        record_id=record_id,
        old_data_json=_dump_audit_data(old_data),
        new_data_json=_dump_audit_data(new_data),
        ip_address=ip_address,
        user_agent=user_agent,
    )
    db.add(entry)
    return entry


def list_audit_logs(
    db: Session,
    tenant_id: int,
    *,
    user_id: int | None = None,
    module_name: str | None = None,
    action: str | None = None,
    brand_id: int | None = None,
    outlet_id: int | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[list[AuditLogRead], int]:
    query = db.query(AuditLog).filter(AuditLog.tenant_id == tenant_id)

    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if module_name is not None:
        query = query.filter(AuditLog.module_name == module_name)
    if action is not None:
        query = query.filter(AuditLog.action == action)
    if brand_id is not None:
        query = query.filter(AuditLog.brand_id == brand_id)
    if outlet_id is not None:
        query = query.filter(AuditLog.outlet_id == outlet_id)
    if date_from is not None:
        query = query.filter(AuditLog.created_at >= date_from)
    if date_to is not None:
        query = query.filter(AuditLog.created_at <= date_to)

    query = query.order_by(AuditLog.created_at.desc(), AuditLog.id.desc())
    items, total = paginate_query(query, page, page_size)
    return [AuditLogRead.model_validate(item) for item in items], total


def get_audit_log(db: Session, tenant_id: int, audit_log_id: int) -> AuditLogRead:
    from app.core.exceptions import NotFoundError

    entry = (
        db.query(AuditLog)
        .filter(AuditLog.id == audit_log_id, AuditLog.tenant_id == tenant_id)
        .first()
    )
    if entry is None:
        raise NotFoundError("Audit log not found")
    return AuditLogRead.model_validate(entry)
