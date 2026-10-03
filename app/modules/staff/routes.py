from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.staff import service
from app.modules.staff.schemas import (
    StaffDaySummary,
    StaffMemberRead,
    StaffShiftCreate,
    StaffShiftRead,
    StaffShiftUpdate,
    TipPoolDistributeRequest,
    TipPoolRead,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/directory", response_model=list[StaffMemberRead])
def staff_directory(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[StaffMemberRead]:
    return service.list_outlet_staff(db, current_user.tenant_id, outlet_id)


@router.get("/summary", response_model=StaffDaySummary)
def day_summary(
    outlet_id: int = Query(...),
    shift_date: date | None = Query(default=None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> StaffDaySummary:
    return service.get_day_summary(
        db,
        current_user.tenant_id,
        outlet_id,
        shift_date or date.today(),
    )


@router.get("/shifts", response_model=list[StaffShiftRead])
def list_shifts(
    outlet_id: int | None = Query(default=None),
    shift_date: date | None = Query(default=None),
    include_inactive: bool = Query(default=False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[StaffShiftRead]:
    return service.list_shifts(
        db,
        current_user.tenant_id,
        outlet_id=outlet_id,
        shift_date=shift_date,
        include_inactive=include_inactive,
    )


@router.post("/shifts", response_model=StaffShiftRead, status_code=status.HTTP_201_CREATED)
def create_shift(
    body: StaffShiftCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> StaffShiftRead:
    return service.create_shift(
        db,
        current_user.tenant_id,
        body,
        brand_id=current_user.brand_id,
        user_id=current_user.id,
    )


@router.patch("/shifts/{shift_id}", response_model=StaffShiftRead)
def update_shift(
    shift_id: int,
    body: StaffShiftUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> StaffShiftRead:
    return service.update_shift(db, current_user.tenant_id, shift_id, body)


@router.get("/tip-pools", response_model=list[TipPoolRead])
def list_tip_pools(
    outlet_id: int | None = Query(default=None),
    limit: int = Query(default=30, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[TipPoolRead]:
    return service.list_tip_pools(db, current_user.tenant_id, outlet_id=outlet_id, limit=limit)


@router.get("/tip-pools/current", response_model=TipPoolRead)
def current_tip_pool(
    outlet_id: int = Query(...),
    shift_date: date | None = Query(default=None),
    ensure: bool = Query(default=True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> TipPoolRead:
    return service.get_tip_pool(
        db,
        current_user.tenant_id,
        outlet_id=outlet_id,
        shift_date=shift_date or date.today(),
        ensure=ensure,
    )


@router.post("/tip-pools/{pool_id}/refresh", response_model=TipPoolRead)
def refresh_tip_pool(
    pool_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TipPoolRead:
    return service.refresh_tip_pool(db, current_user.tenant_id, pool_id)


@router.post("/tip-pools/{pool_id}/distribute", response_model=TipPoolRead)
def distribute_tip_pool(
    pool_id: int,
    body: TipPoolDistributeRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TipPoolRead:
    return service.distribute_tip_pool(
        db,
        current_user.tenant_id,
        pool_id,
        body,
        settled_by=current_user.id,
    )
