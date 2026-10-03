from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.audit import service
from app.modules.audit.schemas import AuditLogRead
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=PaginatedSuccessResponse[AuditLogRead])
def list_audit_logs(
    user_id: int | None = Query(None),
    module_name: str | None = Query(None),
    action: str | None = Query(None),
    brand_id: int | None = Query(None),
    outlet_id: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)),
) -> PaginatedSuccessResponse[AuditLogRead]:
    items, total = service.list_audit_logs(
        db,
        current_user.tenant_id,
        user_id=user_id,
        module_name=module_name,
        action=action,
        brand_id=brand_id,
        outlet_id=outlet_id,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/{audit_log_id}", response_model=AuditLogRead)
def get_audit_log(
    audit_log_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.AUDIT_READ)),
) -> AuditLogRead:
    return service.get_audit_log(db, current_user.tenant_id, audit_log_id)
