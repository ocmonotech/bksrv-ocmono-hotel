from __future__ import annotations

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.tables import service
from app.modules.tables.schemas import (
    AssignWaiterRequest,
    FloorCreate,
    FloorRead,
    MergeTablesRequest,
    MoveTableRequest,
    TableCreate,
    TableRead,
    TableStatusUpdate,
)
from app.modules.users.models import User

router = APIRouter()


@router.post("/floors", response_model=FloorRead, status_code=status.HTTP_201_CREATED)
def create_floor(
    body: FloorCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> FloorRead:
    return service.create_floor(db, current_user.tenant_id, body, current_user.brand_id)


@router.get("/floors", response_model=list[FloorRead])
def list_floors(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[FloorRead]:
    return service.list_floors_by_outlet(db, current_user.tenant_id, outlet_id)


@router.post("/tables", response_model=TableRead, status_code=status.HTTP_201_CREATED)
def create_table(
    body: TableCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.create_table(db, current_user.tenant_id, body, current_user.brand_id)


@router.get("/tables", response_model=list[TableRead])
def list_tables(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_READ)),
) -> list[TableRead]:
    return service.list_tables_by_outlet(db, current_user.tenant_id, outlet_id)


@router.patch("/tables/{table_id}/status", response_model=TableRead)
def update_table_status(
    table_id: int,
    body: TableStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.update_table_status(db, current_user.tenant_id, table_id, body)


@router.post("/tables/{table_id}/assign-waiter", response_model=TableRead)
def assign_waiter(
    table_id: int,
    body: AssignWaiterRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.assign_waiter(db, current_user.tenant_id, table_id, body)


@router.post("/tables/{table_id}/move", response_model=TableRead)
def move_table(
    table_id: int,
    body: MoveTableRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.move_table(db, current_user.tenant_id, table_id, body)


@router.post("/tables/merge", response_model=TableRead)
def merge_tables(
    body: MergeTablesRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.merge_tables(db, current_user.tenant_id, body)


@router.post("/tables/{table_id}/reserve", response_model=TableRead)
def reserve_table(
    table_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.POS_WRITE)),
) -> TableRead:
    return service.reserve_table(db, current_user.tenant_id, table_id)
