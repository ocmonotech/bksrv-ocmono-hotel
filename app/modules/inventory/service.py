from __future__ import annotations

from datetime import date, datetime, timedelta
from math import ceil

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.inventory.models import (
    ApprovalStatus,
    Purchase,
    PurchaseItem,
    RawMaterial,
    StockLedger,
    StockReferenceType,
    StockTransactionType,
    StockTransfer,
    StockTransferItem,
    StockTransferStatus,
    Vendor,
    Wastage,
)
from app.modules.inventory.schemas import (
    LowStockItem,
    OutletInventoryItem,
    PrepBoardIngredient,
    PrepBoardItem,
    PrepBoardRead,
    PrepBoardTotals,
    PurchaseCreate,
    PurchaseRead,
    RawMaterialCreate,
    RawMaterialRead,
    StockLedgerRead,
    StockAdjustmentCreate,
    StockAdjustmentRead,
    StockTransferCreate,
    StockTransferRead,
    StockTransferStatusUpdate,
    VendorCreate,
    VendorRead,
    WastageCreate,
    WastageRead,
)
from app.modules.outlets.models import Outlet


def create_raw_material(
    db: Session,
    tenant_id: int,
    data: RawMaterialCreate,
    default_brand_id: int | None = None,
) -> RawMaterialRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    material = RawMaterial(
        tenant_id=tenant_id,
        brand_id=brand_id,
        name=data.name,
        category=data.category,
        unit=data.unit,
        reorder_level=data.reorder_level,
        average_unit_cost=0,
    )
    db.add(material)
    db.commit()
    db.refresh(material)
    return RawMaterialRead.model_validate(material)


def list_raw_materials(
    db: Session,
    tenant_id: int,
    *,
    brand_id: int | None = None,
    page: int = 1,
    page_size: int = 200,
) -> tuple[list[RawMaterialRead], int]:
    query = db.query(RawMaterial).filter(
        RawMaterial.tenant_id == tenant_id,
        RawMaterial.is_active.is_(True),
    )
    if brand_id is not None:
        query = query.filter(or_(RawMaterial.brand_id.is_(None), RawMaterial.brand_id == brand_id))
    query = query.order_by(RawMaterial.name.asc())
    materials, total = paginate_query(query, page, page_size)
    for material in materials:
        _backfill_material_cost_if_needed(db, tenant_id, material)
    db.commit()
    return [RawMaterialRead.model_validate(row) for row in materials], total


def _backfill_material_cost_if_needed(db: Session, tenant_id: int, material: RawMaterial) -> None:
    if float(material.average_unit_cost or 0) > 0:
        return
    latest = (
        db.query(PurchaseItem.rate)
        .join(Purchase, Purchase.id == PurchaseItem.purchase_id)
        .filter(
            Purchase.tenant_id == tenant_id,
            Purchase.approval_status == ApprovalStatus.APPROVED,
            PurchaseItem.raw_material_id == material.id,
        )
        .order_by(Purchase.purchase_date.desc(), PurchaseItem.id.desc())
        .first()
    )
    if latest:
        rate = float(latest.rate or 0)
        material.average_unit_cost = rate
        material.last_purchase_rate = rate


def _update_material_cost_on_purchase(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    raw_material_id: int,
    quantity: float,
    rate: float,
) -> None:
    material = _get_raw_material(db, tenant_id, raw_material_id)
    current_qty = max(get_stock_balance(db, tenant_id, outlet_id, raw_material_id), 0.0)
    old_avg = float(material.average_unit_cost or 0)
    incoming_qty = float(quantity)
    incoming_rate = float(rate)

    if current_qty + incoming_qty <= 0:
        new_avg = incoming_rate
    else:
        new_avg = ((current_qty * old_avg) + (incoming_qty * incoming_rate)) / (current_qty + incoming_qty)

    material.average_unit_cost = round(new_avg, 4)
    material.last_purchase_rate = incoming_rate


