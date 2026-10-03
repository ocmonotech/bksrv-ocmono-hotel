from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.minibar import service
from app.modules.minibar.schemas import (
    MinibarCatalogItemCreate,
    MinibarCatalogItemRead,
    MinibarCatalogItemUpdate,
    MinibarChargeCreate,
    MinibarChargeResponse,
    MinibarPostingRead,
    MinibarVoidRequest,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/catalog", response_model=list[MinibarCatalogItemRead])
def list_catalog(
    outlet_id: int | None = Query(default=None),
    seed_defaults: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[MinibarCatalogItemRead]:
    if seed_defaults:
        service.ensure_default_catalog(
            db,
            current_user.tenant_id,
            brand_id=current_user.brand_id,
            outlet_id=outlet_id,
        )
    return service.list_catalog(db, current_user.tenant_id, outlet_id=outlet_id)


@router.post("/catalog", response_model=MinibarCatalogItemRead, status_code=status.HTTP_201_CREATED)
def create_catalog_item(
    body: MinibarCatalogItemCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> MinibarCatalogItemRead:
    return service.create_catalog_item(
        db,
        current_user.tenant_id,
        body,
        brand_id=current_user.brand_id,
    )


@router.patch("/catalog/{item_id}", response_model=MinibarCatalogItemRead)
def update_catalog_item(
    item_id: int,
    body: MinibarCatalogItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> MinibarCatalogItemRead:
    return service.update_catalog_item(db, current_user.tenant_id, item_id, body)


@router.get("/postings", response_model=list[MinibarPostingRead])
def list_postings(
    outlet_id: int | None = Query(default=None),
    reservation_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_READ)),
) -> list[MinibarPostingRead]:
    return service.list_postings(
        db,
        current_user.tenant_id,
        outlet_id=outlet_id,
        reservation_id=reservation_id,
    )


@router.post(
    "/reservations/{reservation_id}/charges",
    response_model=MinibarChargeResponse,
    status_code=status.HTTP_201_CREATED,
)
def post_charge(
    reservation_id: int,
    body: MinibarChargeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> MinibarChargeResponse:
    return service.post_minibar_charge(
        db,
        current_user.tenant_id,
        current_user.id,
        reservation_id,
        body,
    )


@router.post("/postings/{posting_id}/void", response_model=MinibarPostingRead)
def void_posting(
    posting_id: int,
    body: MinibarVoidRequest | None = None,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.PMS_WRITE)),
) -> MinibarPostingRead:
    return service.void_minibar_posting(
        db,
        current_user.tenant_id,
        current_user.id,
        posting_id,
        body,
    )
