from __future__ import annotations

import uuid
from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, ForbiddenError, NotFoundError
from app.modules.kot import service as kot_service
from app.modules.menu.models import MenuItem, MenuItemOutlet
from app.modules.outlets.models import Outlet
from app.modules.pos.models import (
    Bill,
    BillPaymentStatus,
    CancelReason,
    CancelReasonType,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderStatus,
    OrderType,
    Payment,
    PaymentMode,
    PaymentRecordStatus,
)
from app.modules.pos.schemas import (
    BillRead,
    CancelBillPlaceholderResponse,
    CancelOrderRequest,
    DiscountApprovalResponse,
    OrderCreate,
    OrderItemCreate,
    OrderItemRead,
    OrderRead,
    PaymentCreate,
    PaymentRead,
    PickupOrderRead,
    SendKotResponse,
)
from app.modules.users.models import User
from app.modules.auth import service as auth_service
from app.modules.tables.models import RestaurantTable, TableStatus

RUNNING_STATUSES = {
    OrderStatus.DRAFT,
    OrderStatus.KOT_SENT,
    OrderStatus.PREPARING,
    OrderStatus.READY,
    OrderStatus.SERVED,
}

SERVICE_CHARGE_RATE = 0.0
QUEUE_TOKEN_MARKER = "token"


def parse_queue_token(source_reference: str | None) -> str | None:
    if not source_reference:
        return None
    parts = source_reference.split(":")
    for i, part in enumerate(parts):
        if part == QUEUE_TOKEN_MARKER and i + 1 < len(parts):
            token = parts[i + 1].strip()
            if token.isdigit():
                return token
    return None


def _next_queue_token(db: Session, outlet_id: int) -> str:
    start = datetime.combine(date.today(), datetime.min.time())
    rows = (
        db.query(Order.source_reference)
        .filter(
            Order.outlet_id == outlet_id,
            Order.order_type == OrderType.TAKEAWAY,
            Order.is_active.is_(True),
            Order.created_at >= start,
        )
        .all()
    )
    max_token = 0
    for (ref,) in rows:
        token = parse_queue_token(ref)
        if token and token.isdigit():
            max_token = max(max_token, int(token))
    return str(max_token + 1)


def _embed_queue_token(source_reference: str | None, token: str) -> str:
    base = (source_reference or "").strip()
    if parse_queue_token(base):
        return base[:128]
    marker = f"{QUEUE_TOKEN_MARKER}:{token}"
    if not base:
        return marker[:128]
    return f"{base}:{marker}"[:128]


DEFAULT_CLICK_COLLECT = {
    "enabled": True,
    "open": "08:00",
    "close": "22:00",
    "slot_minutes": 15,
    "prep_sla_minutes": 20,
    "min_lead_minutes": 20,
    "horizon_hours": 4,
}


def _parse_hhmm(value: str) -> tuple[int, int]:
    parts = (value or "00:00").strip().split(":")
    hour = int(parts[0]) if parts and parts[0].isdigit() else 0
    minute = int(parts[1]) if len(parts) > 1 and parts[1].isdigit() else 0
    return hour, minute


def get_click_collect_config(db: Session, tenant_id: int, outlet_id: int) -> dict:
    from app.modules.settings.service import get_outlet_settings

    settings = get_outlet_settings(db, tenant_id, outlet_id).settings
    pos = settings.get("pos") or {}
    raw = pos.get("click_collect") if isinstance(pos, dict) else None
    if not isinstance(raw, dict):
        return dict(DEFAULT_CLICK_COLLECT)
    merged = dict(DEFAULT_CLICK_COLLECT)
    merged.update({k: v for k, v in raw.items() if k in DEFAULT_CLICK_COLLECT})
    return merged


