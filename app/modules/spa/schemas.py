from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.spa.models import SpaBookingStatus, SpaServiceCategory


class SpaServiceCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    name: str = Field(max_length=128)
    category: SpaServiceCategory
    description: str | None = None
    duration_minutes: int = Field(default=60, ge=15, le=480)
    price: float = Field(default=0, ge=0)
    max_capacity: int = Field(default=1, ge=1, le=50)
    slot_interval_minutes: int = Field(default=30, ge=15, le=120)
    operating_start: str = Field(default="09:00", max_length=8)
    operating_end: str = Field(default="21:00", max_length=8)


class SpaServiceUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=128)
    category: SpaServiceCategory | None = None
    description: str | None = None
    duration_minutes: int | None = Field(default=None, ge=15, le=480)
    price: float | None = Field(default=None, ge=0)
    max_capacity: int | None = Field(default=None, ge=1, le=50)
    slot_interval_minutes: int | None = Field(default=None, ge=15, le=120)
    operating_start: str | None = Field(default=None, max_length=8)
    operating_end: str | None = Field(default=None, max_length=8)
    is_active: bool | None = None


class SpaServiceRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    name: str
    category: SpaServiceCategory
    description: str | None
    duration_minutes: int
    price: float
    max_capacity: int
    slot_interval_minutes: int
    operating_start: str
    operating_end: str
    is_active: bool


class SpaBookingCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    service_id: int
    booked_at: datetime
    party_size: int = Field(default=1, ge=1, le=20)
    guest_name: str = Field(max_length=255)
    guest_phone: str | None = Field(default=None, max_length=32)
    guest_email: str | None = Field(default=None, max_length=255)
    customer_id: int | None = None
    guest_reservation_id: int | None = None
    assigned_staff_id: int | None = None
    notes: str | None = None
    charge_to_folio: bool = True


class SpaBookingUpdate(BaseModel):
    booked_at: datetime | None = None
    party_size: int | None = Field(default=None, ge=1, le=20)
    guest_name: str | None = Field(default=None, max_length=255)
    guest_phone: str | None = Field(default=None, max_length=32)
    guest_email: str | None = Field(default=None, max_length=255)
    customer_id: int | None = None
    guest_reservation_id: int | None = None
    assigned_staff_id: int | None = None
    notes: str | None = None
    status: SpaBookingStatus | None = None
    charge_to_folio: bool | None = None


class SpaBookingCompleteRequest(BaseModel):
    post_to_folio: bool = True


class SpaBookingRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    service_id: int
    service_name: str | None = None
    service_category: SpaServiceCategory | None = None
    booking_number: str
    status: SpaBookingStatus
    booked_at: datetime
    duration_minutes: int
    party_size: int
    price: float
    guest_name: str
    guest_phone: str | None
    guest_email: str | None
    customer_id: int | None
    guest_reservation_id: int | None
    assigned_staff_id: int | None
    assigned_staff_name: str | None = None
    notes: str | None
    confirmed_at: datetime | None
    started_at: datetime | None
    completed_at: datetime | None
    cancelled_at: datetime | None
    charge_to_folio: bool
    folio_posted_at: datetime | None
    folio_entry_id: int | None = None
    reminder_sent_at: datetime | None = None


class SpaAvailabilitySlot(BaseModel):
    start_time: str
    end_time: str
    available_capacity: int
    is_available: bool


class SpaAvailabilityRead(BaseModel):
    service_id: int
    date: date
    slots: list[SpaAvailabilitySlot]


class SpaDashboard(BaseModel):
    total_services: int
    active_services: int
    today_bookings: int
    pending_today: int
    confirmed_today: int
    in_progress_today: int
    upcoming_bookings: list[SpaBookingRead]


class SpaTherapistCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    user_id: int
    title: str | None = Field(default=None, max_length=64)
    specialties: str | None = Field(default=None, max_length=255)
    shift_start: str = Field(default="09:00", max_length=8)
    shift_end: str = Field(default="18:00", max_length=8)
    calendar_color: str = Field(default="#8b5cf6", max_length=7)


class SpaTherapistUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=64)
    specialties: str | None = Field(default=None, max_length=255)
    shift_start: str | None = Field(default=None, max_length=8)
    shift_end: str | None = Field(default=None, max_length=8)
    calendar_color: str | None = Field(default=None, max_length=7)
    is_active: bool | None = None


class SpaTherapistRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    user_id: int
    user_name: str | None = None
    user_email: str | None = None
    title: str | None
    specialties: str | None
    shift_start: str
    shift_end: str
    calendar_color: str
    is_active: bool


class SpaCalendarBooking(BaseModel):
    id: int
    booking_number: str
    guest_name: str
    service_name: str | None
    booked_at: datetime
    duration_minutes: int
    status: SpaBookingStatus
    assigned_staff_id: int | None = None


class SpaCalendarTherapistColumn(BaseModel):
    therapist_id: int
    user_id: int
    name: str
    title: str | None
    specialties: str | None
    shift_start: str
    shift_end: str
    calendar_color: str
    bookings: list[SpaCalendarBooking]


class SpaCalendarRead(BaseModel):
    date: date
    outlet_id: int
    therapists: list[SpaCalendarTherapistColumn]
    unassigned: list[SpaCalendarBooking]


class SpaBookingAssignRequest(BaseModel):
    assigned_staff_id: int | None = None


class PublicSpaServiceRead(BaseModel):
    id: int
    outlet_id: int
    name: str
    category: SpaServiceCategory
    description: str | None
    duration_minutes: int
    price: float
    operating_start: str
    operating_end: str


class PublicSpaBookingCreate(BaseModel):
    outlet_id: int
    service_id: int
    booked_at: datetime
    guest_name: str = Field(max_length=255)
    guest_phone: str = Field(max_length=32)
    guest_email: str | None = Field(default=None, max_length=255)
    party_size: int = Field(default=1, ge=1, le=10)
    notes: str | None = None
    # Optional mock prepaid / card guarantee for public guests
    pay_now: bool = False
    payment_provider: str | None = Field(
        default=None,
        description="razorpay | phonepe | cashfree | ccavenue | paytm",
    )
    card_last4: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    payment_amount: float | None = Field(default=None, ge=0)


class PublicSpaBookingResponse(BaseModel):
    booking_id: int
    booking_number: str
    message: str
    status: SpaBookingStatus
    payment_ref: str | None = None
    payment_amount: float | None = None
    card_last4: str | None = None
    paid: bool = False


class SpaBookingConfirmRequest(BaseModel):
    send_sms: bool = False
    send_email: bool = False
    send_whatsapp: bool = False


class SpaNotificationKind(str, enum.Enum):
    REQUEST_RECEIVED = "request_received"
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"


class SpaNotificationRequest(BaseModel):
    kind: SpaNotificationKind = SpaNotificationKind.CONFIRMATION
    send_sms: bool = True
    send_email: bool = True
    send_whatsapp: bool = True


class SpaNotificationResponse(MessageResponse):
    booking_id: int
    sent_channels: list[str]
    message_preview: str


class SpaReminderBatchResult(BaseModel):
    message: str
    reminders_sent: int
    tenants_processed: int
    bookings_checked: int