def list_inventory_by_outlet(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    page: int,
    page_size: int,
) -> tuple[list[OutletInventoryItem], int]:
    outlet = _get_outlet(db, tenant_id, outlet_id)

    balances = _stock_balances_subquery(db, tenant_id, outlet_id)
    query = (
        db.query(RawMaterial, balances.c.quantity_on_hand)
        .outerjoin(balances, RawMaterial.id == balances.c.raw_material_id)
        .filter(
            RawMaterial.tenant_id == tenant_id,
            RawMaterial.is_active.is_(True),
            or_(RawMaterial.brand_id.is_(None), RawMaterial.brand_id == outlet.brand_id),
        )
        .order_by(RawMaterial.name)
    )

    materials, total = paginate_query(query, page, page_size)
    items = [
        OutletInventoryItem(
            raw_material_id=material.id,
            name=material.name,
            category=material.category,
            unit=material.unit,
            reorder_level=float(material.reorder_level),
            quantity_on_hand=float(qty or 0),
            average_unit_cost=float(material.average_unit_cost or 0),
            is_low_stock=float(qty or 0) <= float(material.reorder_level),
        )
        for material, qty in materials
    ]
    return items, total


def create_vendor(
    db: Session,
    tenant_id: int,
    data: VendorCreate,
    default_brand_id: int | None = None,
) -> VendorRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    vendor = Vendor(
        tenant_id=tenant_id,
        brand_id=brand_id,
        vendor_name=data.vendor_name,
        mobile=data.mobile,
        email=data.email,
        gst_number=data.gst_number,
        address=data.address,
    )
    db.add(vendor)
    db.commit()
    db.refresh(vendor)
    return VendorRead.model_validate(vendor)


def create_purchase(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: PurchaseCreate,
    default_brand_id: int | None = None,
) -> PurchaseRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)
    _get_vendor(db, tenant_id, data.vendor_id)

    total_amount = sum(item.total for item in data.items)
    purchase = Purchase(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        vendor_id=data.vendor_id,
        invoice_number=data.invoice_number,
        purchase_date=data.purchase_date,
        total_amount=total_amount,
        payment_status=data.payment_status,
        approval_status=ApprovalStatus.PENDING,
        created_by=user_id,
    )
    db.add(purchase)
    db.flush()

    for item in data.items:
        _get_raw_material(db, tenant_id, item.raw_material_id)
        db.add(
            PurchaseItem(
                purchase_id=purchase.id,
                raw_material_id=item.raw_material_id,
                quantity=item.quantity,
                unit=item.unit,
                rate=item.rate,
                gst_percent=item.gst_percent,
                total=item.total,
            )
        )

    db.commit()
    return get_purchase(db, tenant_id, purchase.id)


def approve_purchase(db: Session, tenant_id: int, user_id: int, purchase_id: int) -> PurchaseRead:
    purchase = _get_purchase_entity(db, tenant_id, purchase_id, with_items=True)

    if purchase.approval_status == ApprovalStatus.APPROVED:
        raise ConflictError("Purchase is already approved")
    if purchase.approval_status == ApprovalStatus.REJECTED:
        raise ConflictError("Rejected purchase cannot be approved")

    updated_materials: set[int] = set()
    for item in purchase.items:
        _update_material_cost_on_purchase(
            db,
            tenant_id,
            purchase.outlet_id,
            item.raw_material_id,
            float(item.quantity),
            float(item.rate),
        )
        updated_materials.add(item.raw_material_id)
        db.add(
            StockLedger(
                tenant_id=purchase.tenant_id,
                brand_id=purchase.brand_id,
                outlet_id=purchase.outlet_id,
                raw_material_id=item.raw_material_id,
                transaction_type=StockTransactionType.PURCHASE,
                quantity_in=float(item.quantity),
                quantity_out=0,
                unit_cost=float(item.rate),
                line_cost=round(float(item.quantity) * float(item.rate), 2),
                reference_type=StockReferenceType.PURCHASE,
                reference_id=purchase.id,
                remarks=f"Purchase invoice {purchase.invoice_number}",
                created_by=user_id,
            )
        )

    purchase.approval_status = ApprovalStatus.APPROVED
    db.flush()

    from app.modules.menu import service as menu_service

    for material_id in updated_materials:
        menu_service.refresh_menu_items_for_material(db, tenant_id, material_id, commit=False)

    db.commit()
    return get_purchase(db, tenant_id, purchase.id)


def get_purchase(db: Session, tenant_id: int, purchase_id: int) -> PurchaseRead:
    purchase = _get_purchase_entity(db, tenant_id, purchase_id, with_items=True)
    return PurchaseRead.model_validate(purchase)