def build_click_collect_slots(cfg: dict, now: datetime | None = None) -> list[datetime]:
    if not cfg.get("enabled", True):
        return []
    now = now or datetime.utcnow()
    slot_minutes = max(5, int(cfg.get("slot_minutes") or 15))
    prep_sla = max(0, int(cfg.get("prep_sla_minutes") or 20))
    min_lead = max(prep_sla, int(cfg.get("min_lead_minutes") or prep_sla))
    horizon_hours = max(1, int(cfg.get("horizon_hours") or 4))
    open_h, open_m = _parse_hhmm(str(cfg.get("open") or "08:00"))
    close_h, close_m = _parse_hhmm(str(cfg.get("close") or "22:00"))

    day_start = datetime.combine(now.date(), datetime.min.time()).replace(
        hour=open_h, minute=open_m, second=0, microsecond=0
    )
    day_end = datetime.combine(now.date(), datetime.min.time()).replace(
        hour=close_h, minute=close_m, second=0, microsecond=0
    )
    earliest = now + timedelta(minutes=min_lead)
    latest = now + timedelta(hours=horizon_hours)

    # Align first candidate to slot grid at/after earliest
    cursor = day_start
    if earliest > cursor:
        minutes_from_open = int((earliest - day_start).total_seconds() // 60)
        steps = (minutes_from_open + slot_minutes - 1) // slot_minutes
        cursor = day_start + timedelta(minutes=steps * slot_minutes)

    slots: list[datetime] = []
    while cursor <= day_end and cursor <= latest:
        if cursor >= earliest and cursor <= day_end:
            slots.append(cursor)
        cursor += timedelta(minutes=slot_minutes)
    return slots


def resolve_takeaway_schedule(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    requested_pickup: datetime | None,
) -> tuple[datetime, datetime]:
    """Return (pickup_at, ready_at) for takeaway / click & collect."""
    cfg = get_click_collect_config(db, tenant_id, outlet_id)
    now = datetime.utcnow()
    prep_sla = max(0, int(cfg.get("prep_sla_minutes") or 20))
    asap_ready = now + timedelta(minutes=prep_sla)

    if not cfg.get("enabled", True):
        pickup = requested_pickup or asap_ready
        return pickup, min(pickup, asap_ready) if requested_pickup else asap_ready

    slots = build_click_collect_slots(cfg, now)
    if requested_pickup is None:
        pickup = slots[0] if slots else asap_ready
    else:
        candidate = requested_pickup.replace(tzinfo=None) if requested_pickup.tzinfo else requested_pickup
        matched = None
        for slot in slots:
            if abs((slot - candidate).total_seconds()) <= 120:
                matched = slot
                break
            if slot.replace(second=0, microsecond=0) == candidate.replace(second=0, microsecond=0):
                matched = slot
                break
        if matched is None:
            raise ConflictError("Selected pickup time is not available. Choose another slot.")
        pickup = matched

    if pickup <= asap_ready + timedelta(minutes=2):
        ready = min(pickup, asap_ready)
    else:
        ready = pickup - timedelta(minutes=min(5, prep_sla or 5))
        if ready < now:
            ready = now
    return pickup, ready


def _guest_name_from_source(source_reference: str | None) -> str | None:
    bits = (source_reference or "").split(":")
    for bit in bits:
        if bit in {"qr_menu", "pos", QUEUE_TOKEN_MARKER} or bit.isdigit():
            continue
        if bit.startswith("room_service"):
            continue
        if bit.replace("+", "").replace(" ", "").isdigit() and len(bit) >= 8:
            continue
        return bit
    return None


def create_order(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: OrderCreate,
    default_brand_id: int | None = None,
) -> OrderRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    source_reference = None
    pickup_at = None
    ready_at = None
    if data.order_type == OrderType.TAKEAWAY:
        token = _next_queue_token(db, data.outlet_id)
        source_reference = _embed_queue_token("pos", token)
        pickup_at, ready_at = resolve_takeaway_schedule(db, tenant_id, data.outlet_id, None)

    order = Order(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        table_id=data.table_id,
        customer_id=data.customer_id,
        order_number=_next_order_number(),
        order_type=data.order_type,
        order_status=OrderStatus.DRAFT,
        source_reference=source_reference,
        pickup_at=pickup_at,
        ready_at=ready_at,
        created_by=user_id,
    )
    db.add(order)
    db.flush()

    if data.table_id is not None:
        table = _get_table(db, tenant_id, data.table_id)
        if table.current_order_id and table.current_order_id != order.id:
            raise ConflictError("Table already has an active order")
        table.current_order_id = order.id
        table.status = TableStatus.OCCUPIED
        table.occupied_since = datetime.utcnow()

    db.commit()
    return get_order(db, tenant_id, order.id)


def add_item(db: Session, tenant_id: int, order_id: int, data: OrderItemCreate) -> OrderRead:
    from app.modules.menu.models import ItemAddon

    order = _get_order_entity(db, tenant_id, order_id)
    _ensure_editable(order)

    menu_item, price = _resolve_menu_item_price(db, order.outlet_id, data.menu_item_id)
    addon_names: list[str] = []
    addon_extra = 0.0
    if data.addon_ids:
        addons = (
            db.query(ItemAddon)
            .filter(
                ItemAddon.tenant_id == tenant_id,
                ItemAddon.menu_item_id == menu_item.id,
                ItemAddon.id.in_(data.addon_ids),
                ItemAddon.is_active.is_(True),
            )
            .all()
        )
        found_ids = {addon.id for addon in addons}
        missing = [addon_id for addon_id in data.addon_ids if addon_id not in found_ids]
        if missing:
            raise ConflictError(f"Invalid addons for item: {missing}")
        for addon in addons:
            addon_extra += float(addon.price)
            addon_names.append(addon.addon_name)

    note_parts: list[str] = []
    if data.note:
        note_parts.append(data.note)
    if addon_names:
        note_parts.append("Addons: " + ", ".join(addon_names))

    line = OrderItem(
        tenant_id=order.tenant_id,
        brand_id=order.brand_id,
        order_id=order.id,
        menu_item_id=menu_item.id,
        item_name=menu_item.item_name,
        quantity=data.quantity,
        price=round(price + addon_extra, 2),
        discount_amount=data.discount_amount,
        gst_percent=float(menu_item.gst_percent),
        note=(" · ".join(note_parts)[:255] if note_parts else None),
        status=OrderItemStatus.NEW,
    )
    db.add(line)
    db.flush()
    db.expire(order, ["items"])
    order = _get_order_entity(db, tenant_id, order_id, with_items=True)
    _recalculate_order(order)
    db.commit()
    db.expire_all()
    return get_order(db, tenant_id, order.id)


def update_item_quantity(
    db: Session,
    tenant_id: int,
    order_id: int,
    item_id: int,
    quantity: int,
) -> OrderRead:
    order = _get_order_entity(db, tenant_id, order_id)
    _ensure_editable(order)
    item = _get_order_item(db, order, item_id)
    if item.status == OrderItemStatus.CANCELLED:
        raise ConflictError("Cannot update a cancelled item")

    item.quantity = quantity
    _recalculate_order(order)
    db.commit()
    return get_order(db, tenant_id, order.id)


def remove_item(db: Session, tenant_id: int, order_id: int, item_id: int) -> OrderRead:
    order = _get_order_entity(db, tenant_id, order_id)
    _ensure_editable(order)
    item = _get_order_item(db, order, item_id)
    item.status = OrderItemStatus.CANCELLED
    item.is_active = False
    _recalculate_order(order)
    db.commit()
    return get_order(db, tenant_id, order.id)


def send_order_to_kot(
    db: Session,
    tenant_id: int,
    order_id: int,
    user_id: int | None = None,
) -> SendKotResponse:
    kots = kot_service.create_kots_from_order(db, tenant_id, order_id, created_by=user_id)
    order = _get_order_entity(db, tenant_id, order_id, with_items=True)

    from app.modules.inventory import service as inventory_service

    inventory_service.deduct_stock_for_order(
        db,
        tenant_id=tenant_id,
        outlet_id=order.outlet_id,
        brand_id=order.brand_id,
        order=order,
        user_id=user_id,
    )

    return SendKotResponse(
        order_id=order.id,
        order_status=order.order_status,
        kots=kots,
        message="Order sent to KOT and inventory updated",
    )


def submit_guest_menu_order(db: Session, data) -> "PublicMenuOrderResponse":
    from app.modules.menu.models import Combo, ItemAddon
    from app.modules.menu.schemas import PublicMenuOrderResponse

    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    tenant_id = outlet.tenant_id
    order_type_raw = (data.order_type or "dine_in").lower().replace("-", "_")
    is_room_service = order_type_raw == "room_service"
    room_number = (data.room_number or "").strip() or None

    if is_room_service:
        if not room_number:
            raise ConflictError("Room number is required for room service")
        order_type = OrderType.DELIVERY
    else:
        try:
            order_type = OrderType(order_type_raw)
        except ValueError:
            order_type = OrderType.DINE_IN

    table = None
    order: Order | None = None
    table_id = None if is_room_service else data.table_id
    if table_id is not None:
        table = _get_table(db, tenant_id, table_id)
        if table.outlet_id != outlet.id:
            raise ConflictError("Table does not belong to this outlet")
        if table.current_order_id:
            existing = _get_order_entity(db, tenant_id, table.current_order_id, with_items=True)
            if existing.order_status in RUNNING_STATUSES:
                order = existing

    source_bits = ["qr_menu"]
    if is_room_service:
        source_bits.append(f"room_service:{room_number}")
    if data.guest_name:
        source_bits.append(data.guest_name)
    if data.guest_mobile:
        source_bits.append(data.guest_mobile)

    queue_token: str | None = None
    pickup_at: datetime | None = None
    ready_at: datetime | None = None
    if order_type == OrderType.TAKEAWAY:
        queue_token = _next_queue_token(db, outlet.id)
        source_bits.append(f"{QUEUE_TOKEN_MARKER}:{queue_token}")
        pickup_at, ready_at = resolve_takeaway_schedule(
            db, tenant_id, outlet.id, getattr(data, "pickup_at", None)
        )

    if order is None:
        order = Order(
            tenant_id=tenant_id,
            brand_id=outlet.brand_id,
            outlet_id=outlet.id,
            table_id=table_id,
            order_number=_next_order_number(),
            order_type=order_type,
            order_status=OrderStatus.DRAFT,
            source_reference=":".join(source_bits)[:128],
            pickup_at=pickup_at,
            ready_at=ready_at,
            created_by=None,
        )
        db.add(order)
        db.flush()
        if table is not None:
            table.current_order_id = order.id
            table.status = TableStatus.OCCUPIED
            table.occupied_since = datetime.utcnow()
    elif order_type == OrderType.TAKEAWAY and pickup_at and not order.pickup_at:
        order.pickup_at = pickup_at
        order.ready_at = ready_at
        if queue_token and not parse_queue_token(order.source_reference):
            order.source_reference = _embed_queue_token(order.source_reference, queue_token)

    for line in data.items:
        if line.combo_id:
            combo = (
                db.query(Combo)
                .options(joinedload(Combo.items))
                .filter(
                    Combo.id == line.combo_id,
                    Combo.tenant_id == tenant_id,
                    Combo.is_active.is_(True),
                )
                .first()
            )
            if combo is None or not combo.items:
                raise NotFoundError(f"Combo {line.combo_id} not found")
            for index, combo_line in enumerate(combo.items):
                menu_item, _unit = _resolve_menu_item_price(db, outlet.id, combo_line.menu_item_id)
                note_parts = [f"Combo: {combo.combo_name}"]
                if line.note:
                    note_parts.append(line.note)
                db.add(
                    OrderItem(
                        tenant_id=tenant_id,
                        brand_id=outlet.brand_id,
                        order_id=order.id,
                        menu_item_id=menu_item.id,
                        item_name=(
                            f"{combo.combo_name} · {menu_item.item_name}"
                            if index == 0
                            else menu_item.item_name
                        ),
                        quantity=max(1, int(combo_line.quantity)) * line.quantity,
                        price=float(combo.combo_price) if index == 0 else 0.0,
                        discount_amount=0,
                        gst_percent=float(menu_item.gst_percent),
                        note=" · ".join(note_parts)[:255],
                        status=OrderItemStatus.NEW,
                    )
                )
            continue

        if not line.menu_item_id:
            raise ConflictError("Each order line needs a menu item or combo")

        menu_item, price = _resolve_menu_item_price(db, outlet.id, line.menu_item_id)
        addon_names: list[str] = []
        addon_extra = 0.0
        if line.addon_ids:
            addons = (
                db.query(ItemAddon)
                .filter(
                    ItemAddon.tenant_id == tenant_id,
                    ItemAddon.menu_item_id == menu_item.id,
                    ItemAddon.id.in_(line.addon_ids),
                    ItemAddon.is_active.is_(True),
                )
                .all()
            )
            found_ids = {addon.id for addon in addons}
            missing = [addon_id for addon_id in line.addon_ids if addon_id not in found_ids]
            if missing:
                raise ConflictError(f"Invalid addons for item: {missing}")
            for addon in addons:
                addon_extra += float(addon.price)
                addon_names.append(addon.addon_name)

        note_parts = []
        if line.note:
            note_parts.append(line.note)
        if addon_names:
            note_parts.append("Addons: " + ", ".join(addon_names))
        if is_room_service and room_number:
            note_parts.append(f"Room {room_number}")

        db.add(
            OrderItem(
                tenant_id=tenant_id,
                brand_id=outlet.brand_id,
                order_id=order.id,
                menu_item_id=menu_item.id,
                item_name=menu_item.item_name,
                quantity=line.quantity,
                price=round(price + addon_extra, 2),
                discount_amount=0,
                gst_percent=float(menu_item.gst_percent),
                note=(" · ".join(note_parts)[:255] if note_parts else None),
                status=OrderItemStatus.NEW,
            )
        )

    db.flush()
    order = _get_order_entity(db, tenant_id, order.id, with_items=True)
    _recalculate_order(order)
    db.commit()

    kot_sent = False
    if data.send_to_kot:
        send_order_to_kot(db, tenant_id, order.id, user_id=None)
        kot_sent = True
        order = _get_order_entity(db, tenant_id, order.id, with_items=True)

    from urllib.parse import quote
    from app.core.config import settings

    amount = float(order.grand_total)
    upi_deeplink = (
        f"upi://pay?pa={quote(settings.guest_upi_vpa)}"
        f"&pn={quote(settings.guest_upi_payee_name)}"
        f"&am={amount:.2f}&cu=INR&tn={quote(f'Order {order.order_number}')}"
    )

    message = "Order sent to kitchen" if kot_sent else "Order received — wait staff will confirm"
    if is_room_service and room_number:
        message = f"Room service for {room_number} - kitchen notified"
    if queue_token:
        message = f"Token #{queue_token} — {message}"
    final_pickup = order.pickup_at or pickup_at
    if final_pickup:
        message = f"{message} · Pickup by {final_pickup.strftime('%I:%M %p').lstrip('0')}"

    return PublicMenuOrderResponse(
        order_id=order.id,
        order_number=order.order_number,
        order_status=order.order_status.value,
        grand_total=amount,
        table_number=table.table_number if table else None,
        room_number=room_number,
        queue_token=queue_token or parse_queue_token(order.source_reference),
        pickup_at=final_pickup,
        ready_at=order.ready_at or ready_at,
        message=message,
        kot_sent=kot_sent,
        notify_stub="We'll notify you when ready (SMS coming soon)" if order_type == OrderType.TAKEAWAY else None,
        upi_vpa=settings.guest_upi_vpa,
        upi_payee_name=settings.guest_upi_payee_name,
        upi_deeplink=upi_deeplink,
    )


def pay_guest_menu_order(db: Session, data) -> "PublicMenuPayResponse":
    from app.modules.menu.schemas import PublicMenuPayResponse

    order = (
        db.query(Order)
        .filter(Order.id == data.order_id, Order.order_number == data.order_number)
        .first()
    )
    if order is None:
        raise NotFoundError("Order not found")

    tenant_id = order.tenant_id
    mode_raw = (data.payment_mode or "upi").lower()
    if mode_raw not in {"upi", "online", "pay_later"}:
        raise ConflictError("Unsupported payment mode")

    if mode_raw == "pay_later":
        return PublicMenuPayResponse(
            order_id=order.id,
            order_number=order.order_number,
            bill_id=0,
            bill_number="",
            payment_status="unpaid",
            grand_total=float(order.grand_total),
            message="Pay at the counter when ready",
            paid=False,
        )

    existing_bill = (
        db.query(Bill)
        .filter(Bill.order_id == order.id, Bill.payment_status != BillPaymentStatus.CANCELLED)
        .order_by(Bill.id.desc())
        .first()
    )
    if existing_bill and existing_bill.payment_status == BillPaymentStatus.PAID:
        return PublicMenuPayResponse(
            order_id=order.id,
            order_number=order.order_number,
            bill_id=existing_bill.id,
            bill_number=existing_bill.bill_number,
            payment_status=existing_bill.payment_status.value,
            grand_total=float(existing_bill.grand_total),
            message="Already paid",
            paid=True,
        )

    if existing_bill is None:
        if order.order_status == OrderStatus.CANCELLED:
            raise ConflictError("Cancelled order cannot be paid")
        bill = generate_bill(db, tenant_id, user_id=None, order_id=order.id)
    else:
        bill = BillRead.model_validate(existing_bill)

    reference = data.reference_number or f"UPI-{uuid.uuid4().hex[:10].upper()}"
    # MySQL ENUM for payment_mode stores member names (UPI), not values (upi).
    from sqlalchemy import text

    db.execute(
        text(
            """
            INSERT INTO pos_payments (bill_id, payment_mode, amount, reference_number, status)
            VALUES (:bill_id, :mode, :amount, :ref, :status)
            """
        ),
        {
            "bill_id": bill.id,
            "mode": "UPI" if mode_raw == "upi" else "ONLINE",
            "amount": float(bill.grand_total),
            "ref": reference,
            "status": "SUCCESS",
        },
    )
    db.flush()

    paid_total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.bill_id == bill.id)
        .scalar()
    )
    paid_total = float(paid_total or 0)
    bill_entity = _get_bill_entity(db, tenant_id, bill.id, for_update=True)
    if paid_total >= float(bill_entity.grand_total):
        bill_entity.payment_status = BillPaymentStatus.PAID
        order_entity = _get_order_entity(db, tenant_id, bill_entity.order_id)
        if order_entity.table_id:
            table = db.get(RestaurantTable, order_entity.table_id)
            if table:
                table.status = TableStatus.AVAILABLE
                table.current_order_id = None
                table.assigned_waiter_id = None
                table.occupied_since = None
    elif paid_total > 0:
        bill_entity.payment_status = BillPaymentStatus.PARTIAL
    db.commit()

    refreshed = _get_bill_entity(db, tenant_id, bill.id)
    return PublicMenuPayResponse(
        order_id=order.id,
        order_number=order.order_number,
        bill_id=refreshed.id,
        bill_number=refreshed.bill_number,
        payment_status=refreshed.payment_status.value,
        grand_total=float(refreshed.grand_total),
        message="Payment received via UPI",
        paid=refreshed.payment_status == BillPaymentStatus.PAID,
    )


