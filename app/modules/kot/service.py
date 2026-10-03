from __future__ import annotations

import uuid
from collections import defaultdict

from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.kot.models import KOT, KOTItem, KotItemStatus, KotStatus
from app.modules.kot.schemas import KotItemRead, KotRead, KotSummary
from app.modules.kot.websocket import schedule_kot_event
from app.modules.menu.models import MenuItem, PreparationArea
from app.modules.outlets.models import Outlet
from app.modules.pos.models import Order, OrderItem, OrderItemStatus, OrderStatus


def list_kots_by_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[KotRead]:
    _get_outlet(db, tenant_id, outlet_id)
    kots = (
        db.query(KOT)
        .options(joinedload(KOT.items))
        .filter(
            KOT.tenant_id == tenant_id,
            KOT.outlet_id == outlet_id,
            KOT.is_active.is_(True),
            KOT.status != KotStatus.CANCELLED,
        )
        .order_by(KOT.id.desc())
        .limit(100)
        .all()
    )
    return [_to_kot_read(kot) for kot in kots]


def list_kots_by_preparation_area(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    preparation_area: PreparationArea,
) -> list[KotRead]:
    _get_outlet(db, tenant_id, outlet_id)
    kots = (
        db.query(KOT)
        .options(joinedload(KOT.items))
        .filter(
            KOT.tenant_id == tenant_id,
            KOT.outlet_id == outlet_id,
            KOT.preparation_area == preparation_area,
            KOT.is_active.is_(True),
            KOT.status != KotStatus.CANCELLED,
        )
        .order_by(KOT.id.desc())
        .limit(100)
        .all()
    )
    return [_to_kot_read(kot) for kot in kots]


def get_kot(db: Session, tenant_id: int, kot_id: int) -> KotRead:
    kot = _get_kot_entity(db, tenant_id, kot_id, with_items=True)
    return _to_kot_read(kot)


def update_kot_status(db: Session, tenant_id: int, kot_id: int, status: KotStatus) -> KotRead:
    kot = _get_kot_entity(db, tenant_id, kot_id, with_items=True)
    if kot.status == KotStatus.CANCELLED:
        raise ConflictError("Cancelled KOT cannot be updated")

    kot.status = status
    if status == KotStatus.PREPARING:
        for item in kot.items:
            if item.status == KotItemStatus.NEW:
                item.status = KotItemStatus.PREPARING
    elif status == KotStatus.READY:
        for item in kot.items:
            if item.status not in {KotItemStatus.CANCELLED, KotItemStatus.SERVED}:
                item.status = KotItemStatus.READY
    elif status == KotStatus.SERVED:
        for item in kot.items:
            if item.status != KotItemStatus.CANCELLED:
                item.status = KotItemStatus.SERVED

    _sync_order_status_from_kot(db, kot)
    db.commit()
    db.refresh(kot)
    result = _to_kot_read(kot)
    schedule_kot_event(kot.outlet_id, "kot.updated", result.model_dump(mode="json"))
    return result


def update_kot_item_status(
    db: Session,
    tenant_id: int,
    kot_id: int,
    item_id: int,
    status: KotItemStatus,
) -> KotRead:
    kot = _get_kot_entity(db, tenant_id, kot_id, with_items=True)
    item = _get_kot_item(kot, item_id)
    if item.status == KotItemStatus.CANCELLED:
        raise ConflictError("Cancelled KOT item cannot be updated")

    item.status = status
    _sync_kot_status_from_items(kot)
    _sync_order_status_from_kot(db, kot)
    db.commit()
    db.refresh(kot)
    result = _to_kot_read(kot)
    schedule_kot_event(kot.outlet_id, "kot.item.updated", result.model_dump(mode="json"))
    return result


def cancel_kot_item(db: Session, tenant_id: int, kot_id: int, item_id: int) -> KotRead:
    kot = _get_kot_entity(db, tenant_id, kot_id, with_items=True)
    item = _get_kot_item(kot, item_id)
    item.status = KotItemStatus.CANCELLED
    _sync_kot_status_from_items(kot)
    db.commit()
    db.refresh(kot)
    result = _to_kot_read(kot)
    schedule_kot_event(kot.outlet_id, "kot.item.cancelled", result.model_dump(mode="json"))
    return result