def list_stock_ledger(
    db: Session,
    tenant_id: int,
    outlet_id: int | None,
    raw_material_id: int | None,
    page: int,
    page_size: int,
) -> tuple[list[StockLedgerRead], int]:
    query = db.query(StockLedger).filter(StockLedger.tenant_id == tenant_id)
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(StockLedger.outlet_id == outlet_id)
    if raw_material_id is not None:
        _get_raw_material(db, tenant_id, raw_material_id)
        query = query.filter(StockLedger.raw_material_id == raw_material_id)

    query = query.order_by(StockLedger.created_at.desc(), StockLedger.id.desc())
    entries, total = paginate_query(query, page, page_size)
    return [StockLedgerRead.model_validate(entry) for entry in entries], total


def create_stock_transfer(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: StockTransferCreate,
    default_brand_id: int | None = None,
) -> StockTransferRead:
    if data.from_outlet_id == data.to_outlet_id:
        raise ConflictError("Source and destination outlets must differ")

    from_outlet = _get_outlet(db, tenant_id, data.from_outlet_id)
    to_outlet = _get_outlet(db, tenant_id, data.to_outlet_id)
    brand_id = data.brand_id or from_outlet.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    transfer = StockTransfer(
        tenant_id=tenant_id,
        brand_id=brand_id,
        from_outlet_id=data.from_outlet_id,
        to_outlet_id=data.to_outlet_id,
        status=StockTransferStatus.REQUESTED,
        requested_by=user_id,
    )
    db.add(transfer)
    db.flush()

    for item in data.items:
        _get_raw_material(db, tenant_id, item.raw_material_id)
        db.add(
            StockTransferItem(
                stock_transfer_id=transfer.id,
                raw_material_id=item.raw_material_id,
                quantity=item.quantity,
                unit=item.unit,
            )
        )

    db.commit()
    return get_stock_transfer(db, tenant_id, transfer.id)


def update_transfer_status(
    db: Session,
    tenant_id: int,
    user_id: int,
    transfer_id: int,
    data: StockTransferStatusUpdate,
) -> StockTransferRead:
    transfer = _get_transfer_entity(db, tenant_id, transfer_id, with_items=True)
    new_status = data.status
    current = transfer.status

    if new_status == current:
        return get_stock_transfer(db, tenant_id, transfer.id)

    allowed = _TRANSFER_TRANSITIONS.get(current, set())
    if new_status not in allowed:
        raise ConflictError(f"Cannot transition transfer from {current.value} to {new_status.value}")

    if new_status == StockTransferStatus.APPROVED:
        transfer.approved_by = user_id
    elif new_status == StockTransferStatus.DISPATCHED:
        _apply_transfer_out(db, transfer, user_id)
        transfer.dispatched_at = datetime.utcnow()
    elif new_status == StockTransferStatus.RECEIVED:
        if current != StockTransferStatus.DISPATCHED:
            raise ConflictError("Transfer must be dispatched before it can be received")
        _apply_transfer_in(db, transfer, user_id)
        transfer.received_at = datetime.utcnow()
    elif new_status == StockTransferStatus.REJECTED:
        if current not in {StockTransferStatus.REQUESTED, StockTransferStatus.APPROVED}:
            raise ConflictError("Only requested or approved transfers can be rejected")

    transfer.status = new_status
    db.commit()
    return get_stock_transfer(db, tenant_id, transfer.id)


def get_stock_transfer(db: Session, tenant_id: int, transfer_id: int) -> StockTransferRead:
    transfer = _get_transfer_entity(db, tenant_id, transfer_id, with_items=True)
    return StockTransferRead.model_validate(transfer)


def add_wastage(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: WastageCreate,
    default_brand_id: int | None = None,
) -> WastageRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)
    material = _get_raw_material(db, tenant_id, data.raw_material_id)
    unit_cost = float(material.average_unit_cost or 0)
    line_cost = round(unit_cost * float(data.quantity), 2) if unit_cost else None

    current_stock = get_stock_balance(db, tenant_id, data.outlet_id, data.raw_material_id)
    if current_stock < data.quantity:
        raise ConflictError(
            f"Insufficient stock. Available: {current_stock}, requested: {data.quantity}"
        )

    wastage = Wastage(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        raw_material_id=data.raw_material_id,
        quantity=data.quantity,
        reason=data.reason,
        day_part=(data.day_part or None),
        created_by=user_id,
    )
    db.add(wastage)
    db.flush()

    db.add(
        StockLedger(
            tenant_id=tenant_id,
            brand_id=brand_id,
            outlet_id=data.outlet_id,
            raw_material_id=data.raw_material_id,
            transaction_type=StockTransactionType.WASTAGE,
            quantity_in=0,
            quantity_out=float(data.quantity),
            unit_cost=unit_cost or None,
            line_cost=line_cost,
            reference_type=StockReferenceType.WASTAGE,
            reference_id=wastage.id,
            remarks=data.reason,
            created_by=user_id,
        )
    )

    db.commit()
    db.refresh(wastage)
    return _to_wastage_read(wastage, material)