def charge_guest_menu_order_to_room(db: Session, data) -> "PublicRoomChargeResponse":
    from app.modules.menu.schemas import PublicRoomChargeResponse, PublicRoomVerifyRequest
    from app.modules.pms import service as pms_service
    from app.modules.pms.schemas import PostToRoomRequest

    order = (
        db.query(Order)
        .filter(Order.id == data.order_id, Order.order_number == data.order_number)
        .first()
    )
    if order is None:
        raise NotFoundError("Order not found")
    if order.order_status == OrderStatus.CANCELLED:
        raise ConflictError("Cancelled order cannot be charged to room")

    guest = pms_service.verify_public_room_guest(
        db,
        PublicRoomVerifyRequest(
            outlet_id=order.outlet_id,
            room_number=data.room_number,
            guest_mobile=data.guest_mobile,
        ),
    )

    existing_bill = (
        db.query(Bill)
        .filter(Bill.order_id == order.id, Bill.payment_status != BillPaymentStatus.CANCELLED)
        .order_by(Bill.id.desc())
        .first()
    )
    if existing_bill and existing_bill.payment_status == BillPaymentStatus.PAID:
        raise ConflictError("Order is already paid")

    if existing_bill is None:
        bill = generate_bill(db, order.tenant_id, user_id=None, order_id=order.id)
        bill_id = bill.id
        bill_number = bill.bill_number
    else:
        bill_id = existing_bill.id
        bill_number = existing_bill.bill_number

    posted = pms_service.post_bill_to_room(
        db,
        order.tenant_id,
        user_id=None,
        data=PostToRoomRequest(
            bill_id=bill_id,
            reservation_id=guest.reservation_id,
            description=f"Guest menu · {order.order_number} · Room {guest.room_number}",
        ),
    )

    return PublicRoomChargeResponse(
        order_id=order.id,
        order_number=order.order_number,
        bill_id=posted.bill_id,
        bill_number=bill_number,
        reservation_id=posted.reservation_id,
        room_number=guest.room_number,
        guest_name=guest.guest_name,
        amount=float(posted.amount),
        message=f"Charged to room {guest.room_number} · {guest.guest_name}",
        paid=True,
    )


