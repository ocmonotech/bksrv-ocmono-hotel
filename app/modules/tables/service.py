from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.outlets.models import Outlet
from app.modules.pos import service as pos_service
from app.modules.pos.models import Order
from app.modules.tables.models import Floor, RestaurantTable, TableStatus
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


def create_floor(
    db: Session,
    tenant_id: int,
    data: FloorCreate,
    default_brand_id: int | None = None,
) -> FloorRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    floor = Floor(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        name=data.name,
        sort_order=data.sort_order,
    )
    db.add(floor)
    db.commit()
    db.refresh(floor)
    return FloorRead.model_validate(floor)


def list_floors_by_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[FloorRead]:
    _get_outlet(db, tenant_id, outlet_id)
    floors = (
        db.query(Floor)
        .filter(Floor.tenant_id == tenant_id, Floor.outlet_id == outlet_id, Floor.is_active.is_(True))
        .order_by(Floor.sort_order, Floor.name)
        .all()
    )
    return [FloorRead.model_validate(floor) for floor in floors]


def create_table(
    db: Session,
    tenant_id: int,
    data: TableCreate,
    default_brand_id: int | None = None,
) -> TableRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    if data.floor_id is not None:
        _get_floor(db, tenant_id, data.outlet_id, data.floor_id)

    existing = (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.tenant_id == tenant_id,
            RestaurantTable.outlet_id == data.outlet_id,
            RestaurantTable.table_number == data.table_number,
            RestaurantTable.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError("Table number already exists for this outlet")

    table = RestaurantTable(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        floor_id=data.floor_id,
        table_number=data.table_number,
        capacity=data.capacity,
        status=TableStatus.AVAILABLE,
    )
    db.add(table)
    db.commit()
    db.refresh(table)
    return _to_table_read(db, table)


def list_tables_by_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[TableRead]:
    _get_outlet(db, tenant_id, outlet_id)
    tables = (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.tenant_id == tenant_id,
            RestaurantTable.outlet_id == outlet_id,
            RestaurantTable.is_active.is_(True),
        )
        .order_by(RestaurantTable.table_number)
        .all()
    )
    return [_to_table_read(db, table) for table in tables]


def update_table_status(
    db: Session,
    tenant_id: int,
    table_id: int,
    data: TableStatusUpdate,
) -> TableRead:
    table = _get_table(db, tenant_id, table_id)
    _apply_status(table, data.status)
    db.commit()
    db.refresh(table)
    return _to_table_read(db, table)


def assign_waiter(
    db: Session,
    tenant_id: int,
    table_id: int,
    data: AssignWaiterRequest,
) -> TableRead:
    table = _get_table(db, tenant_id, table_id)
    waiter = (
        db.query(User)
        .filter(User.id == data.waiter_id, User.tenant_id == tenant_id, User.is_active.is_(True))
        .first()
    )
    if waiter is None:
        raise NotFoundError("Waiter not found")

    table.assigned_waiter_id = waiter.id
    if table.status == TableStatus.AVAILABLE:
        _apply_status(table, TableStatus.OCCUPIED)

    db.commit()
    db.refresh(table)
    return _to_table_read(db, table)


def move_table(db: Session, tenant_id: int, table_id: int, data: MoveTableRequest) -> TableRead:
    source = _get_table(db, tenant_id, table_id)
    target = _get_table(db, tenant_id, data.target_table_id)

    if source.outlet_id != target.outlet_id:
        raise ConflictError("Tables must belong to the same outlet")

    if target.status not in {TableStatus.AVAILABLE, TableStatus.RESERVED}:
        raise ConflictError("Target table is not available")

    target.assigned_waiter_id = source.assigned_waiter_id
    target.current_order_id = source.current_order_id
    target.occupied_since = source.occupied_since
    _apply_status(target, source.status)

    source.assigned_waiter_id = None
    source.current_order_id = None
    source.occupied_since = None
    _apply_status(source, TableStatus.AVAILABLE)

    db.commit()
    db.refresh(target)
    return _to_table_read(db, target)


