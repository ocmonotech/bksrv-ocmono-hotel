"""Inventory: raw materials, vendors, purchases, stock ledger, transfers, wastage."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.inventory.models import (
    ApprovalStatus,
    MaterialUnit,
    PaymentStatus,
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
from app.seeds.base import SeedContext
from app.seeds.constants import RAW_MATERIALS, VENDORS, SUPER_ADMIN_EMAIL


def seed_inventory(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    ctx.raw_materials = _seed_raw_materials(db, tenant.id, brand.id)
    ctx.vendors = _seed_vendors(db, tenant.id, brand.id)
    _seed_purchases(db, ctx)
    _seed_stock_ledger(db, ctx)
    _seed_stock_transfers(db, ctx)
    _seed_wastage(db, ctx)


def _seed_raw_materials(db: Session, tenant_id: int, brand_id: int) -> dict[str, RawMaterial]:
    unit_map = {
        "kg": MaterialUnit.KG,
        "litre": MaterialUnit.LITRE,
        "piece": MaterialUnit.PIECE,
        "packet": MaterialUnit.PACKET,
        "gram": MaterialUnit.GRAM,
        "ml": MaterialUnit.ML,
    }
    materials: dict[str, RawMaterial] = {}
    for name, category, unit_str, reorder in RAW_MATERIALS:
        material = (
            db.query(RawMaterial)
            .filter(RawMaterial.tenant_id == tenant_id, RawMaterial.name == name)
            .first()
        )
        if material is None:
            material = RawMaterial(
                tenant_id=tenant_id,
                brand_id=brand_id,
                name=name,
                category=category,
                unit=unit_map.get(unit_str, MaterialUnit.KG),
                reorder_level=reorder,
            )
            db.add(material)
            db.flush()
        materials[name] = material
    return materials


def _seed_vendors(db: Session, tenant_id: int, brand_id: int) -> dict[str, Vendor]:
    vendors: dict[str, Vendor] = {}
    for vendor_name, mobile, email, gst in VENDORS:
        vendor = (
            db.query(Vendor)
            .filter(Vendor.tenant_id == tenant_id, Vendor.vendor_name == vendor_name)
            .first()
        )
        if vendor is None:
            vendor = Vendor(
                tenant_id=tenant_id,
                brand_id=brand_id,
                vendor_name=vendor_name,
                mobile=mobile,
                email=email,
                gst_number=gst,
                address="Mumbai, Maharashtra",
            )
            db.add(vendor)
            db.flush()
        vendors[vendor_name] = vendor
    return vendors


def _seed_purchases(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    if admin is None:
        return

    vendor = ctx.vendors.get("Fresh Farms Mumbai")
    chicken = ctx.raw_materials.get("Chicken Breast")
    paneer = ctx.raw_materials.get("Paneer")
    if vendor is None or chicken is None or paneer is None:
        return

    purchase_specs = [
        ("INV-2024-001", 12500, PaymentStatus.PAID, ApprovalStatus.APPROVED, [
            ("Chicken Breast", 20, 450),
            ("Paneer", 15, 320),
        ]),
        ("INV-2024-002", 8400, PaymentStatus.PENDING, ApprovalStatus.PENDING, [
            ("Basmati Rice", 50, 120),
            ("Tomato", 30, 40),
        ]),
    ]

    spice_vendor = ctx.vendors.get("Spice Traders Co")
    for invoice, total, pay_status, approval, items in purchase_specs:
        purchase = (
            db.query(Purchase)
            .filter(Purchase.tenant_id == tenant.id, Purchase.invoice_number == invoice)
            .first()
        )
        if purchase is not None:
            continue

        purchase = Purchase(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            vendor_id=vendor.id if invoice == "INV-2024-001" else spice_vendor.id,
            invoice_number=invoice,
            purchase_date=date.today() - timedelta(days=7 if invoice == "INV-2024-001" else 2),
            total_amount=total,
            payment_status=pay_status,
            approval_status=approval,
            created_by=admin.id,
        )
        db.add(purchase)
        db.flush()

        for material_name, qty, rate in items:
            material = ctx.raw_materials.get(material_name)
            if material is None:
                continue
            line_total = qty * rate
            db.add(
                PurchaseItem(
                    purchase_id=purchase.id,
                    raw_material_id=material.id,
                    quantity=qty,
                    unit=material.unit,
                    rate=rate,
                    gst_percent=5,
                    total=line_total,
                )
            )


def _seed_stock_ledger(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    if admin is None:
        return

    entries = [
        ("Chicken Breast", 20, StockTransactionType.PURCHASE, StockReferenceType.PURCHASE),
        ("Paneer", 15, StockTransactionType.PURCHASE, StockReferenceType.PURCHASE),
        ("Basmati Rice", 50, StockTransactionType.PURCHASE, StockReferenceType.PURCHASE),
        ("Chicken Breast", 2.5, StockTransactionType.SALE, StockReferenceType.SALE),
    ]

    for material_name, qty, txn_type, ref_type in entries:
        material = ctx.raw_materials.get(material_name)
        if material is None:
            continue
        remarks = f"Demo {txn_type.value} for {material_name}"
        existing = (
            db.query(StockLedger)
            .filter(
                StockLedger.tenant_id == tenant.id,
                StockLedger.outlet_id == andheri.id,
                StockLedger.raw_material_id == material.id,
                StockLedger.remarks == remarks,
            )
            .first()
        )
        if existing is not None:
            continue

        is_in = txn_type in (StockTransactionType.PURCHASE, StockTransactionType.TRANSFER_IN)
        db.add(
            StockLedger(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                raw_material_id=material.id,
                transaction_type=txn_type,
                quantity_in=qty if is_in else 0,
                quantity_out=0 if is_in else qty,
                reference_type=ref_type,
                remarks=remarks,
                created_by=admin.id,
            )
        )


def _seed_stock_transfers(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    bandra = ctx.outlets["Bandra"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    paneer = ctx.raw_materials.get("Paneer")
    if admin is None or paneer is None:
        return

    transfer = (
        db.query(StockTransfer)
        .filter(
            StockTransfer.tenant_id == tenant.id,
            StockTransfer.from_outlet_id == andheri.id,
            StockTransfer.to_outlet_id == bandra.id,
            StockTransfer.status == StockTransferStatus.RECEIVED,
        )
        .first()
    )
    if transfer is not None:
        return

    transfer = StockTransfer(
        tenant_id=tenant.id,
        brand_id=brand.id,
        from_outlet_id=andheri.id,
        to_outlet_id=bandra.id,
        status=StockTransferStatus.RECEIVED,
        requested_by=admin.id,
        approved_by=admin.id,
        dispatched_at=datetime.utcnow() - timedelta(days=1),
        received_at=datetime.utcnow() - timedelta(hours=20),
    )
    db.add(transfer)
    db.flush()
    db.add(
        StockTransferItem(
            stock_transfer_id=transfer.id,
            raw_material_id=paneer.id,
            quantity=5,
            unit=paneer.unit,
        )
    )


def _seed_wastage(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    tomato = ctx.raw_materials.get("Tomato")
    if admin is None or tomato is None:
        return

    existing = (
        db.query(Wastage)
        .filter(
            Wastage.tenant_id == tenant.id,
            Wastage.outlet_id == andheri.id,
            Wastage.raw_material_id == tomato.id,
            Wastage.reason == "Spoiled during storage",
        )
        .first()
    )
    if existing is not None:
        return

    db.add(
        Wastage(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            raw_material_id=tomato.id,
            quantity=2,
            reason="Spoiled during storage",
            created_by=admin.id,
        )
    )
