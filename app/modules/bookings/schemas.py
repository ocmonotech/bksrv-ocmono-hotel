from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.bookings.models import BookingPlatform, BookingStatus
from app.modules.delivery.models import IntegrationStatus


class IntegrationCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    platform: BookingPlatform
    external_store_id: str | None = None
    is_enabled: bool = False
    auto_confirm_bookings: bool = False
    auto_reserve_table: bool = True
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    external_store_id: str | None = None
    status: IntegrationStatus | None = None
    is_enabled: bool | None = None
    auto_confirm_bookings: bool | None = None
    auto_reserve_table: bool | None = None
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict | None = None


class IntegrationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    platform: BookingPlatform
    external_store_id: str | None
    status: IntegrationStatus
    is_enabled: bool
    auto_confirm_bookings: bool
    auto_reserve_table: bool
    webhook_token: str
    config: dict = Field(default_factory=dict)
    has_api_key: bool = False
    has_webhook_secret: bool = False
    last_sync_at: datetime | None = None
    last_error: str | None = None
    webhook_url: str | None = None


class InboundBookingPayload(BaseModel):
    external_booking_id: str
    customer_name: str
    customer_phone: str | None = None
    customer_email: str | None = None
    guest_count: int = Field(default=2, ge=1, le=50)
    booked_for: datetime
    duration_minutes: int = Field(default=90, ge=30, le=480)
    special_requests: str | None = None
    notes: str | None = None


class BookingCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    customer_name: str
    customer_phone: str | None = None
    customer_email: str | None = None
    guest_count: int = Field(default=2, ge=1, le=50)
    booked_for: datetime
    duration_minutes: int = Field(default=90, ge=30, le=480)
    table_id: int | None = None
    special_requests: str | None = None
    notes: str | None = None


class BookingRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int | None
    outlet_id: int
    platform: BookingPlatform
    external_booking_id: str | None
    status: BookingStatus
    customer_name: str
    customer_phone: str | None
    customer_email: str | None
    guest_count: int
    booked_for: datetime
    duration_minutes: int
    table_id: int | None
    table_number: str | None = None
    special_requests: str | None
    notes: str | None


class BookingAction(BaseModel):
    notes: str | None = None


class SeatBookingRequest(BaseModel):
    table_id: int
    notes: str | None = None


class MockBookingRequest(BaseModel):
    customer_name: str = "Test Guest"
    customer_phone: str = "+919876543210"
    guest_count: int = Field(default=4, ge=1, le=50)
    booked_for: datetime | None = None
    duration_minutes: int = Field(default=90, ge=30, le=480)
    special_requests: str | None = "Window seat preferred"


class WebhookAckResponse(BaseModel):
    success: bool
    message: str
    booking_id: int | None = None


class PlatformInfo(BaseModel):
    platform: BookingPlatform
    label: str
    description: str


class IntegrationDeleteResponse(MessageResponse):
    integration_id: int