def adjust_stock(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: StockAdjustmentCreate,
    default_brand_id: int | None = None,
) -> StockAdjustmentRead:
    if data.quantity == 0:
        raise ConflictError("Adjustment quantity cannot be zero")

    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)
    _get_raw_material(db, tenant_id, data.raw_material_id)

    current_stock = get_stock_balance(db, tenant_id, data.outlet_id, data.raw_material_id)
    if data.quantity < 0 and current_stock < abs(data.quantity):
        raise ConflictError(
            f"Insufficient stock. Available: {current_stock}, requested removal: {abs(data.quantity)}"
        )

    quantity_in = float(data.quantity) if data.quantity > 0 else 0.0
    quantity_out = float(abs(data.quantity)) if data.quantity < 0 else 0.0

    ledger = StockLedger(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        raw_material_id=data.raw_material_id,
        transaction_type=StockTransactionType.ADJUSTMENT,
        quantity_in=quantity_in,
        quantity_out=quantity_out,
        reference_type=StockReferenceType.ADJUSTMENT,
        reference_id=None,
        remarks=data.remarks,
        created_by=user_id,
    )
    db.add(ledger)
    db.flush()

    new_balance = get_stock_balance(db, tenant_id, data.outlet_id, data.raw_material_id)

    from app.modules.audit.models import AuditAction
    from app.modules.audit.service import log_audit

    log_audit(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        user_id=user_id,
        action=AuditAction.STOCK_ADJUSTED.value,
        module_name="inventory",
        record_type="stock_ledger",
        record_id=ledger.id,
        old_data={
            "raw_material_id": data.raw_material_id,
            "quantity_on_hand": current_stock,
        },
        new_data={
            "raw_material_id": data.raw_material_id,
            "adjustment_quantity": data.quantity,
            "quantity_on_hand": new_balance,
            "remarks": data.remarks,
        },
    )

    db.commit()
    db.refresh(ledger)
    return StockAdjustmentRead(
        ledger_id=ledger.id,
        outlet_id=data.outlet_id,
        raw_material_id=data.raw_material_id,
        quantity=data.quantity,
        remarks=data.remarks,
        quantity_on_hand=new_balance,
    )


def low_stock_report(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
) -> list[LowStockItem]:
    low_items: list[LowStockItem] = []

    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        balances = _stock_balances_subquery(db, tenant_id, outlet_id)
        rows = (
            db.query(RawMaterial, balances.c.quantity_on_hand)
            .outerjoin(balances, RawMaterial.id == balances.c.raw_material_id)
            .filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.is_active.is_(True),
            )
            .all()
        )
        for material, qty in rows:
            quantity_on_hand = float(qty or 0)
            reorder_level = float(material.reorder_level)
            if quantity_on_hand <= reorder_level:
                low_items.append(
                    LowStockItem(
                        outlet_id=outlet_id,
                        raw_material_id=material.id,
                        name=material.name,
                        category=material.category,
                        unit=material.unit,
                        reorder_level=reorder_level,
                        quantity_on_hand=quantity_on_hand,
                        shortfall=max(0, reorder_level - quantity_on_hand),
                    )
                )
    else:
        balances = _stock_balances_subquery(db, tenant_id, None)
        rows = (
            db.query(RawMaterial, balances.c.outlet_id, balances.c.quantity_on_hand)
            .join(balances, RawMaterial.id == balances.c.raw_material_id)
            .filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.is_active.is_(True),
            )
            .all()
        )
        for material, outlet, qty in rows:
            quantity_on_hand = float(qty or 0)
            reorder_level = float(material.reorder_level)
            if quantity_on_hand <= reorder_level:
                low_items.append(
                    LowStockItem(
                        outlet_id=outlet,
                        raw_material_id=material.id,
                        name=material.name,
                        category=material.category,
                        unit=material.unit,
                        reorder_level=reorder_level,
                        quantity_on_hand=quantity_on_hand,
                        shortfall=max(0, reorder_level - quantity_on_hand),
                    )
                )

    low_items.sort(key=lambda item: (item.outlet_id, item.name))
    return low_items


