from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.banquet.models import BanquetBookingStatus, BanquetEventType, BanquetVenueType


class BanquetVenueCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    name: str = Field(max_length=128)
    venue_type: BanquetVenueType
    description: str | None = None
    capacity_min: int = Field(default=20, ge=1, le=5000)
    capacity_max: int = Field(default=200, ge=1, le=5000)
    half_day_rate: float = Field(default=0, ge=0)
    full_day_rate: float = Field(default=0, ge=0)
    amenities: str | None = Field(default=None, max_length=512)


class BanquetVenueUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    venue_type: BanquetVenueType | None = None
    description: str | None = None
    capacity_min: int | None = Field(default=None, ge=1, le=5000)
    capacity_max: int | None = Field(default=None, ge=1, le=5000)
    half_day_rate: float | None = Field(default=None, ge=0)
    full_day_rate: float | None = Field(default=None, ge=0)
    amenities: str | None = Field(default=None, max_length=512)
    is_active: bool | None = None


class BanquetVenueRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    name: str
    venue_type: BanquetVenueType
    description: str | None
    capacity_min: int
    capacity_max: int
    half_day_rate: float
    full_day_rate: float
    amenities: str | None
    is_active: bool


class BanquetBookingCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    venue_id: int
    title: str = Field(max_length=255)
    event_type: BanquetEventType
    event_date: date
    start_time: str = Field(max_length=8)
    end_time: str = Field(max_length=8)
    guest_count: int = Field(default=50, ge=1, le=5000)
    contact_name: str = Field(max_length=255)
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=255)
    guest_reservation_id: int | None = None
    notes: str | None = None
    estimated_amount: float = Field(default=0, ge=0)
    advance_paid: float = Field(default=0, ge=0)
    charge_to_folio: bool = True


class BanquetBookingUpdate(BaseModel):
    venue_id: int | None = None
    title: str | None = Field(default=None, max_length=255)
    event_type: BanquetEventType | None = None
    event_date: date | None = None
    start_time: str | None = Field(default=None, max_length=8)
    end_time: str | None = Field(default=None, max_length=8)
    guest_count: int | None = Field(default=None, ge=1, le=5000)
    contact_name: str | None = Field(default=None, max_length=255)
    contact_phone: str | None = Field(default=None, max_length=32)
    contact_email: str | None = Field(default=None, max_length=255)
    guest_reservation_id: int | None = None
    notes: str | None = None
    estimated_amount: float | None = Field(default=None, ge=0)
    advance_paid: float | None = Field(default=None, ge=0)
    charge_to_folio: bool | None = None
    status: BanquetBookingStatus | None = None


class BanquetBookingRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    venue_id: int
    venue_name: str | None = None
    venue_type: BanquetVenueType | None = None
    booking_number: str
    title: str
    event_type: BanquetEventType
    status: BanquetBookingStatus
    event_date: date
    start_time: str
    end_time: str
    guest_count: int
    contact_name: str
    contact_phone: str | None
    contact_email: str | None
    guest_reservation_id: int | None
    notes: str | None
    estimated_amount: float
    advance_paid: float
    balance_due: float = 0
    charge_to_folio: bool
    folio_posted_at: datetime | None
    deposit_folio_posted_at: datetime | None
    folio_entry_id: int | None = None
    deposit_folio_entry_id: int | None = None
    reminder_sent_at: datetime | None = None
    confirmed_at: datetime | None
    cancelled_at: datetime | None
    is_active: bool


class BanquetDashboard(BaseModel):
    total_venues: int
    active_venues: int
    upcoming_bookings: int
    confirmed_upcoming: int
    inquiry_count: int
    upcoming_events: list[BanquetBookingRead]


class PublicBanquetVenueRead(BaseModel):
    id: int
    outlet_id: int
    name: str
    venue_type: BanquetVenueType
    description: str | None
    capacity_min: int
    capacity_max: int
    half_day_rate: float
    full_day_rate: float
    amenities: str | None


class BanquetAvailabilitySlot(BaseModel):
    start_time: str
    end_time: str
    label: str
    is_available: bool


class BanquetAvailabilityRead(BaseModel):
    venue_id: int
    date: date
    slots: list[BanquetAvailabilitySlot]


class PublicBanquetInquiryCreate(BaseModel):
    outlet_id: int
    venue_id: int
    title: str = Field(max_length=255)
    event_type: BanquetEventType
    event_date: date
    start_time: str = Field(max_length=8)
    end_time: str = Field(max_length=8)
    guest_count: int = Field(default=50, ge=1, le=5000)
    contact_name: str = Field(max_length=255)
    contact_phone: str = Field(max_length=32)
    contact_email: str | None = Field(default=None, max_length=255)
    notes: str | None = None


class PublicBanquetInquiryResponse(BaseModel):
    booking_id: int
    booking_number: str
    message: str
    status: BanquetBookingStatus


class BanquetBookingCompleteRequest(BaseModel):
    post_to_folio: bool = True


class BanquetBookingConfirmRequest(BaseModel):
    send_sms: bool = False
    send_email: bool = False
    send_whatsapp: bool = False


class BanquetNotificationKind(str, enum.Enum):
    INQUIRY_RECEIVED = "inquiry_received"
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"


class BanquetNotificationRequest(BaseModel):
    kind: BanquetNotificationKind = BanquetNotificationKind.CONFIRMATION
    send_sms: bool = True
    send_email: bool = True
    send_whatsapp: bool = True


class BanquetNotificationResponse(MessageResponse):
    booking_id: int
    sent_channels: list[str]
    message_preview: str


class BanquetReminderBatchResult(BaseModel):
    message: str
    reminders_sent: int
    tenants_processed: int
    bookings_checked: int


class BanquetCalendarBooking(BaseModel):
    id: int
    booking_number: str
    title: str
    event_type: BanquetEventType
    start_time: str
    end_time: str
    guest_count: int
    status: BanquetBookingStatus
    contact_name: str


class BanquetCalendarVenueColumn(BaseModel):
    venue_id: int
    name: str
    venue_type: BanquetVenueType
    capacity_min: int
    capacity_max: int
    bookings: list[BanquetCalendarBooking]


class BanquetCalendarRead(BaseModel):
    date: date
    outlet_id: int
    venues: list[BanquetCalendarVenueColumn]