def generate_bill(db: Session, tenant_id: int, user_id: int | None, order_id: int) -> BillRead:
    try:
        order = _get_order_entity(db, tenant_id, order_id, with_items=True, for_update=True)
        if order.order_status in {OrderStatus.CANCELLED, OrderStatus.BILLED}:
            raise ConflictError("Order cannot be billed in its current status")
        if not any(item.status != OrderItemStatus.CANCELLED for item in order.items):
            raise ConflictError("Order has no billable items")

        _recalculate_order(order)
        round_off, grand_total = _apply_round_off(float(order.grand_total))

        bill = Bill(
            tenant_id=order.tenant_id,
            brand_id=order.brand_id,
            outlet_id=order.outlet_id,
            order_id=order.id,
            bill_number=_next_bill_number(),
            subtotal=order.subtotal,
            discount_amount=order.discount_amount,
            service_charge=order.service_charge,
            gst_amount=order.gst_amount,
            round_off=round_off,
            grand_total=grand_total,
            payment_status=BillPaymentStatus.UNPAID,
            created_by=user_id,
        )
        db.add(bill)
        order.order_status = OrderStatus.BILLED

        if order.table_id:
            table = db.get(RestaurantTable, order.table_id)
            if table:
                table.status = TableStatus.BILLING

        db.commit()
        db.refresh(bill)
        return BillRead.model_validate(bill)
    except Exception:
        db.rollback()
        raise


