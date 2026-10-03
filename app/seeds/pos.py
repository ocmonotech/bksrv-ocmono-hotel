"""POS orders, bills, payments, KOTs, and cancel reasons."""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.modules.kot.models import KOT, KOTItem, KotItemStatus, KotStatus
from app.modules.menu.models import PreparationArea
from app.modules.pos.models import (
    Bill,
    BillPaymentStatus,
    CancelReason,
    CancelReasonType,
    Order,
    OrderItem,
    OrderItemStatus,
    OrderSource,
    OrderStatus,
    OrderType,
    Payment,
    PaymentMode,
    PaymentRecordStatus,
)
from app.seeds.base import SeedContext
from app.seeds.constants import CANCEL_REASONS, SUPER_ADMIN_EMAIL


def seed_pos(db: Session, ctx: SeedContext) -> None:
    _seed_cancel_reasons(db, ctx)
    ctx.orders = _seed_orders(db, ctx)
    ctx.bills = _seed_bills(db, ctx)
    _seed_kots(db, ctx)


def _seed_cancel_reasons(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    type_map = {
        "order_cancel": CancelReasonType.ORDER,
        "bill_cancel": CancelReasonType.BILL,
        "item_cancel": CancelReasonType.ITEM,
    }
    for reason_type_str, reason_text in CANCEL_REASONS:
        reason_type = type_map[reason_type_str]
        existing = (
            db.query(CancelReason)
            .filter(
                CancelReason.tenant_id == tenant.id,
                CancelReason.reason_type == reason_type,
                CancelReason.reason_text == reason_text,
            )
            .first()
        )
        if existing is None:
            db.add(
                CancelReason(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    reason_type=reason_type,
                    reason_text=reason_text,
                )
            )


def _seed_orders(db: Session, ctx: SeedContext) -> dict[str, Order]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    cashier = ctx.users.get("cashier.andheri@restrochain.test")
    created_by = cashier.id if cashier else (admin.id if admin else None)

    table_t1 = ctx.tables.get(("Andheri West", "T1"))
    table_t2 = ctx.tables.get(("Andheri West", "T2"))
    customer = ctx.customers.get("+919800000001")

    butter_chicken = ctx.menu_items.get("Butter Chicken")
    garlic_naan = ctx.menu_items.get("Garlic Naan")
    paneer_tikka = ctx.menu_items.get("Paneer Tikka")
    mango_lassi = ctx.menu_items.get("Mango Lassi")
    chicken_biryani = ctx.menu_items.get("Chicken Biryani")

    order_specs = [
        {
            "order_number": "ORD-AND-001",
            "order_type": OrderType.DINE_IN,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.BILLED,
            "table": table_t1,
            "customer": customer,
            "items": [
                (butter_chicken, "Butter Chicken", 1, 420),
                (garlic_naan, "Garlic Naan", 2, 80),
                (mango_lassi, "Mango Lassi", 2, 110),
            ],
        },
        {
            "order_number": "ORD-AND-002",
            "order_type": OrderType.DINE_IN,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.PREPARING,
            "table": table_t2,
            "customer": None,
            "items": [
                (paneer_tikka, "Paneer Tikka", 1, 280),
                (garlic_naan, "Garlic Naan", 2, 80),
            ],
        },
        {
            "order_number": "ORD-AND-003",
            "order_type": OrderType.TAKEAWAY,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.READY,
            "table": None,
            "customer": ctx.customers.get("+919800000002"),
            "items": [
                (chicken_biryani, "Chicken Biryani", 2, 380),
            ],
        },
        {
            "order_number": "ORD-AND-004",
            "order_type": OrderType.DELIVERY,
            "order_source": OrderSource.ZOMATO,
            "order_source_ref": "ZMT-987654",
            "order_status": OrderStatus.KOT_SENT,
            "table": None,
            "customer": None,
            "items": [
                (butter_chicken, "Butter Chicken", 1, 420),
                (garlic_naan, "Garlic Naan", 4, 80),
            ],
        },
        {
            "order_number": "ORD-AND-005",
            "order_type": OrderType.DINE_IN,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.BILLED,
            "table": ctx.tables.get(("Andheri West", "T3")),
            "customer": ctx.customers.get("+919800000003"),
            "items": [
                (ctx.menu_items.get("Veg Biryani"), "Veg Biryani", 2, 320),
                (ctx.menu_items.get("Dal Makhani"), "Dal Makhani", 1, 280),
                (ctx.menu_items.get("Butter Naan"), "Butter Naan", 3, 60),
            ],
        },
        {
            "order_number": "ORD-AND-006",
            "order_type": OrderType.TAKEAWAY,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.SERVED,
            "table": None,
            "customer": ctx.customers.get("+919800000006"),
            "items": [
                (chicken_biryani, "Chicken Biryani", 1, 380),
                (ctx.menu_items.get("Gulab Jamun"), "Gulab Jamun", 2, 120),
                (ctx.menu_items.get("Mango Lassi"), "Mango Lassi", 1, 110),
            ],
        },
        {
            "order_number": "ORD-AND-007",
            "order_type": OrderType.DINE_IN,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.BILLED,
            "table": ctx.tables.get(("Andheri West", "T4")),
            "customer": ctx.customers.get("+919800000008"),
            "items": [
                (paneer_tikka, "Paneer Tikka", 2, 280),
                (butter_chicken, "Butter Chicken", 2, 420),
                (garlic_naan, "Garlic Naan", 4, 80),
                (ctx.menu_items.get("Kulfi Falooda"), "Kulfi Falooda", 2, 160),
            ],
        },
        {
            "order_number": "ORD-AND-008",
            "order_type": OrderType.DELIVERY,
            "order_source": OrderSource.SWIGGY,
            "order_source_ref": "SWG-112233",
            "order_status": OrderStatus.PREPARING,
            "table": None,
            "customer": ctx.customers.get("+919800000009"),
            "items": [
                (ctx.menu_items.get("Palak Paneer"), "Palak Paneer", 1, 320),
                (ctx.menu_items.get("Butter Naan"), "Butter Naan", 3, 60),
                (ctx.menu_items.get("Sweet Lassi"), "Sweet Lassi", 2, 100),
            ],
        },
        {
            "order_number": "ORD-AND-009",
            "order_type": OrderType.DINE_IN,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.DRAFT,
            "table": ctx.tables.get(("Andheri West", "T5")),
            "customer": ctx.customers.get("+919800000010"),
            "items": [
                (ctx.menu_items.get("Hara Bhara Kebab"), "Hara Bhara Kebab", 1, 240),
                (ctx.menu_items.get("Kadhai Paneer"), "Kadhai Paneer", 1, 340),
                (garlic_naan, "Garlic Naan", 2, 80),
            ],
        },
        {
            "order_number": "ORD-AND-010",
            "order_type": OrderType.TAKEAWAY,
            "order_source": OrderSource.IN_HOUSE,
            "order_status": OrderStatus.READY,
            "table": None,
            "customer": ctx.customers.get("+919800000012"),
            "items": [
                (ctx.menu_items.get("Chicken Wings"), "Chicken Wings", 2, 300),
                (ctx.menu_items.get("Virgin Mojito"), "Virgin Mojito", 2, 160),
            ],
        },
    ]

    orders: dict[str, Order] = {}
    for spec in order_specs:
        order = (
            db.query(Order)
            .filter(Order.tenant_id == tenant.id, Order.order_number == spec["order_number"])
            .first()
        )
        if order is not None:
            orders[spec["order_number"]] = order
            continue

        subtotal = sum(qty * price for _, _, qty, price in spec["items"])
        gst = round(subtotal * 0.05, 2)
        grand_total = subtotal + gst

        order = Order(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            table_id=spec["table"].id if spec["table"] else None,
            customer_id=spec["customer"].id if spec["customer"] else None,
            order_number=spec["order_number"],
            order_type=spec["order_type"],
            order_source=spec["order_source"],
            source_reference=spec.get("order_source_ref"),
            order_status=spec["order_status"],
            subtotal=subtotal,
            gst_amount=gst,
            grand_total=grand_total,
            created_by=created_by,
        )
        db.add(order)
        db.flush()

        item_status = (
            OrderItemStatus.SERVED
            if spec["order_status"] == OrderStatus.BILLED
            else OrderItemStatus.PREPARING
        )
        for menu_item, item_name, qty, price in spec["items"]:
            if menu_item is None:
                continue
            db.add(
                OrderItem(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    order_id=order.id,
                    menu_item_id=menu_item.id,
                    item_name=item_name,
                    quantity=qty,
                    price=price,
                    gst_percent=5,
                    status=item_status,
                )
            )
        orders[spec["order_number"]] = order

    return orders


def _seed_bills(db: Session, ctx: SeedContext) -> dict[str, Bill]:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    cashier = ctx.users.get("cashier.andheri@restrochain.test")
    created_by = cashier.id if cashier else (admin.id if admin else None)

    bill_specs = [
        ("BILL-AND-001", "ORD-AND-001", PaymentMode.UPI, "UPI-DEMO-001"),
        ("BILL-AND-002", "ORD-AND-005", PaymentMode.CASH, "CASH-DEMO-002"),
        ("BILL-AND-003", "ORD-AND-007", PaymentMode.CARD, "CARD-DEMO-003"),
    ]

    bills: dict[str, Bill] = {}
    for bill_number, order_number, payment_mode, payment_ref in bill_specs:
        order = ctx.orders.get(order_number)
        if order is None:
            continue

        bill = (
            db.query(Bill)
            .filter(Bill.tenant_id == tenant.id, Bill.bill_number == bill_number)
            .first()
        )
        if bill is None:
            bill = Bill(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                order_id=order.id,
                bill_number=bill_number,
                subtotal=float(order.subtotal),
                gst_amount=float(order.gst_amount),
                grand_total=float(order.grand_total),
                payment_status=BillPaymentStatus.PAID,
                created_by=created_by,
            )
            db.add(bill)
            db.flush()

            db.add(
                Payment(
                    bill_id=bill.id,
                    payment_mode=payment_mode,
                    amount=float(bill.grand_total),
                    reference_number=payment_ref,
                    status=PaymentRecordStatus.SUCCESS,
                )
            )
        bills[bill_number] = bill
    return bills


def _seed_kots(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    cashier = ctx.users.get("cashier.andheri@restrochain.test")
    created_by = cashier.id if cashier else (admin.id if admin else None)

    kot_specs = [
        ("KOT-AND-001", "ORD-AND-001", PreparationArea.KITCHEN, KotStatus.SERVED),
        ("KOT-AND-002", "ORD-AND-002", PreparationArea.TANDOOR, KotStatus.PREPARING),
        ("KOT-AND-003", "ORD-AND-004", PreparationArea.KITCHEN, KotStatus.ACCEPTED),
        ("KOT-AND-004", "ORD-AND-005", PreparationArea.KITCHEN, KotStatus.SERVED),
        ("KOT-AND-005", "ORD-AND-006", PreparationArea.KITCHEN, KotStatus.SERVED),
        ("KOT-AND-006", "ORD-AND-007", PreparationArea.KITCHEN, KotStatus.SERVED),
    ]

    for kot_number, order_number, prep_area, kot_status in kot_specs:
        order = ctx.orders.get(order_number)
        if order is None:
            continue

        kot = (
            db.query(KOT)
            .filter(KOT.tenant_id == tenant.id, KOT.kot_number == kot_number)
            .first()
        )
        if kot is not None:
            continue

        kot = KOT(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            order_id=order.id,
            kot_number=kot_number,
            preparation_area=prep_area,
            status=kot_status,
            created_by=created_by,
        )
        db.add(kot)
        db.flush()

        order_items = (
            db.query(OrderItem)
            .filter(OrderItem.order_id == order.id)
            .all()
        )
        item_status = (
            KotItemStatus.SERVED
            if kot_status == KotStatus.SERVED
            else KotItemStatus.PREPARING
        )
        for order_item in order_items:
            db.add(
                KOTItem(
                    kot_id=kot.id,
                    order_item_id=order_item.id,
                    item_name=order_item.item_name,
                    quantity=order_item.quantity,
                    status=item_status,
                )
            )