def get_stock_balance(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    raw_material_id: int,
) -> float:
    result = (
        db.query(
            func.coalesce(func.sum(StockLedger.quantity_in - StockLedger.quantity_out), 0)
        )
        .filter(
            StockLedger.tenant_id == tenant_id,
            StockLedger.outlet_id == outlet_id,
            StockLedger.raw_material_id == raw_material_id,
        )
        .scalar()
    )
    return float(result or 0)


_TRANSFER_TRANSITIONS = {
    StockTransferStatus.REQUESTED: {
        StockTransferStatus.APPROVED,
        StockTransferStatus.REJECTED,
    },
    StockTransferStatus.APPROVED: {
        StockTransferStatus.DISPATCHED,
        StockTransferStatus.REJECTED,
    },
    StockTransferStatus.DISPATCHED: {StockTransferStatus.RECEIVED},
}


def _stock_balances_subquery(db: Session, tenant_id: int, outlet_id: int | None):
    query = db.query(
        StockLedger.outlet_id.label("outlet_id"),
        StockLedger.raw_material_id.label("raw_material_id"),
        func.coalesce(func.sum(StockLedger.quantity_in - StockLedger.quantity_out), 0).label(
            "quantity_on_hand"
        ),
    ).filter(StockLedger.tenant_id == tenant_id)

    if outlet_id is not None:
        query = query.filter(StockLedger.outlet_id == outlet_id)

    return query.group_by(StockLedger.outlet_id, StockLedger.raw_material_id).subquery()


def _apply_transfer_out(db: Session, transfer: StockTransfer, user_id: int) -> None:
    for item in transfer.items:
        current_stock = get_stock_balance(
            db, transfer.tenant_id, transfer.from_outlet_id, item.raw_material_id
        )
        if current_stock < float(item.quantity):
            raise ConflictError(
                f"Insufficient stock for material {item.raw_material_id} at source outlet"
            )

        db.add(
            StockLedger(
                tenant_id=transfer.tenant_id,
                brand_id=transfer.brand_id,
                outlet_id=transfer.from_outlet_id,
                raw_material_id=item.raw_material_id,
                transaction_type=StockTransactionType.TRANSFER_OUT,
                quantity_in=0,
                quantity_out=float(item.quantity),
                reference_type=StockReferenceType.STOCK_TRANSFER,
                reference_id=transfer.id,
                remarks=f"Transfer to outlet {transfer.to_outlet_id}",
                created_by=user_id,
            )
        )


def _apply_transfer_in(db: Session, transfer: StockTransfer, user_id: int) -> None:
    for item in transfer.items:
        db.add(
            StockLedger(
                tenant_id=transfer.tenant_id,
                brand_id=transfer.brand_id,
                outlet_id=transfer.to_outlet_id,
                raw_material_id=item.raw_material_id,
                transaction_type=StockTransactionType.TRANSFER_IN,
                quantity_in=float(item.quantity),
                quantity_out=0,
                reference_type=StockReferenceType.STOCK_TRANSFER,
                reference_id=transfer.id,
                remarks=f"Transfer from outlet {transfer.from_outlet_id}",
                created_by=user_id,
            )
        )