def add_payment(db: Session, tenant_id: int, bill_id: int, data: PaymentCreate, user_id: int | None = None) -> PaymentRead:
    try:
        bill = _get_bill_entity(db, tenant_id, bill_id, for_update=True)
        if bill.payment_status == BillPaymentStatus.CANCELLED:
            raise ConflictError("Bill is cancelled")
        if bill.payment_status == BillPaymentStatus.PAID:
            raise ConflictError("Bill is already fully paid")

        order = _get_order_entity(db, tenant_id, bill.order_id)

        if data.payment_mode == PaymentMode.LOYALTY:
            if not order.customer_id:
                raise ConflictError("Attach a customer to redeem loyalty points")
            if not data.loyalty_points:
                raise ConflictError("loyalty_points is required for loyalty payment")
            from app.modules.loyalty import service as loyalty_service

            loyalty_service.burn_for_pos_payment(
                db,
                tenant_id,
                customer_id=order.customer_id,
                bill_id=bill.id,
                points=int(data.loyalty_points),
                amount=float(data.amount),
                outlet_id=order.outlet_id,
                brand_id=order.brand_id,
                user_id=user_id,
            )

        payment = Payment(
            bill_id=bill.id,
            payment_mode=data.payment_mode,
            amount=data.amount,
            tip_amount=float(data.tip_amount or 0),
            reference_number=data.reference_number
            or (f"LOYALTY:{data.loyalty_points}" if data.payment_mode == PaymentMode.LOYALTY else None),
            status=PaymentRecordStatus.SUCCESS,
        )
        db.add(payment)
        db.flush()

        paid_total = (
            db.query(func.coalesce(func.sum(Payment.amount), 0))
            .filter(Payment.bill_id == bill.id, Payment.status == PaymentRecordStatus.SUCCESS)
            .scalar()
        )
        paid_total = float(paid_total or 0)

        if paid_total >= float(bill.grand_total):
            bill.payment_status = BillPaymentStatus.PAID
            if order.table_id:
                table = db.get(RestaurantTable, order.table_id)
                if table:
                    table.status = TableStatus.AVAILABLE
                    table.current_order_id = None
                    table.assigned_waiter_id = None
                    table.occupied_since = None

            from app.modules.loyalty import service as loyalty_service

            loyalty_service.earn_from_pos_bill(db, tenant_id, bill, order, user_id=user_id)
        elif paid_total > 0:
            bill.payment_status = BillPaymentStatus.PARTIAL

        db.commit()
        db.refresh(payment)
        return PaymentRead.model_validate(payment)
    except Exception:
        db.rollback()
        raise


