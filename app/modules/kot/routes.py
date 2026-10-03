from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.kot import service
from app.modules.kot.schemas import KotItemStatusUpdate, KotRead, KotStatusUpdate
from app.modules.menu.models import PreparationArea
from app.modules.users.models import User

router = APIRouter()


@router.get("", response_model=list[KotRead])
def list_kots_by_outlet(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_READ)),
) -> list[KotRead]:
    return service.list_kots_by_outlet(db, current_user.tenant_id, outlet_id)


@router.get("/by-area", response_model=list[KotRead])
def list_kots_by_preparation_area(
    outlet_id: int = Query(...),
    preparation_area: PreparationArea = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_READ)),
) -> list[KotRead]:
    return service.list_kots_by_preparation_area(
        db, current_user.tenant_id, outlet_id, preparation_area
    )


@router.get("/{kot_id}", response_model=KotRead)
def get_kot(
    kot_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_READ)),
) -> KotRead:
    return service.get_kot(db, current_user.tenant_id, kot_id)


@router.patch("/{kot_id}/status", response_model=KotRead)
def update_kot_status(
    kot_id: int,
    body: KotStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_WRITE)),
) -> KotRead:
    return service.update_kot_status(db, current_user.tenant_id, kot_id, body.status)


@router.patch("/{kot_id}/items/{item_id}/status", response_model=KotRead)
def update_kot_item_status(
    kot_id: int,
    item_id: int,
    body: KotItemStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_WRITE)),
) -> KotRead:
    return service.update_kot_item_status(
        db, current_user.tenant_id, kot_id, item_id, body.status
    )


@router.post("/{kot_id}/items/{item_id}/cancel", response_model=KotRead)
def cancel_kot_item(
    kot_id: int,
    item_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.KOT_WRITE)),
) -> KotRead:
    return service.cancel_kot_item(db, current_user.tenant_id, kot_id, item_id)