def deduct_stock_for_order(
    db: Session,
    *,
    tenant_id: int,
    outlet_id: int,
    brand_id: int | None,
    order,
    user_id: int | None = None,
) -> None:
    from app.modules.menu.models import MenuItemIngredient
    from app.modules.pos.models import OrderItemStatus

    active_items = [
        item for item in order.items if item.status != OrderItemStatus.CANCELLED and item.is_active
    ]
    if not active_items:
        return

    menu_item_ids = [item.menu_item_id for item in active_items]
    ingredients = (
        db.query(MenuItemIngredient)
        .filter(
            MenuItemIngredient.tenant_id == tenant_id,
            MenuItemIngredient.menu_item_id.in_(menu_item_ids),
            MenuItemIngredient.is_active.is_(True),
        )
        .all()
    )
    by_menu_item: dict[int, list[MenuItemIngredient]] = {}
    for ingredient in ingredients:
        by_menu_item.setdefault(ingredient.menu_item_id, []).append(ingredient)

    material_ids = list({ingredient.raw_material_id for ingredient in ingredients})
    materials = {
        row.id: row
        for row in db.query(RawMaterial)
        .filter(RawMaterial.tenant_id == tenant_id, RawMaterial.id.in_(material_ids))
        .all()
    } if material_ids else {}

    for item in active_items:
        for ingredient in by_menu_item.get(item.menu_item_id, []):
            quantity_out = float(ingredient.quantity_per_serving) * item.quantity
            if quantity_out <= 0:
                continue
            material = materials.get(ingredient.raw_material_id)
            unit_cost = float(material.average_unit_cost or 0) if material else 0.0
            db.add(
                StockLedger(
                    tenant_id=tenant_id,
                    brand_id=brand_id,
                    outlet_id=outlet_id,
                    raw_material_id=ingredient.raw_material_id,
                    transaction_type=StockTransactionType.SALE,
                    quantity_in=0,
                    quantity_out=quantity_out,
                    unit_cost=unit_cost or None,
                    line_cost=round(unit_cost * quantity_out, 2) if unit_cost else None,
                    reference_type=StockReferenceType.SALE,
                    reference_id=order.id,
                    remarks=f"KOT sale for {item.item_name}",
                    created_by=user_id,
                )
            )


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_vendor(db: Session, tenant_id: int, vendor_id: int) -> Vendor:
    vendor = db.query(Vendor).filter(Vendor.id == vendor_id, Vendor.tenant_id == tenant_id).first()
    if vendor is None:
        raise NotFoundError("Vendor not found")
    return vendor


def _get_raw_material(db: Session, tenant_id: int, raw_material_id: int) -> RawMaterial:
    material = (
        db.query(RawMaterial)
        .filter(RawMaterial.id == raw_material_id, RawMaterial.tenant_id == tenant_id)
        .first()
    )
    if material is None:
        raise NotFoundError("Raw material not found")
    return material


def _get_purchase_entity(
    db: Session,
    tenant_id: int,
    purchase_id: int,
    with_items: bool = False,
) -> Purchase:
    query = db.query(Purchase).filter(Purchase.id == purchase_id, Purchase.tenant_id == tenant_id)
    if with_items:
        query = query.options(joinedload(Purchase.items))
    purchase = query.first()
    if purchase is None:
        raise NotFoundError("Purchase not found")
    return purchase


def _get_transfer_entity(
    db: Session,
    tenant_id: int,
    transfer_id: int,
    with_items: bool = False,
) -> StockTransfer:
    query = db.query(StockTransfer).filter(
        StockTransfer.id == transfer_id,
        StockTransfer.tenant_id == tenant_id,
    )
    if with_items:
        query = query.options(joinedload(StockTransfer.items))
    transfer = query.first()
    if transfer is None:
        raise NotFoundError("Stock transfer not found")
    return transfer


DAY_PART_HOURS = {
    "breakfast": (6, 11),
    "lunch": (11, 16),
    "dinner": (16, 23),
    "all_day": (0, 24),
}


def _normalize_day_part(day_part: str | None) -> str:
    value = (day_part or "all_day").strip().lower().replace("-", "_")
    if value not in DAY_PART_HOURS:
        return "all_day"
    return value


def _to_wastage_read(wastage: Wastage, material: RawMaterial | None = None) -> WastageRead:
    unit_cost = float(material.average_unit_cost or 0) if material else 0.0
    qty = float(wastage.quantity or 0)
    return WastageRead(
        id=wastage.id,
        tenant_id=wastage.tenant_id,
        brand_id=wastage.brand_id,
        outlet_id=wastage.outlet_id,
        raw_material_id=wastage.raw_material_id,
        quantity=qty,
        reason=wastage.reason,
        day_part=getattr(wastage, "day_part", None),
        created_by=wastage.created_by,
        is_active=wastage.is_active,
        created_at=wastage.created_at,
        updated_at=wastage.updated_at,
        material_name=material.name if material else None,
        unit=material.unit if material else None,
        line_cost=round(unit_cost * qty, 2) if unit_cost else None,
    )


