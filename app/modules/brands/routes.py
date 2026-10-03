from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.brands import service
from app.modules.brands.schemas import BrandCreate, BrandRead, BrandUpdate
from app.modules.outlets.schemas import OutletRead
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=list[BrandRead])
def list_brands(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BRANDS_READ)),
) -> list[BrandRead]:
    return service.list_brands(db, current_user.tenant_id)


@router.post("", response_model=BrandRead, status_code=status.HTTP_201_CREATED)
def create_brand(
    body: BrandCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BRANDS_WRITE)),
) -> BrandRead:
    return service.create_brand(db, current_user.tenant_id, body)


@router.get("/{brand_id}", response_model=BrandRead)
def get_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BRANDS_READ)),
) -> BrandRead:
    return service.get_brand(db, current_user.tenant_id, brand_id)


@router.patch("/{brand_id}", response_model=BrandRead)
def update_brand(
    brand_id: int,
    body: BrandUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.BRANDS_WRITE)),
) -> BrandRead:
    return service.update_brand(db, current_user.tenant_id, brand_id, body)


@router.get("/{brand_id}/outlets", response_model=list[OutletRead])
def get_outlets_by_brand(
    brand_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_READ)),
) -> list[OutletRead]:
    from app.modules.outlets import service as outlet_service

    return outlet_service.list_outlets_by_brand(db, current_user.tenant_id, brand_id)
