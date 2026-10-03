from __future__ import annotations

from typing import Optional

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class MaterialUnit(str, enum.Enum):
    KG = "kg"
    LITRE = "litre"
    PIECE = "piece"
    PACKET = "packet"
    GRAM = "gram"
    ML = "ml"


class PaymentStatus(str, enum.Enum):
    PENDING = "pending"
    PAID = "paid"
    PARTIAL = "partial"


class ApprovalStatus(str, enum.Enum):
    PENDING = "pending"
    APPROVED = "approved"
    REJECTED = "rejected"


class StockTransactionType(str, enum.Enum):
    PURCHASE = "purchase"
    SALE = "sale"
    WASTAGE = "wastage"
    TRANSFER_IN = "transfer_in"
    TRANSFER_OUT = "transfer_out"
    ADJUSTMENT = "adjustment"


class StockReferenceType(str, enum.Enum):
    PURCHASE = "purchase"
    WASTAGE = "wastage"
    STOCK_TRANSFER = "stock_transfer"
    SALE = "sale"
    ADJUSTMENT = "adjustment"


class StockTransferStatus(str, enum.Enum):
    REQUESTED = "requested"
    APPROVED = "approved"
    DISPATCHED = "dispatched"
    RECEIVED = "received"
    REJECTED = "rejected"


class RawMaterial(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "raw_materials"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    category: Mapped[str] = mapped_column(String(128), default="General", nullable=False)
    unit: Mapped[MaterialUnit] = mapped_column(Enum(MaterialUnit), default=MaterialUnit.KG)
    reorder_level: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    average_unit_cost: Mapped[float] = mapped_column(Numeric(12, 4), default=0, nullable=False)
    last_purchase_rate: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)


class Vendor(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "vendors"

    vendor_name: Mapped[str] = mapped_column(String(255), nullable=False)
    mobile: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    gst_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class Purchase(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "purchases"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    vendor_id: Mapped[int] = mapped_column(ForeignKey("vendors.id"), index=True, nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(64), nullable=False)
    purchase_date: Mapped[date] = mapped_column(Date, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    payment_status: Mapped[PaymentStatus] = mapped_column(
        Enum(PaymentStatus), default=PaymentStatus.PENDING
    )
    approval_status: Mapped[ApprovalStatus] = mapped_column(
        Enum(ApprovalStatus), default=ApprovalStatus.PENDING
    )
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    items: Mapped[list["PurchaseItem"]] = relationship(
        back_populates="purchase",
        cascade="all, delete-orphan",
    )


class PurchaseItem(Base, BaseMixin):
    __tablename__ = "purchase_items"

    purchase_id: Mapped[int] = mapped_column(ForeignKey("purchases.id"), index=True, nullable=False)
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id"), index=True, nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[MaterialUnit] = mapped_column(Enum(MaterialUnit), nullable=False)
    rate: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0)
    total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)

    purchase: Mapped["Purchase"] = relationship(back_populates="items")


class StockLedger(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "stock_ledger"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id"), index=True, nullable=False
    )
    transaction_type: Mapped[StockTransactionType] = mapped_column(Enum(StockTransactionType))
    quantity_in: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    quantity_out: Mapped[float] = mapped_column(Numeric(12, 3), default=0)
    reference_type: Mapped[Optional[StockReferenceType]] = mapped_column(
        Enum(StockReferenceType), nullable=True
    )
    reference_id: Mapped[Optional[int]] = mapped_column(nullable=True)
    remarks: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    unit_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 4), nullable=True)
    line_cost: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class StockTransfer(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "stock_transfers"

    from_outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    to_outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    status: Mapped[StockTransferStatus] = mapped_column(
        Enum(StockTransferStatus), default=StockTransferStatus.REQUESTED
    )
    requested_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    dispatched_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    received_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    items: Mapped[list["StockTransferItem"]] = relationship(
        back_populates="stock_transfer",
        cascade="all, delete-orphan",
    )


class StockTransferItem(Base, BaseMixin):
    __tablename__ = "stock_transfer_items"

    stock_transfer_id: Mapped[int] = mapped_column(
        ForeignKey("stock_transfers.id"), index=True, nullable=False
    )
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id"), index=True, nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit: Mapped[MaterialUnit] = mapped_column(Enum(MaterialUnit), nullable=False)

    stock_transfer: Mapped["StockTransfer"] = relationship(back_populates="items")


class Wastage(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "wastage"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    raw_material_id: Mapped[int] = mapped_column(
        ForeignKey("raw_materials.id"), index=True, nullable=False
    )
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    day_part: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
