from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.common.response import MessageResponse
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.outlets import service
from app.modules.outlets.schemas import OutletCreate, OutletRead, OutletUpdate
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=PaginatedSuccessResponse[OutletRead])
def list_outlets(
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    brand_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_READ)),
) -> PaginatedSuccessResponse[OutletRead]:
    items, total = service.list_outlets(
        db, current_user.tenant_id, page, page_size, brand_id=brand_id
    )
    return success_paginated(items, total, page, page_size)


@router.post("", response_model=OutletRead, status_code=status.HTTP_201_CREATED)
def create_outlet(
    body: OutletCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_WRITE)),
) -> OutletRead:
    return service.create_outlet(db, current_user.tenant_id, body)


@router.get("/{outlet_id}", response_model=OutletRead)
def get_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_READ)),
) -> OutletRead:
    return service.get_outlet(db, current_user.tenant_id, outlet_id)


@router.patch("/{outlet_id}", response_model=OutletRead)
def update_outlet(
    outlet_id: int,
    body: OutletUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_WRITE)),
) -> OutletRead:
    return service.update_outlet(db, current_user.tenant_id, outlet_id, body)


@router.delete("/{outlet_id}", response_model=MessageResponse)
def delete_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_WRITE)),
) -> MessageResponse:
    service.delete_outlet(db, current_user.tenant_id, outlet_id)
    return MessageResponse(message="Outlet deactivated")


@router.post("/{outlet_id}/activate", response_model=OutletRead)
def activate_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_WRITE)),
) -> OutletRead:
    return service.activate_outlet(db, current_user.tenant_id, outlet_id)


@router.post("/{outlet_id}/deactivate", response_model=OutletRead)
def deactivate_outlet(
    outlet_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.OUTLETS_WRITE)),
) -> OutletRead:
    return service.deactivate_outlet(db, current_user.tenant_id, outlet_id)
