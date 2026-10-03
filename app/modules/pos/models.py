from __future__ import annotations

from typing import Optional

import enum

from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class OrderType(str, enum.Enum):
    DINE_IN = "dine_in"
    TAKEAWAY = "takeaway"
    DELIVERY = "delivery"


class OrderSource(str, enum.Enum):
    IN_HOUSE = "in_house"
    ZOMATO = "zomato"
    SWIGGY = "swiggy"
    ONDC = "ondc"
    DUNZO = "dunzo"
    MAGICPIN = "magicpin"


class OrderStatus(str, enum.Enum):
    DRAFT = "draft"
    KOT_SENT = "kot_sent"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    BILLED = "billed"
    CANCELLED = "cancelled"


class OrderItemStatus(str, enum.Enum):
    NEW = "new"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"


class PaymentMode(str, enum.Enum):
    CASH = "cash"
    UPI = "upi"
    CARD = "card"
    ONLINE = "online"
    SPLIT = "split"
    ROOM_CHARGE = "room_charge"
    LOYALTY = "loyalty"


class PaymentRecordStatus(str, enum.Enum):
    PENDING = "pending"
    SUCCESS = "success"
    FAILED = "failed"


class BillPaymentStatus(str, enum.Enum):
    UNPAID = "unpaid"
    PARTIAL = "partial"
    PAID = "paid"
    REFUNDED = "refunded"
    CANCELLED = "cancelled"


class CancelReasonType(str, enum.Enum):
    ORDER = "order_cancel"
    BILL = "bill_cancel"
    ITEM = "item_cancel"


class Order(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "pos_orders"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    table_id: Mapped[Optional[int]] = mapped_column(ForeignKey("restaurant_tables.id"), nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True)
    order_number: Mapped[str] = mapped_column(String(32), index=True)
    order_type: Mapped[OrderType] = mapped_column(Enum(OrderType), default=OrderType.DINE_IN)
    order_source: Mapped[OrderSource] = mapped_column(
        Enum(OrderSource), default=OrderSource.IN_HOUSE, nullable=False
    )
    source_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True, index=True)
    pickup_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True, index=True)
    ready_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    order_status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.DRAFT)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    service_charge: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    items: Mapped[list["OrderItem"]] = relationship(
        back_populates="order",
        cascade="all, delete-orphan",
    )
    bills: Mapped[list["Bill"]] = relationship(back_populates="order")


class OrderItem(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "pos_order_items"

    order_id: Mapped[int] = mapped_column(ForeignKey("pos_orders.id", ondelete="CASCADE"), index=True)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    price: Mapped[float] = mapped_column(Numeric(10, 2))
    discount_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=5)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[OrderItemStatus] = mapped_column(Enum(OrderItemStatus), default=OrderItemStatus.NEW)

    order: Mapped["Order"] = relationship(back_populates="items")


class Bill(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "pos_bills"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("pos_orders.id"), index=True)
    bill_number: Mapped[str] = mapped_column(String(32), unique=True, index=True)
    subtotal: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    discount_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    service_charge: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    gst_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    round_off: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    grand_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    payment_status: Mapped[BillPaymentStatus] = mapped_column(
        Enum(BillPaymentStatus), default=BillPaymentStatus.UNPAID
    )
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    order: Mapped["Order"] = relationship(back_populates="bills")
    payments: Mapped[list["Payment"]] = relationship(
        back_populates="bill",
        cascade="all, delete-orphan",
    )


class Payment(Base):
    __tablename__ = "pos_payments"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    bill_id: Mapped[int] = mapped_column(ForeignKey("pos_bills.id", ondelete="CASCADE"), index=True)
    payment_mode: Mapped[PaymentMode] = mapped_column(
        Enum(PaymentMode, values_callable=lambda enum_cls: [member.name for member in enum_cls])
    )
    amount: Mapped[float] = mapped_column(Numeric(12, 2))
    tip_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    reference_number: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[PaymentRecordStatus] = mapped_column(
        Enum(PaymentRecordStatus), default=PaymentRecordStatus.SUCCESS
    )

    bill: Mapped["Bill"] = relationship(back_populates="payments")


class CancelReason(Base, TenantBrandMixin):
    __tablename__ = "pos_cancel_reasons"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    reason_type: Mapped[CancelReasonType] = mapped_column(Enum(CancelReasonType), index=True)
    reason_text: Mapped[str] = mapped_column(String(255), nullable=False)


# Backward-compatible aliases
PosOrder = Order
PosOrderItem = OrderItem