def cancel_order(
    db: Session,
    tenant_id: int,
    user_id: int,
    order_id: int,
    data: CancelOrderRequest,
) -> OrderRead:
    order = _get_order_entity(db, tenant_id, order_id, with_items=True)
    if order.order_status == OrderStatus.BILLED:
        raise ConflictError("Billed order cannot be cancelled")

    db.add(
        CancelReason(
            tenant_id=tenant_id,
            brand_id=order.brand_id,
            reason_type=data.reason_type,
            reason_text=data.reason_text,
        )
    )
    order.order_status = OrderStatus.CANCELLED
    for item in order.items:
        if item.status != OrderItemStatus.CANCELLED:
            item.status = OrderItemStatus.CANCELLED

    if order.table_id:
        table = db.get(RestaurantTable, order.table_id)
        if table and table.current_order_id == order.id:
            table.status = TableStatus.AVAILABLE
            table.current_order_id = None
            table.assigned_waiter_id = None
            table.occupied_since = None

    db.commit()
    return get_order(db, tenant_id, order.id)


def merge_orders(db: Session, tenant_id: int, source_order_id: int, target_order_id: int) -> None:
    source_order = _get_order_entity(db, tenant_id, source_order_id, with_items=True)
    target_order = _get_order_entity(db, tenant_id, target_order_id, with_items=True)

    if source_order.outlet_id != target_order.outlet_id:
        raise ConflictError("Orders must belong to the same outlet")
    if source_order.order_status in {OrderStatus.BILLED, OrderStatus.CANCELLED}:
        raise ConflictError("Source order cannot be merged")
    if target_order.order_status in {OrderStatus.BILLED, OrderStatus.CANCELLED}:
        raise ConflictError("Target order cannot receive merged items")

    for item in source_order.items:
        if item.status == OrderItemStatus.CANCELLED or not item.is_active:
            continue
        item.order_id = target_order.id

    source_order.order_status = OrderStatus.CANCELLED
    _recalculate_order(target_order)