def create_kots_from_order(
    db: Session,
    tenant_id: int,
    order_id: int,
    created_by: int | None = None,
) -> list[KotSummary]:
    order = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(Order.id == order_id, Order.tenant_id == tenant_id)
        .first()
    )
    if order is None:
        raise NotFoundError("Order not found")
    if order.order_status == OrderStatus.CANCELLED:
        raise ConflictError("Cancelled order cannot be sent to KOT")

    active_items = [item for item in order.items if item.status != OrderItemStatus.CANCELLED]
    if not active_items:
        raise ConflictError("Order has no active items")

    grouped: dict[PreparationArea, list[OrderItem]] = defaultdict(list)
    for order_item in active_items:
        menu_item = db.get(MenuItem, order_item.menu_item_id)
        area = menu_item.preparation_area if menu_item else PreparationArea.KITCHEN
        grouped[area].append(order_item)

    summaries: list[KotSummary] = []
    for area, items in grouped.items():
        kot = KOT(
            tenant_id=order.tenant_id,
            brand_id=order.brand_id,
            outlet_id=order.outlet_id,
            order_id=order.id,
            kot_number=_next_kot_number(),
            preparation_area=area,
            status=KotStatus.NEW,
            created_by=created_by,
        )
        db.add(kot)
        db.flush()

        for order_item in items:
            db.add(
                KOTItem(
                    kot_id=kot.id,
                    order_item_id=order_item.id,
                    item_name=order_item.item_name,
                    quantity=order_item.quantity,
                    note=order_item.note,
                    status=KotItemStatus.NEW,
                )
            )
            if order_item.status == OrderItemStatus.NEW:
                order_item.status = OrderItemStatus.PREPARING

        summaries.append(
            KotSummary(kot_id=kot.id, kot_number=kot.kot_number, preparation_area=area)
        )
        schedule_kot_event(
            order.outlet_id,
            "kot.created",
            {"kot_id": kot.id, "kot_number": kot.kot_number, "preparation_area": area.value},
        )

    order.order_status = OrderStatus.KOT_SENT
    db.commit()
    return summaries


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_kot_entity(db: Session, tenant_id: int, kot_id: int, with_items: bool = False) -> KOT:
    query = db.query(KOT).filter(KOT.id == kot_id, KOT.tenant_id == tenant_id)
    if with_items:
        query = query.options(joinedload(KOT.items))
    kot = query.first()
    if kot is None:
        raise NotFoundError("KOT not found")
    return kot


def _get_kot_item(kot: KOT, item_id: int) -> KOTItem:
    for item in kot.items:
        if item.id == item_id:
            return item
    raise NotFoundError("KOT item not found")


def _sync_kot_status_from_items(kot: KOT) -> None:
    active_items = [item for item in kot.items if item.status != KotItemStatus.CANCELLED]
    if not active_items:
        kot.status = KotStatus.CANCELLED
        return
    if all(item.status == KotItemStatus.SERVED for item in active_items):
        kot.status = KotStatus.SERVED
    elif all(item.status == KotItemStatus.READY for item in active_items):
        kot.status = KotStatus.READY
    elif any(item.status == KotItemStatus.PREPARING for item in active_items):
        kot.status = KotStatus.PREPARING


def _to_kot_read(kot: KOT) -> KotRead:
    from sqlalchemy.orm import object_session
    from app.modules.tables.models import RestaurantTable
    from app.modules.pos.service import parse_queue_token

    table_number: str | None = None
    order_type: str | None = None
    queue_token: str | None = None
    session = object_session(kot)
    if session is not None and kot.order_id:
        order = session.get(Order, kot.order_id)
        if order is not None:
            order_type = (
                order.order_type.value if hasattr(order.order_type, "value") else str(order.order_type)
            )
            queue_token = parse_queue_token(order.source_reference)
            if queue_token and order_type == "takeaway":
                table_number = f"#{queue_token}"
                if getattr(order, "pickup_at", None):
                    table_number = (
                        f"#{queue_token} · {order.pickup_at.strftime('%H:%M')}"
                    )
            elif order.table_id:
                table = session.get(RestaurantTable, order.table_id)
                if table is not None:
                    table_number = table.table_number

    return KotRead(
        id=kot.id,
        tenant_id=kot.tenant_id,
        brand_id=kot.brand_id,
        outlet_id=kot.outlet_id,
        order_id=kot.order_id,
        kot_number=kot.kot_number,
        preparation_area=kot.preparation_area,
        status=kot.status,
        created_by=kot.created_by,
        is_active=kot.is_active,
        created_at=kot.created_at,
        updated_at=kot.updated_at,
        table_number=table_number,
        order_type=order_type,
        queue_token=queue_token,
        items=[KotItemRead.model_validate(item) for item in kot.items],
    )


def _sync_order_status_from_kot(db: Session, kot: KOT) -> None:
    order = db.get(Order, kot.order_id)
    if order is None or order.order_status in {OrderStatus.BILLED, OrderStatus.CANCELLED}:
        return
    status_map = {
        KotStatus.NEW: OrderStatus.KOT_SENT,
        KotStatus.PREPARING: OrderStatus.PREPARING,
        KotStatus.READY: OrderStatus.READY,
        KotStatus.SERVED: OrderStatus.SERVED,
    }
    mapped = status_map.get(kot.status)
    if mapped and order.order_status != mapped:
        order.order_status = mapped
        for item in order.items:
            if item.status == OrderItemStatus.CANCELLED:
                continue
            if mapped == OrderStatus.PREPARING:
                item.status = OrderItemStatus.PREPARING
            elif mapped == OrderStatus.READY:
                item.status = OrderItemStatus.READY
            elif mapped == OrderStatus.SERVED:
                item.status = OrderItemStatus.SERVED


def _next_kot_number() -> str:
    return f"KOT-{uuid.uuid4().hex[:6].upper()}"
