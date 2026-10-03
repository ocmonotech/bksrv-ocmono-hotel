from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.automation import service
from app.modules.automation.models import AutomationRuleStatus, AutomationRunStatus, AutomationTriggerType
from app.modules.automation.schemas import (
    AutomationRuleCreate,
    AutomationRuleRead,
    AutomationRuleUpdate,
    AutomationRunRead,
    MockRunRequest,
    MockRunResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("/rules", response_model=AutomationRuleRead, status_code=status.HTTP_201_CREATED)
def create_automation_rule(
    body: AutomationRuleCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> AutomationRuleRead:
    return service.create_rule(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/rules", response_model=PaginatedSuccessResponse[AutomationRuleRead])
def list_automation_rules(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    trigger_type: AutomationTriggerType | None = Query(None),
    status: AutomationRuleStatus | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> PaginatedSuccessResponse[AutomationRuleRead]:
    items, total = service.list_rules(
        db,
        current_user.tenant_id,
        page,
        page_size,
        trigger_type=trigger_type,
        status=status,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.patch("/rules/{rule_id}", response_model=AutomationRuleRead)
def update_automation_rule(
    rule_id: int,
    body: AutomationRuleUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> AutomationRuleRead:
    return service.update_rule(db, current_user.tenant_id, rule_id, body)


@router.post("/rules/{rule_id}/activate", response_model=AutomationRuleRead)
def activate_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> AutomationRuleRead:
    return service.activate_rule(db, current_user.tenant_id, rule_id)


@router.post("/rules/{rule_id}/deactivate", response_model=AutomationRuleRead)
def deactivate_automation_rule(
    rule_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> AutomationRuleRead:
    return service.deactivate_rule(db, current_user.tenant_id, rule_id)


@router.post("/rules/{rule_id}/run", response_model=MockRunResponse, status_code=status.HTTP_201_CREATED)
async def run_automation(
    rule_id: int,
    body: MockRunRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> MockRunResponse:
    return await service.run_automation_mock(db, current_user.tenant_id, rule_id, body)


@router.get("/runs", response_model=PaginatedSuccessResponse[AutomationRunRead])
def list_automation_runs(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    rule_id: int | None = Query(None),
    status: AutomationRunStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> PaginatedSuccessResponse[AutomationRunRead]:
    items, total = service.list_runs(
        db,
        current_user.tenant_id,
        page,
        page_size,
        rule_id=rule_id,
        status=status,
    )
    return success_paginated(items, total, page, page_size)
