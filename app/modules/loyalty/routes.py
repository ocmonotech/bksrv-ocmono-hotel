from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.loyalty import service
from app.modules.loyalty.schemas import (
    LoyaltyAdjustRequest,
    LoyaltyConfigRead,
    LoyaltyConfigUpdate,
    LoyaltyLedgerRead,
    LoyaltyRedeemPreview,
    LoyaltySummaryRead,
    LoyaltyTierCreate,
    LoyaltyTierRead,
    LoyaltyTierSeedRequest,
    LoyaltyTierUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/summary", response_model=LoyaltySummaryRead)
def loyalty_summary(
    brand_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> LoyaltySummaryRead:
    return service.get_summary(
        db,
        current_user.tenant_id,
        brand_id or current_user.brand_id,
    )


@router.get("/config", response_model=LoyaltyConfigRead)
def get_config(
    brand_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> LoyaltyConfigRead:
    bid = brand_id or current_user.brand_id
    if not bid:
        return LoyaltyConfigRead()
    return service.get_loyalty_config(db, current_user.tenant_id, bid)


@router.patch("/config", response_model=LoyaltyConfigRead)
def patch_config(
    body: LoyaltyConfigUpdate,
    brand_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> LoyaltyConfigRead:
    bid = brand_id or current_user.brand_id
    if not bid:
        from app.core.exceptions import ConflictError

        raise ConflictError("Brand is required to update loyalty settings")
    return service.update_loyalty_config(db, current_user.tenant_id, bid, body)


@router.get("/tiers", response_model=list[LoyaltyTierRead])
def list_tiers(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> list[LoyaltyTierRead]:
    service.ensure_default_tiers(db, current_user.tenant_id, current_user.brand_id)
    return service.list_tiers(db, current_user.tenant_id)


@router.post("/tiers/seed", response_model=list[LoyaltyTierRead])
def seed_tiers(
    body: LoyaltyTierSeedRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> list[LoyaltyTierRead]:
    return service.ensure_default_tiers(
        db,
        current_user.tenant_id,
        current_user.brand_id,
        reset=body.reset,
    )


@router.post("/tiers", response_model=LoyaltyTierRead, status_code=status.HTTP_201_CREATED)
def create_tier(
    body: LoyaltyTierCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> LoyaltyTierRead:
    return service.create_tier(db, current_user.tenant_id, body, current_user.brand_id)


@router.patch("/tiers/{tier_id}", response_model=LoyaltyTierRead)
def update_tier(
    tier_id: int,
    body: LoyaltyTierUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> LoyaltyTierRead:
    return service.update_tier(db, current_user.tenant_id, tier_id, body)


@router.get("/ledger", response_model=PaginatedSuccessResponse[LoyaltyLedgerRead])
def list_ledger(
    customer_id: int | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> PaginatedSuccessResponse[LoyaltyLedgerRead]:
    rows, total = service.list_ledger(
        db,
        current_user.tenant_id,
        customer_id=customer_id,
        page=page,
        page_size=page_size,
    )
    return success_paginated(rows, total=total, page=page, page_size=page_size)


@router.post("/adjust", response_model=LoyaltyLedgerRead)
def adjust_points(
    body: LoyaltyAdjustRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_WRITE)),
) -> LoyaltyLedgerRead:
    return service.adjust_points(
        db,
        current_user.tenant_id,
        body,
        user_id=current_user.id,
        brand_id=current_user.brand_id,
    )


@router.get("/customers/{customer_id}/redeem-preview", response_model=LoyaltyRedeemPreview)
def redeem_preview(
    customer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.CUSTOMERS_READ)),
) -> LoyaltyRedeemPreview:
    return service.get_redeem_preview(
        db,
        current_user.tenant_id,
        customer_id,
        brand_id=current_user.brand_id,
    )
