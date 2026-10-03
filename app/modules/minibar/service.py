"""Minibar catalog + charge-to-folio with optional stock deduct."""

from __future__ import annotations

from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.housekeeping.models import HotelRoom
from app.modules.inventory.models import StockLedger, StockReferenceType, StockTransactionType
from app.modules.minibar.models import (
    MinibarCatalogItem,
    MinibarPosting,
    MinibarPostingLine,
    MinibarPostingStatus,
)
from app.modules.minibar.schemas import (
    MinibarCatalogItemCreate,
    MinibarCatalogItemRead,
    MinibarCatalogItemUpdate,
    MinibarChargeCreate,
    MinibarChargeResponse,
    MinibarPostingLineRead,
    MinibarPostingRead,
    MinibarVoidRequest,
)
from app.modules.outlets.models import Outlet
from app.modules.pms.models import FolioEntryType, FolioStatus, GuestReservation, ReservationStatus
from app.modules.pms.schemas import FolioRead


def _catalog_to_read(item: MinibarCatalogItem) -> MinibarCatalogItemRead:
    return MinibarCatalogItemRead(
        id=item.id,
        tenant_id=item.tenant_id,
        brand_id=item.brand_id,
        outlet_id=item.outlet_id,
        name=item.name,
        sku_code=item.sku_code,
        barcode=item.barcode,
        category=item.category,
        unit_price=float(item.unit_price),
        gst_percent=float(item.gst_percent or 0),
        menu_item_id=item.menu_item_id,
        raw_material_id=item.raw_material_id,
        sort_order=int(item.sort_order or 0),
        is_active=item.is_active,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def list_catalog(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
    include_inactive: bool = False,
) -> list[MinibarCatalogItemRead]:
    query = db.query(MinibarCatalogItem).filter(MinibarCatalogItem.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(MinibarCatalogItem.is_active.is_(True))
    if outlet_id is not None:
        query = query.filter(
            (MinibarCatalogItem.outlet_id.is_(None)) | (MinibarCatalogItem.outlet_id == outlet_id)
        )
    rows = query.order_by(MinibarCatalogItem.sort_order.asc(), MinibarCatalogItem.name.asc()).all()
    return [_catalog_to_read(row) for row in rows]


def create_catalog_item(
    db: Session,
    tenant_id: int,
    data: MinibarCatalogItemCreate,
    brand_id: int | None = None,
) -> MinibarCatalogItemRead:
    if data.outlet_id is not None:
        outlet = db.query(Outlet).filter(Outlet.id == data.outlet_id, Outlet.tenant_id == tenant_id).first()
        if outlet is None:
            raise NotFoundError("Outlet not found")
        brand_id = brand_id or outlet.brand_id

    if data.sku_code:
        clash = (
            db.query(MinibarCatalogItem)
            .filter(
                MinibarCatalogItem.tenant_id == tenant_id,
                MinibarCatalogItem.sku_code == data.sku_code.strip().upper(),
                MinibarCatalogItem.is_active.is_(True),
            )
            .first()
        )
        if clash:
            raise ConflictError("SKU code already exists")

    item = MinibarCatalogItem(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        name=data.name.strip(),
        sku_code=data.sku_code.strip().upper() if data.sku_code else None,
        barcode=data.barcode.strip() if data.barcode else None,
        category=(data.category or "general").strip().lower(),
        unit_price=data.unit_price,
        gst_percent=data.gst_percent,
        menu_item_id=data.menu_item_id,
        raw_material_id=data.raw_material_id,
        sort_order=data.sort_order,
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return _catalog_to_read(item)


def update_catalog_item(
    db: Session,
    tenant_id: int,
    item_id: int,
    data: MinibarCatalogItemUpdate,
) -> MinibarCatalogItemRead:
    item = (
        db.query(MinibarCatalogItem)
        .filter(MinibarCatalogItem.id == item_id, MinibarCatalogItem.tenant_id == tenant_id)
        .first()
    )
    if item is None:
        raise NotFoundError("Minibar catalog item not found")
    payload = data.model_dump(exclude_unset=True)
    if "sku_code" in payload and payload["sku_code"]:
        payload["sku_code"] = str(payload["sku_code"]).strip().upper()
    if "name" in payload and payload["name"]:
        payload["name"] = str(payload["name"]).strip()
    if "category" in payload and payload["category"]:
        payload["category"] = str(payload["category"]).strip().lower()
    for key, value in payload.items():
        setattr(item, key, value)
    db.commit()
    db.refresh(item)
    return _catalog_to_read(item)


def ensure_default_catalog(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
    outlet_id: int | None = None,
) -> list[MinibarCatalogItemRead]:
    existing = (
        db.query(MinibarCatalogItem)
        .filter(MinibarCatalogItem.tenant_id == tenant_id, MinibarCatalogItem.is_active.is_(True))
        .count()
    )
    if existing:
        return list_catalog(db, tenant_id, outlet_id=outlet_id)

    defaults = [
        ("Mineral Water 1L", "MB-WATER", "beverages", 80),
        ("Soft Drink Can", "MB-SODA", "beverages", 120),
        ("Premium Beer", "MB-BEER", "beverages", 350),
        ("Potato Chips", "MB-CHIPS", "snacks", 90),
        ("Chocolate Bar", "MB-CHOC", "snacks", 150),
        ("Nuts Mix", "MB-NUTS", "snacks", 220),
        ("Energy Bar", "MB-ENERGY", "snacks", 180),
        ("Instant Noodles", "MB-NOODLE", "food", 160),
    ]
    for idx, (name, sku, category, price) in enumerate(defaults):
        db.add(
            MinibarCatalogItem(
                tenant_id=tenant_id,
                brand_id=brand_id,
                outlet_id=outlet_id,
                name=name,
                sku_code=sku,
                category=category,
                unit_price=price,
                gst_percent=5,
                sort_order=idx + 1,
            )
        )
    db.commit()
    return list_catalog(db, tenant_id, outlet_id=outlet_id)


def _posting_to_read(db: Session, posting: MinibarPosting) -> MinibarPostingRead:
    room = db.get(HotelRoom, posting.room_id)
    reservation = db.get(GuestReservation, posting.reservation_id)
    return MinibarPostingRead(
        id=posting.id,
        tenant_id=posting.tenant_id,
        brand_id=posting.brand_id,
        outlet_id=posting.outlet_id,
        room_id=posting.room_id,
        room_number=room.room_number if room else None,
        reservation_id=posting.reservation_id,
        guest_name=reservation.guest_name if reservation else None,
        folio_entry_id=posting.folio_entry_id,
        status=posting.status,
        total_amount=float(posting.total_amount),
        notes=posting.notes,
        posted_by=posting.posted_by,
        voided_by=posting.voided_by,
        void_reason=posting.void_reason,
        lines=[
            MinibarPostingLineRead(
                id=line.id,
                posting_id=line.posting_id,
                catalog_item_id=line.catalog_item_id,
                item_name=line.item_name,
                quantity=float(line.quantity),
                unit_price=float(line.unit_price),
                line_total=float(line.line_total),
                raw_material_id=line.raw_material_id,
                created_at=line.created_at,
                updated_at=line.updated_at,
                is_active=line.is_active,
            )
            for line in posting.lines
        ],
        created_at=posting.created_at,
        updated_at=posting.updated_at,
        is_active=posting.is_active,
    )


def _deduct_stock_for_line(
    db: Session,
    *,
    tenant_id: int,
    brand_id: int | None,
    outlet_id: int,
    catalog: MinibarCatalogItem,
    quantity: float,
    posting_id: int,
    item_name: str,
    user_id: int | None,
) -> int | None:
    """Deduct via menu BOM if linked, else raw_material 1:1. Returns raw_material_id used."""
    from app.modules.menu.models import MenuItemIngredient

    if catalog.menu_item_id:
        ingredients = (
            db.query(MenuItemIngredient)
            .filter(
                MenuItemIngredient.tenant_id == tenant_id,
                MenuItemIngredient.menu_item_id == catalog.menu_item_id,
                MenuItemIngredient.is_active.is_(True),
            )
            .all()
        )
        for ingredient in ingredients:
            qty_out = float(ingredient.quantity_per_serving) * float(quantity)
            if qty_out <= 0:
                continue
            db.add(
                StockLedger(
                    tenant_id=tenant_id,
                    brand_id=brand_id,
                    outlet_id=outlet_id,
                    raw_material_id=ingredient.raw_material_id,
                    transaction_type=StockTransactionType.SALE,
                    quantity_in=0,
                    quantity_out=qty_out,
                    reference_type=StockReferenceType.SALE,
                    reference_id=posting_id,
                    remarks=f"Minibar · {item_name}",
                    created_by=user_id,
                )
            )
        if ingredients:
            return ingredients[0].raw_material_id

    if catalog.raw_material_id:
        db.add(
            StockLedger(
                tenant_id=tenant_id,
                brand_id=brand_id,
                outlet_id=outlet_id,
                raw_material_id=catalog.raw_material_id,
                transaction_type=StockTransactionType.SALE,
                quantity_in=0,
                quantity_out=float(quantity),
                reference_type=StockReferenceType.SALE,
                reference_id=posting_id,
                remarks=f"Minibar · {item_name}",
                created_by=user_id,
            )
        )
        return catalog.raw_material_id
    return None


def _reverse_stock_for_posting(
    db: Session,
    *,
    tenant_id: int,
    brand_id: int | None,
    posting: MinibarPosting,
    user_id: int | None,
) -> None:
    for line in posting.lines:
        if not line.raw_material_id:
            continue
        db.add(
            StockLedger(
                tenant_id=tenant_id,
                brand_id=brand_id,
                outlet_id=posting.outlet_id,
                raw_material_id=line.raw_material_id,
                transaction_type=StockTransactionType.ADJUSTMENT,
                quantity_in=float(line.quantity),
                quantity_out=0,
                reference_type=StockReferenceType.ADJUSTMENT,
                reference_id=posting.id,
                remarks=f"Minibar void · {line.item_name}",
                created_by=user_id,
            )
        )


def post_minibar_charge(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: MinibarChargeCreate,
) -> MinibarChargeResponse:
    from app.modules.pms import service as pms_service

    reservation = pms_service._get_reservation(db, tenant_id, reservation_id)
    if reservation.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Guest must be checked in to post minibar charges")
    if not reservation.folio:
        raise NotFoundError("Guest folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    room_id = data.room_id or reservation.room_id
    if not room_id:
        raise ConflictError("No room assigned to this reservation")
    room = db.get(HotelRoom, room_id)
    if room is None or room.tenant_id != tenant_id:
        raise NotFoundError("Room not found")
    if room.outlet_id != reservation.outlet_id:
        raise ConflictError("Room belongs to a different outlet")

    catalog_ids = [line.catalog_item_id for line in data.lines]
    catalog_rows = (
        db.query(MinibarCatalogItem)
        .filter(
            MinibarCatalogItem.tenant_id == tenant_id,
            MinibarCatalogItem.id.in_(catalog_ids),
            MinibarCatalogItem.is_active.is_(True),
        )
        .all()
    )
    by_id = {row.id: row for row in catalog_rows}
    if len(by_id) != len(set(catalog_ids)):
        raise NotFoundError("One or more catalog items were not found")

    posting = MinibarPosting(
        tenant_id=tenant_id,
        brand_id=reservation.brand_id,
        outlet_id=reservation.outlet_id,
        room_id=room_id,
        reservation_id=reservation.id,
        status=MinibarPostingStatus.POSTED,
        total_amount=0,
        notes=data.notes,
        posted_by=user_id,
    )
    db.add(posting)
    db.flush()

    line_parts: list[str] = []
    total = 0.0
    for line in data.lines:
        catalog = by_id[line.catalog_item_id]
        qty = float(line.quantity)
        unit_price = float(catalog.unit_price)
        line_total = round(qty * unit_price, 2)
        raw_id = _deduct_stock_for_line(
            db,
            tenant_id=tenant_id,
            brand_id=reservation.brand_id,
            outlet_id=reservation.outlet_id,
            catalog=catalog,
            quantity=qty,
            posting_id=posting.id,
            item_name=catalog.name,
            user_id=user_id,
        )
        db.add(
            MinibarPostingLine(
                posting_id=posting.id,
                catalog_item_id=catalog.id,
                item_name=catalog.name,
                quantity=qty,
                unit_price=unit_price,
                line_total=line_total,
                raw_material_id=raw_id,
            )
        )
        total = round(total + line_total, 2)
        qty_label = int(qty) if qty == int(qty) else qty
        line_parts.append(f"{catalog.name} ×{qty_label}")

    posting.total_amount = total
    description = f"Minibar — {', '.join(line_parts)}"[:255]
    if data.notes:
        description = f"{description} ({data.notes.strip()})"[:255]

    entry = pms_service._add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.MINIBAR_CHARGE,
        description,
        total,
        posted_by=user_id,
    )
    posting.folio_entry_id = entry.id
    db.commit()
    db.refresh(posting)
    posting = (
        db.query(MinibarPosting)
        .options(joinedload(MinibarPosting.lines))
        .filter(MinibarPosting.id == posting.id)
        .one()
    )
    db.refresh(reservation.folio)
    return MinibarChargeResponse(
        posting=_posting_to_read(db, posting),
        folio=pms_service._folio_to_read(reservation.folio),
    )


def void_minibar_posting(
    db: Session,
    tenant_id: int,
    user_id: int,
    posting_id: int,
    data: MinibarVoidRequest | None = None,
) -> MinibarPostingRead:
    from app.modules.pms import service as pms_service
    from app.modules.pms.models import FolioEntry

    posting = (
        db.query(MinibarPosting)
        .options(joinedload(MinibarPosting.lines))
        .filter(MinibarPosting.id == posting_id, MinibarPosting.tenant_id == tenant_id)
        .first()
    )
    if posting is None:
        raise NotFoundError("Minibar posting not found")
    if posting.status == MinibarPostingStatus.VOIDED:
        raise ConflictError("Minibar posting is already voided")

    reservation = pms_service._get_reservation(db, tenant_id, posting.reservation_id)
    if reservation.folio and reservation.folio.status == FolioStatus.OPEN and posting.folio_entry_id:
        entry = db.get(FolioEntry, posting.folio_entry_id)
        if entry and entry.is_active:
            # Reverse charge effect: treat as void by reducing balance and deactivating
            reservation.folio.balance = float(reservation.folio.balance) - abs(float(entry.amount))
            entry.is_active = False
            entry.description = f"[VOID] {entry.description}"[:255]

    _reverse_stock_for_posting(
        db,
        tenant_id=tenant_id,
        brand_id=posting.brand_id,
        posting=posting,
        user_id=user_id,
    )
    posting.status = MinibarPostingStatus.VOIDED
    posting.voided_by = user_id
    posting.void_reason = (data.reason if data else None) or "Voided"
    posting.is_active = False
    db.commit()
    db.refresh(posting)
    return _posting_to_read(db, posting)


def list_postings(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
    reservation_id: int | None = None,
    limit: int = 50,
) -> list[MinibarPostingRead]:
    query = (
        db.query(MinibarPosting)
        .options(joinedload(MinibarPosting.lines))
        .filter(MinibarPosting.tenant_id == tenant_id)
    )
    if outlet_id:
        query = query.filter(MinibarPosting.outlet_id == outlet_id)
    if reservation_id:
        query = query.filter(MinibarPosting.reservation_id == reservation_id)
    rows = query.order_by(MinibarPosting.id.desc()).limit(limit).all()
    return [_posting_to_read(db, row) for row in rows]