def list_wastage(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    business_date: date | None = None,
    day_part: str | None = None,
) -> list[WastageRead]:
    _get_outlet(db, tenant_id, outlet_id)
    day = business_date or date.today()
    start = datetime.combine(day, datetime.min.time())
    end = start + timedelta(days=1)
    query = (
        db.query(Wastage, RawMaterial)
        .outerjoin(RawMaterial, RawMaterial.id == Wastage.raw_material_id)
        .filter(
            Wastage.tenant_id == tenant_id,
            Wastage.outlet_id == outlet_id,
            Wastage.is_active.is_(True),
            Wastage.created_at >= start,
            Wastage.created_at < end,
        )
        .order_by(Wastage.id.desc())
    )
    part = _normalize_day_part(day_part) if day_part else None
    if part and part != "all_day":
        query = query.filter(or_(Wastage.day_part == part, Wastage.day_part.is_(None)))
    rows = query.all()
    return [_to_wastage_read(wastage, material) for wastage, material in rows]


def _inclusion_covers_for_day_part(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    day_part: str,
) -> int:
    from app.modules.pms.models import (
        GuestReservation,
        InclusionType,
        ReservationPackageEntitlement,
        ReservationStatus,
    )

    mapping = {
        "breakfast": {InclusionType.BREAKFAST, InclusionType.CAFE},
        "lunch": {InclusionType.LUNCH, InclusionType.CAFE},
        "dinner": {InclusionType.DINNER, InclusionType.CAFE},
        "all_day": {
            InclusionType.BREAKFAST,
            InclusionType.LUNCH,
            InclusionType.DINNER,
            InclusionType.CAFE,
        },
    }
    types = mapping.get(day_part, mapping["all_day"])
    rows = (
        db.query(GuestReservation)
        .join(
            ReservationPackageEntitlement,
            ReservationPackageEntitlement.reservation_id == GuestReservation.id,
        )
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.status == ReservationStatus.CHECKED_IN,
            GuestReservation.is_active.is_(True),
            ReservationPackageEntitlement.is_active.is_(True),
            ReservationPackageEntitlement.inclusion_type.in_(list(types)),
            ReservationPackageEntitlement.qty_total > ReservationPackageEntitlement.qty_used,
        )
        .distinct()
        .all()
    )
    return sum(int(r.adults or 0) + int(r.children or 0) for r in rows)


