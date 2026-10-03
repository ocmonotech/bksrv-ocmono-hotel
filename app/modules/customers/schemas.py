from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field

from app.common.response import ORMSchema, TimestampSchema
from app.modules.customers.models import (
    CustomerSource,
    CustomerStatus,
    FeedbackSentiment,
    FeedbackSource,
)


class CustomerCreate(BaseModel):
    full_name: str = Field(min_length=1, max_length=255)
    mobile: str = Field(min_length=5, max_length=32)
    email: str | None = None
    birthday: date | None = None
    anniversary: date | None = None
    source: CustomerSource = CustomerSource.WALK_IN
    consent_whatsapp: bool = False
    consent_sms: bool = False
    consent_email: bool = False
    favourite_outlet_id: int | None = None
    brand_id: int | None = None


class CustomerUpdate(BaseModel):
    full_name: str | None = Field(default=None, min_length=1, max_length=255)
    mobile: str | None = Field(default=None, min_length=5, max_length=32)
    email: str | None = None
    birthday: date | None = None
    anniversary: date | None = None
    source: CustomerSource | None = None
    consent_whatsapp: bool | None = None
    consent_sms: bool | None = None
    consent_email: bool | None = None
    favourite_outlet_id: int | None = None
    status: CustomerStatus | None = None
    loyalty_points: int | None = Field(default=None, ge=0)


class CustomerRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    full_name: str
    mobile: str
    email: str | None
    birthday: date | None
    anniversary: date | None
    source: CustomerSource
    consent_whatsapp: bool
    consent_sms: bool
    consent_email: bool
    total_visits: int
    total_spend: float
    loyalty_points: int
    last_visit_at: datetime | None
    favourite_outlet_id: int | None
    status: CustomerStatus
    is_active: bool


class CustomerTagRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    name: str
    is_active: bool


class CustomerProfileRead(CustomerRead):
    tags: list[CustomerTagRead] = []
    recent_visit_count: int = 0
    feedback_count: int = 0
    average_rating: float | None = None


class CustomerTagAssign(BaseModel):
    tag_id: int | None = None
    name: str | None = Field(default=None, min_length=1, max_length=64)


class CustomerVisitRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    customer_id: int
    bill_id: int | None
    visit_date: datetime
    total_amount: float


class FeedbackCreate(BaseModel):
    outlet_id: int
    customer_id: int
    rating: int = Field(ge=1, le=5)
    message: str | None = None
    sentiment: FeedbackSentiment | None = None
    source: FeedbackSource = FeedbackSource.POS
    brand_id: int | None = None


class FeedbackRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    customer_id: int
    rating: int
    message: str | None
    sentiment: FeedbackSentiment
    source: FeedbackSource


class VipCustomerRead(CustomerRead):
    vip_reason: str


class InactiveCustomerRead(CustomerRead):
    days_since_last_visit: int | None = None


class Guest360OutletTouch(BaseModel):
    outlet_id: int
    outlet_name: str | None = None
    last_at: datetime | None = None
    channels: list[str] = Field(default_factory=list)


class Guest360Stay(BaseModel):
    reservation_id: int
    confirmation_number: str
    outlet_id: int
    outlet_name: str | None = None
    status: str
    check_in_date: date
    check_out_date: date
    room_number: str | None = None
    guest_mobile: str | None = None
    notes: str | None = None


class Guest360PosVisit(BaseModel):
    id: int
    outlet_id: int
    outlet_name: str | None = None
    visit_date: datetime
    total_amount: float
    bill_id: int | None = None


class Guest360Spa(BaseModel):
    booking_id: int
    booking_number: str | None = None
    outlet_id: int
    outlet_name: str | None = None
    service_name: str | None = None
    status: str
    booked_at: datetime | None = None
    price: float = 0
    guest_reservation_id: int | None = None


class Guest360Banquet(BaseModel):
    booking_id: int
    booking_number: str | None = None
    title: str | None = None
    outlet_id: int
    outlet_name: str | None = None
    event_date: date | None = None
    status: str
    estimated_amount: float = 0


class Guest360LoyaltyLedger(BaseModel):
    id: int
    points: int
    txn_type: str
    source: str | None = None
    description: str | None = None
    created_at: datetime | None = None


class Guest360Loyalty(BaseModel):
    points: int = 0
    tier_code: str | None = None
    tier_name: str | None = None
    recent_ledger: list[Guest360LoyaltyLedger] = Field(default_factory=list)


class Guest360Preferences(BaseModel):
    tags: list[str] = Field(default_factory=list)
    favourite_outlet_id: int | None = None
    notes_snippets: list[str] = Field(default_factory=list)


class Guest360Summary(BaseModel):
    hotel_stays: int = 0
    cafe_visits: int = 0
    spa_bookings: int = 0
    banquet_events: int = 0
    lifetime_spend: float = 0
    last_touch_at: datetime | None = None
    last_touch_channel: str | None = None


class Guest360TimelineItem(BaseModel):
    channel: str
    at: datetime | None = None
    title: str
    subtitle: str | None = None
    amount: float | None = None
    outlet_name: str | None = None
    reference_id: str | None = None


class Guest360Read(BaseModel):
    profile: CustomerProfileRead
    outlets_touched: list[Guest360OutletTouch] = Field(default_factory=list)
    stays: list[Guest360Stay] = Field(default_factory=list)
    pos_visits: list[Guest360PosVisit] = Field(default_factory=list)
    spa: list[Guest360Spa] = Field(default_factory=list)
    banquet: list[Guest360Banquet] = Field(default_factory=list)
    loyalty: Guest360Loyalty = Field(default_factory=Guest360Loyalty)
    feedback: list[FeedbackRead] = Field(default_factory=list)
    preferences: Guest360Preferences = Field(default_factory=Guest360Preferences)
    summary: Guest360Summary = Field(default_factory=Guest360Summary)
    timeline: list[Guest360TimelineItem] = Field(default_factory=list)
