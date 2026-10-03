from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.offers import service
from app.modules.offers.models import OfferStatus
from app.modules.offers.schemas import OfferCreate, OfferDeleteResponse, OfferRead, OfferUpdate
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=PaginatedSuccessResponse[OfferRead])
def list_offers(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None),
    outlet_id: int | None = Query(None),
    status: OfferStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> PaginatedSuccessResponse[OfferRead]:
    items, total = service.list_offers(
        db,
        current_user.tenant_id,
        page,
        page_size,
        brand_id=brand_id,
        outlet_id=outlet_id,
        status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.post("", response_model=OfferRead, status_code=status.HTTP_201_CREATED)
def create_offer(
    body: OfferCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> OfferRead:
    return service.create_offer(
        db,
        current_user.tenant_id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/{offer_id}", response_model=OfferRead)
def get_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_READ)),
) -> OfferRead:
    return service.get_offer(db, current_user.tenant_id, offer_id)


@router.patch("/{offer_id}", response_model=OfferRead)
def update_offer(
    offer_id: int,
    body: OfferUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> OfferRead:
    return service.update_offer(db, current_user.tenant_id, offer_id, body)


@router.delete("/{offer_id}", response_model=OfferDeleteResponse)
def delete_offer(
    offer_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.MENU_WRITE)),
) -> OfferDeleteResponse:
    return service.delete_offer(db, current_user.tenant_id, offer_id)