def get_prep_board(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    business_date: date | None = None,
    day_part: str | None = None,
    lookback_days: int = 14,
) -> PrepBoardRead:
    from app.modules.menu.models import MenuItem, MenuItemIngredient
    from app.modules.pos.models import Order, OrderItem, OrderStatus

    _get_outlet(db, tenant_id, outlet_id)
    day = business_date or date.today()
    part = _normalize_day_part(day_part)
    lookback = max(3, min(int(lookback_days or 14), 60))
    hour_from, hour_to = DAY_PART_HOURS[part]

    end = datetime.combine(day, datetime.min.time())
    start = end - timedelta(days=lookback)

    sold_query = (
        db.query(
            OrderItem.menu_item_id,
            func.max(OrderItem.item_name).label("item_name"),
            func.coalesce(func.sum(OrderItem.quantity), 0).label("qty"),
        )
        .join(Order, Order.id == OrderItem.order_id)
        .filter(
            Order.tenant_id == tenant_id,
            Order.outlet_id == outlet_id,
            Order.order_status != OrderStatus.CANCELLED,
            Order.created_at >= start,
            Order.created_at < end,
            OrderItem.is_active.is_(True),
        )
        .group_by(OrderItem.menu_item_id)
    )
    if part != "all_day":
        sold_query = sold_query.filter(
            func.extract("hour", Order.created_at) >= hour_from,
            func.extract("hour", Order.created_at) < hour_to,
        )

    sold_rows = sold_query.all()
    menu_ids = [int(r.menu_item_id) for r in sold_rows if r.menu_item_id]
    menu_by_id: dict[int, MenuItem] = {}
    ingredients_by_item: dict[int, list[MenuItemIngredient]] = {}
    if menu_ids:
        menu_items = (
            db.query(MenuItem)
            .filter(
                MenuItem.tenant_id == tenant_id,
                MenuItem.id.in_(menu_ids),
                MenuItem.is_active.is_(True),
            )
            .all()
        )
        menu_by_id = {item.id: item for item in menu_items}
        ingredients = (
            db.query(MenuItemIngredient)
            .filter(
                MenuItemIngredient.tenant_id == tenant_id,
                MenuItemIngredient.menu_item_id.in_(menu_ids),
                MenuItemIngredient.is_active.is_(True),
            )
            .all()
        )
        for row in ingredients:
            ingredients_by_item.setdefault(row.menu_item_id, []).append(row)

    covers = _inclusion_covers_for_day_part(db, tenant_id, outlet_id, part)
    cover_boost = covers * 0.35 if covers else 0.0

    prep_items: list[PrepBoardItem] = []
    needed: dict[int, float] = {}

    ranked = sorted(sold_rows, key=lambda r: float(r.qty or 0), reverse=True)
    for index, row in enumerate(ranked):
        menu_item_id = int(row.menu_item_id)
        menu_item = menu_by_id.get(menu_item_id)
        if menu_item is None:
            continue
        bom = ingredients_by_item.get(menu_item_id) or []
        if not bom:
            continue
        avg = round(float(row.qty or 0) / lookback, 2)
        boost = cover_boost / max(1, min(5, len(ranked))) if index < 5 else 0.0
        forecast = float(max(1, ceil(avg + boost))) if avg > 0 or boost > 0 else 0.0
        if forecast <= 0:
            continue

        recipe_cost = 0.0
        for ingredient in bom:
            material = db.get(RawMaterial, ingredient.raw_material_id)
            unit_cost = float(material.average_unit_cost or 0) if material else 0.0
            per = float(ingredient.quantity_per_serving or 0)
            recipe_cost += unit_cost * per
            needed[ingredient.raw_material_id] = needed.get(ingredient.raw_material_id, 0.0) + (
                per * forecast
            )
        prep_items.append(
            PrepBoardItem(
                menu_item_id=menu_item_id,
                item_name=menu_item.item_name,
                preparation_area=(
                    menu_item.preparation_area.value
                    if hasattr(menu_item.preparation_area, "value")
                    else str(menu_item.preparation_area)
                ),
                avg_qty_sold=avg,
                forecast_qty=forecast,
                recipe_cost=round(recipe_cost, 2),
            )
        )

    ingredient_rows: list[PrepBoardIngredient] = []
    estimated_prep_cost = 0.0
    shortfall_lines = 0
    if needed:
        materials = (
            db.query(RawMaterial)
            .filter(
                RawMaterial.tenant_id == tenant_id,
                RawMaterial.id.in_(list(needed.keys())),
            )
            .all()
        )
        material_by_id = {m.id: m for m in materials}
        for raw_id, qty_needed in sorted(needed.items(), key=lambda kv: kv[1], reverse=True):
            material = material_by_id.get(raw_id)
            if material is None:
                continue
            on_hand = get_stock_balance(db, tenant_id, outlet_id, raw_id)
            qty_needed_r = round(qty_needed, 3)
            shortfall = round(max(0.0, qty_needed_r - on_hand), 3)
            if shortfall > 0:
                shortfall_lines += 1
            unit_cost = float(material.average_unit_cost or 0)
            est = round(unit_cost * qty_needed_r, 2)
            estimated_prep_cost += est
            ingredient_rows.append(
                PrepBoardIngredient(
                    raw_material_id=raw_id,
                    name=material.name,
                    unit=material.unit,
                    qty_needed=qty_needed_r,
                    qty_on_hand=round(on_hand, 3),
                    shortfall=shortfall,
                    average_unit_cost=unit_cost,
                    estimated_cost=est,
                )
            )

    wastage_rows = list_wastage(db, tenant_id, outlet_id, day, part)
    wastage_cost = round(sum(float(w.line_cost or 0) for w in wastage_rows), 2)

    return PrepBoardRead(
        outlet_id=outlet_id,
        business_date=day,
        day_part=part,
        lookback_days=lookback,
        expected_inclusion_covers=covers,
        items=prep_items,
        ingredients=ingredient_rows,
        wastage=wastage_rows,
        totals=PrepBoardTotals(
            ingredient_lines=len(ingredient_rows),
            shortfall_lines=shortfall_lines,
            estimated_prep_cost=round(estimated_prep_cost, 2),
            wastage_cost_today=wastage_cost,
        ),
    )
