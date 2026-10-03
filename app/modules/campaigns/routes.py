from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.campaigns import service
from app.modules.campaigns.models import CampaignChannel, CampaignStatus, RecipientStatus
from app.modules.campaigns.schemas import (
    CampaignCreate,
    CampaignDetailRead,
    CampaignRead,
    CampaignRecipientRead,
    CampaignReport,
    CampaignSchedule,
    CampaignUpdate,
    MockLaunchResponse,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("", response_model=CampaignRead, status_code=status.HTTP_201_CREATED)
def create_campaign(
    body: CampaignCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.create_campaign(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("", response_model=PaginatedSuccessResponse[CampaignRead])
def list_campaigns(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    channel: CampaignChannel | None = Query(None),
    status: CampaignStatus | None = Query(None),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> PaginatedSuccessResponse[CampaignRead]:
    items, total = service.list_campaigns(
        db,
        current_user.tenant_id,
        page,
        page_size,
        channel=channel,
        status=status,
        brand_id=brand_id,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/{campaign_id}", response_model=CampaignDetailRead)
def get_campaign_details(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> CampaignDetailRead:
    return service.get_campaign_details(db, current_user.tenant_id, campaign_id)


@router.patch("/{campaign_id}", response_model=CampaignRead)
def update_campaign(
    campaign_id: int,
    body: CampaignUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.update_campaign(db, current_user.tenant_id, campaign_id, body)


@router.post("/{campaign_id}/schedule", response_model=CampaignRead)
def schedule_campaign(
    campaign_id: int,
    body: CampaignSchedule,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.schedule_campaign(db, current_user.tenant_id, campaign_id, body)


@router.post("/{campaign_id}/pause", response_model=CampaignRead)
def pause_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.pause_campaign(db, current_user.tenant_id, campaign_id)


@router.post("/{campaign_id}/resume", response_model=CampaignRead)
def resume_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.resume_campaign(db, current_user.tenant_id, campaign_id)


@router.post("/{campaign_id}/cancel", response_model=CampaignRead)
def cancel_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> CampaignRead:
    return service.cancel_campaign(db, current_user.tenant_id, campaign_id)


@router.get("/{campaign_id}/recipients", response_model=PaginatedSuccessResponse[CampaignRecipientRead])
def get_campaign_recipients(
    campaign_id: int,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    status: RecipientStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> PaginatedSuccessResponse[CampaignRecipientRead]:
    items, total = service.get_campaign_recipients(
        db,
        current_user.tenant_id,
        campaign_id,
        page,
        page_size,
        status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/{campaign_id}/reports", response_model=CampaignReport)
def get_campaign_reports(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_READ)),
) -> CampaignReport:
    return service.get_campaign_report(db, current_user.tenant_id, campaign_id)


@router.post("/{campaign_id}/launch", response_model=MockLaunchResponse, status_code=status.HTTP_201_CREATED)
async def mock_launch_campaign(
    campaign_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CAMPAIGNS_WRITE)),
) -> MockLaunchResponse:
    return await service.mock_launch_campaign(
        db,
        current_user.tenant_id,
        campaign_id,
        current_user.id,
    )
