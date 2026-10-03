from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.events.models import EventActivityType, EventSource, EventStatus, EventType


class EventCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    customer_id: int | None = None
    lead_id: int | None = None
    offer_id: int | None = None
    event_type: EventType
    title: str = Field(max_length=255)
    guest_of_honor: str | None = Field(default=None, max_length=255)
    customer_name: str = Field(max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    customer_email: str | None = Field(default=None, max_length=255)
    event_date: date
    start_time: str = Field(max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    duration_minutes: int = Field(default=180, ge=30, le=720)
    expected_guests: int = Field(default=10, ge=1, le=500)
    source: EventSource = EventSource.WALK_IN
    assigned_to: int | None = None
    special_requests: str | None = None
    decoration_notes: str | None = None
    dietary_notes: str | None = None
    estimated_amount: float = Field(default=0, ge=0)
    advance_paid: float = Field(default=0, ge=0)
    table_ids: list[int] = Field(default_factory=list)


class EventUpdate(BaseModel):
    event_type: EventType | None = None
    title: str | None = Field(default=None, max_length=255)
    guest_of_honor: str | None = Field(default=None, max_length=255)
    customer_name: str | None = Field(default=None, max_length=255)
    customer_phone: str | None = Field(default=None, max_length=32)
    customer_email: str | None = Field(default=None, max_length=255)
    event_date: date | None = None
    start_time: str | None = Field(default=None, max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    duration_minutes: int | None = Field(default=None, ge=30, le=720)
    expected_guests: int | None = Field(default=None, ge=1, le=500)
    confirmed_guests: int | None = Field(default=None, ge=1, le=500)
    status: EventStatus | None = None
    source: EventSource | None = None
    assigned_to: int | None = None
    special_requests: str | None = None
    decoration_notes: str | None = None
    dietary_notes: str | None = None
    estimated_amount: float | None = Field(default=None, ge=0)
    advance_paid: float | None = Field(default=None, ge=0)
    offer_id: int | None = None
    table_ids: list[int] | None = None


class EventTableAssignmentRead(ORMSchema, TimestampSchema):
    id: int
    table_id: int
    table_number: str | None = None
    reserved_from: datetime
    reserved_until: datetime


class EventActivityCreate(BaseModel):
    activity_type: EventActivityType = EventActivityType.NOTE
    note: str | None = None


class EventActivityRead(ORMSchema, TimestampSchema):
    id: int
    event_id: int
    activity_type: EventActivityType
    note: str | None
    created_by: int


class EventRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    customer_id: int | None
    lead_id: int | None
    booking_id: int | None
    pos_order_id: int | None
    offer_id: int | None
    event_type: EventType
    title: str
    guest_of_honor: str | None
    customer_name: str
    customer_phone: str | None
    customer_email: str | None
    event_date: date
    start_time: str
    end_time: str | None
    duration_minutes: int
    expected_guests: int
    confirmed_guests: int | None
    status: EventStatus
    source: EventSource
    assigned_to: int | None
    special_requests: str | None
    decoration_notes: str | None
    dietary_notes: str | None
    estimated_amount: float
    advance_paid: float
    balance_due: float = 0
    is_active: bool


class EventDetailRead(EventRead):
    tables: list[EventTableAssignmentRead] = Field(default_factory=list)
    activities: list[EventActivityRead] = Field(default_factory=list)
    preorders: list["EventPreOrderRead"] = Field(default_factory=list)


class EventPreOrderItemCreate(BaseModel):
    menu_item_id: int
    quantity: int = Field(default=1, ge=1, le=500)
    notes: str | None = Field(default=None, max_length=255)


class EventPreOrderRead(ORMSchema, TimestampSchema):
    id: int
    event_id: int
    menu_item_id: int
    item_name: str
    quantity: int
    unit_price: float
    notes: str | None


class EventPreOrdersReplace(BaseModel):
    items: list[EventPreOrderItemCreate] = Field(default_factory=list)


class EventPosOrderResponse(BaseModel):
    event_id: int
    pos_order_id: int
    order_number: str
    message: str = "POS order created from event"


class PublicEventInquiryCreate(BaseModel):
    outlet_id: int
    event_type: EventType
    title: str = Field(max_length=255)
    customer_name: str = Field(max_length=255)
    customer_phone: str = Field(max_length=32)
    customer_email: str | None = Field(default=None, max_length=255)
    guest_of_honor: str | None = Field(default=None, max_length=255)
    event_date: date
    start_time: str = Field(default="19:00", max_length=8)
    expected_guests: int = Field(default=10, ge=1, le=500)
    special_requests: str | None = None
    package_id: str | None = None


class PublicEventInquiryResponse(BaseModel):
    event_id: int
    message: str
    status: EventStatus


class EventConfirmRequest(BaseModel):
    table_ids: list[int] = Field(default_factory=list)
    notes: str | None = None
    send_whatsapp: bool = False


class EventFromLeadCreate(BaseModel):
    lead_id: int
    event_type: EventType | None = None
    title: str | None = Field(default=None, max_length=255)
    event_date: date | None = None
    start_time: str | None = Field(default=None, max_length=8)
    expected_guests: int | None = Field(default=None, ge=1, le=500)
    special_requests: str | None = None
    estimated_amount: float | None = Field(default=None, ge=0)


class EventWhatsAppKind(str, enum.Enum):
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"


class EventWhatsAppRequest(BaseModel):
    kind: EventWhatsAppKind = EventWhatsAppKind.CONFIRMATION


class EventWhatsAppResponse(MessageResponse):
    event_id: int
    message_preview: str


class EventCancelRequest(BaseModel):
    notes: str | None = None


class EventDeleteResponse(MessageResponse):
    event_id: int


class EventPackageRead(BaseModel):
    id: str
    name: str
    event_type: EventType
    price_per_person: float
    min_guests: int
    includes: list[str] = Field(default_factory=list)
    description: str | None = None


class BirthdayOpportunityRead(BaseModel):
    customer_id: int
    customer_name: str
    mobile: str
    birthday: date
    days_until: int
    favourite_outlet_id: int | None = None
