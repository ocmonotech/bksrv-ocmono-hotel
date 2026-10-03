from __future__ import annotations

from datetime import datetime

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.leads import service
from app.modules.leads.models import LeadSource, LeadStage, LeadStatus
from app.modules.leads.schemas import (
    LeadActivityCreate,
    LeadActivityRead,
    LeadAssign,
    LeadCreate,
    LeadDetailRead,
    LeadFollowUpUpdate,
    LeadRead,
    LeadStageUpdate,
    SegmentCreate,
    SegmentEstimateResponse,
    SegmentRead,
    SegmentUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("", response_model=LeadRead, status_code=status.HTTP_201_CREATED)
def create_lead(
    body: LeadCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    return service.create_lead(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("", response_model=PaginatedSuccessResponse[LeadRead])
def list_leads(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    outlet_id: int | None = Query(None),
    source: LeadSource | None = Query(None),
    campaign_id: int | None = Query(None),
    stage: LeadStage | None = Query(None),
    min_lead_score: int | None = Query(None, ge=0, le=100),
    max_lead_score: int | None = Query(None, ge=0, le=100),
    assigned_user: int | None = Query(None),
    date_from: datetime | None = Query(None),
    date_to: datetime | None = Query(None),
    tags: list[str] | None = Query(None),
    brand_id: int | None = Query(None),
    status: LeadStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_READ)),
) -> PaginatedSuccessResponse[LeadRead]:
    items, total = service.list_leads(
        db,
        current_user.tenant_id,
        page,
        page_size,
        outlet_id=outlet_id,
        source=source,
        campaign_id=campaign_id,
        stage=stage,
        min_lead_score=min_lead_score,
        max_lead_score=max_lead_score,
        assigned_user=assigned_user,
        date_from=date_from,
        date_to=date_to,
        tags=tags,
        brand_id=brand_id,
        status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.post("/segments", response_model=SegmentRead, status_code=status.HTTP_201_CREATED)
def create_segment(
    body: SegmentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> SegmentRead:
    return service.create_segment(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/segments", response_model=PaginatedSuccessResponse[SegmentRead])
def list_segments(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_READ)),
) -> PaginatedSuccessResponse[SegmentRead]:
    items, total = service.list_segments(
        db, current_user.tenant_id, page, page_size, brand_id=brand_id
    )
    return success_paginated(items, total, page, page_size)


@router.patch("/segments/{segment_id}", response_model=SegmentRead)
def update_segment(
    segment_id: int,
    body: SegmentUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> SegmentRead:
    return service.update_segment(db, current_user.tenant_id, segment_id, body)


@router.delete("/segments/{segment_id}", response_model=SegmentRead)
def delete_segment(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> SegmentRead:
    return service.delete_segment(db, current_user.tenant_id, segment_id)


@router.post("/segments/{segment_id}/estimate-count", response_model=SegmentEstimateResponse)
def estimate_segment_count(
    segment_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_READ)),
) -> SegmentEstimateResponse:
    return service.estimate_segment_count(db, current_user.tenant_id, segment_id)


@router.get("/{lead_id}", response_model=LeadDetailRead)
def get_lead_details(
    lead_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_READ)),
) -> LeadDetailRead:
    return service.get_lead_details(db, current_user.tenant_id, lead_id)


@router.patch("/{lead_id}/stage", response_model=LeadRead)
def update_lead_stage(
    lead_id: int,
    body: LeadStageUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    return service.update_lead_stage(
        db, current_user.tenant_id, current_user.id, lead_id, body
    )


@router.patch("/{lead_id}/assign", response_model=LeadRead)
def assign_lead(
    lead_id: int,
    body: LeadAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    return service.assign_lead(db, current_user.tenant_id, current_user.id, lead_id, body)


@router.post("/{lead_id}/activities", response_model=LeadActivityRead, status_code=status.HTTP_201_CREATED)
def add_activity(
    lead_id: int,
    body: LeadActivityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadActivityRead:
    return service.add_activity(
        db, current_user.tenant_id, current_user.id, lead_id, body
    )


@router.patch("/{lead_id}/follow-up", response_model=LeadRead)
def add_follow_up(
    lead_id: int,
    body: LeadFollowUpUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.LEADS_WRITE)),
) -> LeadRead:
    return service.add_follow_up(
        db, current_user.tenant_id, current_user.id, lead_id, body
    )