def merge_tables(
    db: Session,
    tenant_id: int,
    data: MergeTablesRequest,
) -> TableRead:
    source = _get_table(db, tenant_id, data.source_table_id)
    target = _get_table(db, tenant_id, data.target_table_id)

    if source.id == target.id:
        raise ConflictError("Cannot merge a table with itself")
    if source.outlet_id != target.outlet_id:
        raise ConflictError("Tables must belong to the same outlet")

    source_order_id = source.current_order_id
    target_order_id = target.current_order_id

    if source_order_id is None and target_order_id is None:
        raise ConflictError("No active orders to merge")

    if source_order_id and target_order_id is None:
        order = db.get(Order, source_order_id)
        if order is None or order.tenant_id != tenant_id:
            raise NotFoundError("Source order not found")
        order.table_id = target.id
        target.current_order_id = source_order_id
        target.assigned_waiter_id = source.assigned_waiter_id or target.assigned_waiter_id
        target.occupied_since = source.occupied_since or target.occupied_since
        _apply_status(target, source.status)
    elif source_order_id and target_order_id:
        pos_service.merge_orders(db, tenant_id, source_order_id, target_order_id)
        target.assigned_waiter_id = target.assigned_waiter_id or source.assigned_waiter_id
        target.occupied_since = target.occupied_since or source.occupied_since
        _apply_status(target, TableStatus.OCCUPIED)

    source.assigned_waiter_id = None
    source.current_order_id = None
    source.occupied_since = None
    _apply_status(source, TableStatus.AVAILABLE)

    db.commit()
    db.refresh(target)
    return _to_table_read(db, target)


def reserve_table(db: Session, tenant_id: int, table_id: int) -> TableRead:
    table = _get_table(db, tenant_id, table_id)
    if table.status not in {TableStatus.AVAILABLE, TableStatus.CLEANING}:
        raise ConflictError("Table cannot be reserved in its current status")

    _apply_status(table, TableStatus.RESERVED)
    db.commit()
    db.refresh(table)
    return _to_table_read(db, table)


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id)
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_floor(db: Session, tenant_id: int, outlet_id: int, floor_id: int) -> Floor:
    floor = (
        db.query(Floor)
        .filter(Floor.id == floor_id, Floor.tenant_id == tenant_id, Floor.outlet_id == outlet_id)
        .first()
    )
    if floor is None:
        raise NotFoundError("Floor not found")
    return floor


def _get_table(db: Session, tenant_id: int, table_id: int) -> RestaurantTable:
    table = (
        db.query(RestaurantTable)
        .filter(RestaurantTable.id == table_id, RestaurantTable.tenant_id == tenant_id)
        .first()
    )
    if table is None:
        raise NotFoundError("Table not found")
    return table


def _apply_status(table: RestaurantTable, status: TableStatus) -> None:
    table.status = status
    if status == TableStatus.OCCUPIED:
        if table.occupied_since is None:
            table.occupied_since = datetime.utcnow()
    elif status in {TableStatus.AVAILABLE, TableStatus.CLEANING}:
        table.assigned_waiter_id = None
        table.current_order_id = None
        table.occupied_since = None
    elif status == TableStatus.BILLING:
        if table.occupied_since is None:
            table.occupied_since = datetime.utcnow()


def _to_table_read(db: Session, table: RestaurantTable) -> TableRead:
    floor_name = None
    waiter_name = None
    running_bill = 0.0
    if table.floor_id:
        floor = db.get(Floor, table.floor_id)
        if floor is not None:
            floor_name = floor.name
    if table.assigned_waiter_id:
        waiter = db.get(User, table.assigned_waiter_id)
        if waiter is not None:
            waiter_name = waiter.full_name or waiter.email or f'User {waiter.id}'
    if table.current_order_id:
        order = db.get(Order, table.current_order_id)
        if order is not None:
            running_bill = float(order.grand_total or 0)
    return TableRead(
        id=table.id,
        tenant_id=table.tenant_id,
        brand_id=table.brand_id,
        outlet_id=table.outlet_id,
        floor_id=table.floor_id,
        floor_name=floor_name,
        table_number=table.table_number,
        capacity=table.capacity,
        status=table.status,
        assigned_waiter_id=table.assigned_waiter_id,
        waiter_name=waiter_name,
        current_order_id=table.current_order_id,
        occupied_since=table.occupied_since,
        is_active=table.is_active,
        created_at=table.created_at,
        updated_at=table.updated_at,
        running_bill=running_bill,
    )