def cancel_bill(
    db: Session,
    tenant_id: int,
    user: User,
    bill_id: int,
    reason_text: str,
) -> CancelBillPlaceholderResponse:
    bill = _get_bill_entity(db, tenant_id, bill_id)
    if bill.payment_status == BillPaymentStatus.PAID and not auth_service.user_can_approve_pos_actions(user):
        raise ForbiddenError("Paid bills require manager approval to cancel")

    old_status = bill.payment_status.value
    order = _get_order_entity(db, tenant_id, bill.order_id)

    db.add(
        CancelReason(
            tenant_id=tenant_id,
            brand_id=bill.brand_id,
            reason_type=CancelReasonType.BILL,
            reason_text=reason_text,
        )
    )

    if bill.payment_status == BillPaymentStatus.PAID:
        bill.payment_status = BillPaymentStatus.REFUNDED
        for payment in bill.payments:
            payment.status = PaymentRecordStatus.FAILED
    else:
        bill.payment_status = BillPaymentStatus.CANCELLED

    if order.order_status != OrderStatus.CANCELLED:
        order.order_status = OrderStatus.CANCELLED

    if order.table_id:
        table = db.get(RestaurantTable, order.table_id)
        if table and table.current_order_id == order.id:
            table.status = TableStatus.AVAILABLE
            table.current_order_id = None
            table.assigned_waiter_id = None
            table.occupied_since = None

    from app.modules.audit.models import AuditAction
    from app.modules.audit.service import log_audit

    log_audit(
        db,
        tenant_id=tenant_id,
        brand_id=bill.brand_id,
        outlet_id=bill.outlet_id,
        user_id=user.id,
        action=AuditAction.BILL_CANCELLED.value,
        module_name="pos",
        record_type="bill",
        record_id=bill.id,
        old_data={"payment_status": old_status, "reason_text": reason_text},
        new_data={"payment_status": bill.payment_status.value, "reason_text": reason_text},
    )

    db.commit()
    return CancelBillPlaceholderResponse(
        message="Bill cancelled successfully",
        bill_id=bill.id,
    )


def approve_order_discount(
    db: Session,
    tenant_id: int,
    user_id: int,
    order_id: int,
    notes: str | None = None,
) -> DiscountApprovalResponse:
    order = _get_order_entity(db, tenant_id, order_id, with_items=True)
    if float(order.discount_amount) <= 0:
        raise ConflictError("Order has no discount to approve")

    from app.modules.audit.models import AuditAction
    from app.modules.audit.service import log_audit

    log_audit(
        db,
        tenant_id=tenant_id,
        brand_id=order.brand_id,
        outlet_id=order.outlet_id,
        user_id=user_id,
        action=AuditAction.DISCOUNT_APPROVED.value,
        module_name="pos",
        record_type="order",
        record_id=order.id,
        old_data={
            "discount_amount": float(order.discount_amount),
            "grand_total": float(order.grand_total),
            "approved": False,
        },
        new_data={
            "discount_amount": float(order.discount_amount),
            "grand_total": float(order.grand_total),
            "approved": True,
            "notes": notes,
        },
    )
    db.commit()
    return DiscountApprovalResponse(
        message="Discount approved",
        order_id=order.id,
        discount_amount=float(order.discount_amount),
    )


def get_running_orders(db: Session, tenant_id: int, outlet_id: int) -> list[OrderRead]:
    _get_outlet(db, tenant_id, outlet_id)
    orders = (
        db.query(Order)
        .options(joinedload(Order.items))
        .filter(
            Order.tenant_id == tenant_id,
            Order.outlet_id == outlet_id,
            Order.order_status.in_(RUNNING_STATUSES),
        )
        .order_by(Order.id.desc())
        .all()
    )
    return [_to_order_read(order) for order in orders]


def get_public_queue_board(db: Session, outlet_id: int):
    from app.modules.menu.schemas import PublicQueueBoardItem, PublicQueueBoardResponse

    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    start = datetime.combine(date.today(), datetime.min.time())
    orders = (
        db.query(Order)
        .filter(
            Order.outlet_id == outlet_id,
            Order.order_type == OrderType.TAKEAWAY,
            Order.is_active.is_(True),
            Order.created_at >= start,
            Order.order_status.in_(
                [OrderStatus.KOT_SENT, OrderStatus.PREPARING, OrderStatus.READY]
            ),
        )
        .order_by(Order.created_at.asc())
        .all()
    )

    preparing: list = []
    ready: list = []
    upcoming: list = []
    now = datetime.utcnow()
    for order in orders:
        token = parse_queue_token(order.source_reference)
        if not token:
            continue
        item = PublicQueueBoardItem(
            order_id=order.id,
            order_number=order.order_number,
            queue_token=token,
            order_status=order.order_status.value,
            guest_name=_guest_name_from_source(order.source_reference),
            pickup_at=order.pickup_at,
            ready_at=order.ready_at,
        )
        if order.order_status == OrderStatus.READY:
            ready.append(item)
        else:
            preparing.append(item)
        if order.pickup_at and order.pickup_at >= now - timedelta(minutes=30):
            upcoming.append(item)

    upcoming.sort(key=lambda row: row.pickup_at or now)

    return PublicQueueBoardResponse(
        outlet_id=outlet_id,
        preparing=preparing,
        ready=ready,
        upcoming_pickups=upcoming,
    )


def list_pickup_orders(db: Session, tenant_id: int, outlet_id: int) -> list[PickupOrderRead]:
    _get_outlet(db, tenant_id, outlet_id)
    start = datetime.combine(date.today(), datetime.min.time())
    end = start + timedelta(days=1)
    orders = (
        db.query(Order)
        .filter(
            Order.tenant_id == tenant_id,
            Order.outlet_id == outlet_id,
            Order.order_type == OrderType.TAKEAWAY,
            Order.is_active.is_(True),
            Order.pickup_at.isnot(None),
            Order.pickup_at >= start,
            Order.pickup_at < end,
            Order.order_status.in_(
                [OrderStatus.KOT_SENT, OrderStatus.PREPARING, OrderStatus.READY, OrderStatus.DRAFT]
            ),
        )
        .order_by(Order.pickup_at.asc())
        .all()
    )
    return [
        PickupOrderRead(
            order_id=order.id,
            order_number=order.order_number,
            queue_token=parse_queue_token(order.source_reference),
            guest_name=_guest_name_from_source(order.source_reference),
            order_status=order.order_status,
            pickup_at=order.pickup_at,
            ready_at=order.ready_at,
            grand_total=float(order.grand_total),
        )
        for order in orders
    ]


