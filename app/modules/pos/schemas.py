from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.kot.schemas import KotSummary
from app.modules.pos.models import (
    BillPaymentStatus,
    CancelReasonType,
    OrderItemStatus,
    OrderSource,
    OrderStatus,
    OrderType,
    PaymentMode,
    PaymentRecordStatus,
)


class OrderCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    table_id: int | None = None
    customer_id: int | None = None
    order_type: OrderType = OrderType.DINE_IN


class OrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1)
    discount_amount: float = Field(default=0, ge=0)
    note: str | None = None
    addon_ids: list[int] = Field(default_factory=list)


class OrderItemUpdate(BaseModel):
    quantity: int = Field(ge=1)


class OrderItemRead(ORMSchema, TimestampSchema):
    id: int
    order_id: int
    menu_item_id: int
    item_name: str
    quantity: int
    price: float
    discount_amount: float
    gst_percent: float
    note: str | None
    status: OrderItemStatus
    is_active: bool


class OrderRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    table_id: int | None
    customer_id: int | None
    order_number: str
    order_type: OrderType
    order_source: OrderSource = OrderSource.IN_HOUSE
    source_reference: str | None = None
    queue_token: str | None = None
    pickup_at: datetime | None = None
    ready_at: datetime | None = None
    order_status: OrderStatus
    subtotal: float
    discount_amount: float
    service_charge: float
    gst_amount: float
    grand_total: float
    created_by: int | None
    items: list[OrderItemRead] = Field(default_factory=list)


class PickupOrderRead(BaseModel):
    order_id: int
    order_number: str
    queue_token: str | None = None
    guest_name: str | None = None
    order_status: OrderStatus
    pickup_at: datetime | None = None
    ready_at: datetime | None = None
    grand_total: float


class BillRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    order_id: int
    bill_number: str
    subtotal: float
    discount_amount: float
    service_charge: float
    gst_amount: float
    round_off: float
    grand_total: float
    payment_status: BillPaymentStatus
    created_by: int | None


class PaymentCreate(BaseModel):
    payment_mode: PaymentMode
    amount: float = Field(gt=0)
    tip_amount: float = Field(default=0, ge=0)
    reference_number: str | None = None
    loyalty_points: int | None = Field(default=None, ge=1)


class PaymentRead(BaseModel):
    id: int
    bill_id: int
    payment_mode: PaymentMode
    amount: float
    tip_amount: float = 0
    reference_number: str | None
    status: PaymentRecordStatus

    model_config = {"from_attributes": True}


class CancelOrderRequest(BaseModel):
    reason_type: CancelReasonType = CancelReasonType.ORDER
    reason_text: str = Field(min_length=3, max_length=255)


class CancelBillRequest(BaseModel):
    reason_text: str = Field(min_length=3, max_length=255)


class CancelBillPlaceholderResponse(MessageResponse):
    bill_id: int


class DiscountApprovalRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=255)


class DiscountApprovalResponse(MessageResponse):
    order_id: int
    discount_amount: float


class SendKotResponse(BaseModel):
    order_id: int
    order_status: OrderStatus
    kots: list[KotSummary] = Field(default_factory=list)
    message: str = "Order sent to KOT and inventory updated"