def get_bills_by_outlet(db: Session, tenant_id: int, outlet_id: int) -> list[BillRead]:
    _get_outlet(db, tenant_id, outlet_id)
    bills = (
        db.query(Bill)
        .filter(Bill.tenant_id == tenant_id, Bill.outlet_id == outlet_id)
        .order_by(Bill.id.desc())
        .limit(100)
        .all()
    )
    return [BillRead.model_validate(bill) for bill in bills]


def get_order(db: Session, tenant_id: int, order_id: int) -> OrderRead:
    order = _get_order_entity(db, tenant_id, order_id, with_items=True)
    return _to_order_read(order)


def _get_order_entity(
    db: Session,
    tenant_id: int,
    order_id: int,
    with_items: bool = False,
    for_update: bool = False,
) -> Order:
    query = db.query(Order).filter(Order.id == order_id, Order.tenant_id == tenant_id)
    if with_items:
        query = query.options(joinedload(Order.items))
    if for_update:
        query = query.with_for_update()
    order = query.first()
    if order is None:
        raise NotFoundError("Order not found")
    return order


def _get_bill_entity(
    db: Session,
    tenant_id: int,
    bill_id: int,
    for_update: bool = False,
) -> Bill:
    query = db.query(Bill).filter(Bill.id == bill_id, Bill.tenant_id == tenant_id)
    if for_update:
        query = query.with_for_update()
    bill = query.first()
    if bill is None:
        raise NotFoundError("Bill not found")
    return bill


def _get_order_item(db: Session, order: Order, item_id: int) -> OrderItem:
    item = (
        db.query(OrderItem)
        .filter(OrderItem.id == item_id, OrderItem.order_id == order.id)
        .first()
    )
    if item is None:
        raise NotFoundError("Order item not found")
    return item


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_table(db: Session, tenant_id: int, table_id: int) -> RestaurantTable:
    table = (
        db.query(RestaurantTable)
        .filter(RestaurantTable.id == table_id, RestaurantTable.tenant_id == tenant_id)
        .first()
    )
    if table is None:
        raise NotFoundError("Table not found")
    return table


def _resolve_menu_item_price(db: Session, outlet_id: int, menu_item_id: int) -> tuple[MenuItem, float]:
    menu_item = db.get(MenuItem, menu_item_id)
    if menu_item is None or not menu_item.is_active:
        raise NotFoundError("Menu item not found")

    mapping = (
        db.query(MenuItemOutlet)
        .filter(
            MenuItemOutlet.menu_item_id == menu_item_id,
            MenuItemOutlet.outlet_id == outlet_id,
            MenuItemOutlet.is_available.is_(True),
        )
        .first()
    )
    price = float(mapping.outlet_price) if mapping else float(menu_item.base_price)
    return menu_item, price


def _ensure_editable(order: Order) -> None:
    if order.order_status in {OrderStatus.BILLED, OrderStatus.CANCELLED}:
        raise ConflictError("Order cannot be modified in its current status")


def _recalculate_order(order: Order) -> None:
    subtotal = 0.0
    discount_total = 0.0
    gst_total = 0.0

    for item in order.items:
        if item.status == OrderItemStatus.CANCELLED:
            continue
        line_gross = float(item.price) * item.quantity
        line_discount = float(item.discount_amount)
        line_net = max(line_gross - line_discount, 0)
        line_gst = round(line_net * float(item.gst_percent) / 100, 2)
        subtotal += line_net
        discount_total += line_discount
        gst_total += line_gst

    service_charge = round(subtotal * SERVICE_CHARGE_RATE, 2)
    grand_total = round(subtotal + service_charge + gst_total, 2)

    order.subtotal = round(subtotal, 2)
    order.discount_amount = round(discount_total, 2)
    order.service_charge = service_charge
    order.gst_amount = round(gst_total, 2)
    order.grand_total = grand_total


def _apply_round_off(amount: float) -> tuple[float, float]:
    rounded = round(amount)
    round_off = round(rounded - amount, 2)
    return round_off, rounded


def _next_order_number() -> str:
    return f"ORD-{uuid.uuid4().hex[:8].upper()}"


def _next_bill_number() -> str:
    return f"BILL-{uuid.uuid4().hex[:8].upper()}"


def _to_order_read(order: Order) -> OrderRead:
    active_items = [item for item in order.items if item.status != OrderItemStatus.CANCELLED]
    return OrderRead(
        id=order.id,
        tenant_id=order.tenant_id,
        brand_id=order.brand_id,
        outlet_id=order.outlet_id,
        table_id=order.table_id,
        customer_id=order.customer_id,
        order_number=order.order_number,
        order_type=order.order_type,
        order_source=order.order_source,
        source_reference=order.source_reference,
        queue_token=parse_queue_token(order.source_reference),
        pickup_at=order.pickup_at,
        ready_at=order.ready_at,
        order_status=order.order_status,
        subtotal=float(order.subtotal),
        discount_amount=float(order.discount_amount),
        service_charge=float(order.service_charge),
        gst_amount=float(order.gst_amount),
        grand_total=float(order.grand_total),
        created_by=order.created_by,
        is_active=order.is_active,
        created_at=order.created_at,
        updated_at=order.updated_at,
        items=[OrderItemRead.model_validate(item) for item in active_items],
    )
