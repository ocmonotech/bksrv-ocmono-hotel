from __future__ import annotations

from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.delivery.models import IntegrationStatus
from app.modules.ota.models import OtaPlatform
from app.modules.pms.models import ReservationStatus


class IntegrationCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    platform: OtaPlatform
    external_property_id: str | None = None
    is_enabled: bool = False
    auto_confirm_reservations: bool = True
    auto_push_availability: bool = False
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict = Field(default_factory=dict)


class IntegrationUpdate(BaseModel):
    external_property_id: str | None = None
    status: IntegrationStatus | None = None
    is_enabled: bool | None = None
    auto_confirm_reservations: bool | None = None
    auto_push_availability: bool | None = None
    api_key: str | None = None
    webhook_secret: str | None = None
    config: dict | None = None


class IntegrationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    platform: OtaPlatform
    external_property_id: str | None
    status: IntegrationStatus
    is_enabled: bool
    auto_confirm_reservations: bool
    auto_push_availability: bool
    webhook_token: str
    config: dict = Field(default_factory=dict)
    has_api_key: bool = False
    has_webhook_secret: bool = False
    last_sync_at: datetime | None = None
    last_error: str | None = None
    webhook_url: str | None = None
    mapping_count: int = 0


class RoomTypeMappingCreate(BaseModel):
    external_room_type_id: str = Field(min_length=1, max_length=64)
    external_room_type_name: str | None = Field(default=None, max_length=128)
    room_type_id: int


class RoomTypeMappingRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    external_room_type_id: str
    external_room_type_name: str | None
    room_type_id: int
    room_type_name: str | None = None


class RatePlanMappingCreate(BaseModel):
    external_rate_id: str = Field(min_length=1, max_length=64)
    external_rate_name: str | None = Field(default=None, max_length=128)
    rate_plan_id: int


class RatePlanMappingRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    external_rate_id: str
    external_rate_name: str | None
    rate_plan_id: int
    rate_plan_name: str | None = None


class InboundOtaReservationPayload(BaseModel):
    external_reservation_id: str
    guest_name: str
    guest_mobile: str
    guest_email: str | None = None
    external_room_type_id: str | None = None
    room_type_id: int | None = None
    external_rate_id: str | None = None
    check_in_date: date
    check_out_date: date
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    notes: str | None = None
    status: str | None = None
    action: str = "create"  # create | modify | cancel

    @field_validator("check_out_date")
    @classmethod
    def checkout_after_checkin(cls, v: date, info) -> date:
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("check_out_date must be after check_in_date")
        return v

    @field_validator("action")
    @classmethod
    def normalize_action(cls, v: str) -> str:
        action = (v or "create").strip().lower()
        if action not in {"create", "modify", "cancel"}:
            raise ValueError("action must be create, modify, or cancel")
        return action


class OtaReservationRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    guest_reservation_id: int
    platform: OtaPlatform
    external_reservation_id: str
    external_status: str | None
    confirmation_number: str
    guest_name: str
    guest_mobile: str
    reservation_status: ReservationStatus
    check_in_date: date
    check_out_date: date
    room_type_name: str | None = None
    total_amount: float


class MockOtaReservationRequest(BaseModel):
    guest_name: str = "OTA Test Guest"
    guest_mobile: str = "+919876543210"
    external_room_type_id: str = "STD"
    check_in_date: date | None = None
    check_out_date: date | None = None
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    notes: str | None = "Simulated OTA booking"


class MockOtaReservationActionRequest(BaseModel):
    external_reservation_id: str = Field(min_length=3, max_length=64)
    check_in_date: date | None = None
    check_out_date: date | None = None
    guest_name: str | None = None
    guest_mobile: str | None = None
    notes: str | None = None


class WebhookAckResponse(BaseModel):
    success: bool
    message: str
    reservation_link_id: int | None = None
    guest_reservation_id: int | None = None


class PlatformInfo(BaseModel):
    platform: OtaPlatform
    label: str
    description: str
    supported_adapter_modes: list[str] = Field(default_factory=lambda: ["mock", "http"])
    default_adapter_mode: str = "mock"


class IntegrationDeleteResponse(MessageResponse):
    integration_id: int


class AriPushRequest(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    max_days: int = Field(default=14, ge=1, le=90)


class AriDayRead(BaseModel):
    date: date
    available_rooms: int
    rate: float
    stop_sell: bool = False
    cta: bool = False
    ctd: bool = False
    min_stay: int | None = None
    max_stay: int | None = None


class AriRoomTypeRead(BaseModel):
    external_room_type_id: str
    external_room_type_name: str | None
    room_type_id: int
    room_type_name: str | None = None
    days: list[AriDayRead] = Field(default_factory=list)


class AriPreviewRead(BaseModel):
    integration_id: int
    outlet_id: int
    platform: OtaPlatform
    external_property_id: str | None
    start_date: date
    end_date: date
    room_types: list[AriRoomTypeRead] = Field(default_factory=list)


class AriPushResponse(BaseModel):
    success: bool
    message: str
    external_reference: str | None = None
    sync_log_id: int | None = None


class ReservationPullItemResult(BaseModel):
    external_reservation_id: str
    success: bool
    message: str
    reservation_link_id: int | None = None
    guest_reservation_id: int | None = None


class ReservationPullResponse(BaseModel):
    success: bool
    message: str
    external_reference: str | None = None
    sync_log_id: int | None = None
    pulled_count: int = 0
    created_count: int = 0
    skipped_count: int = 0
    failed_count: int = 0
    results: list[ReservationPullItemResult] = Field(default_factory=list)


class AutoAriPushResultItem(BaseModel):
    integration_id: int
    platform: OtaPlatform
    success: bool
    message: str
    external_reference: str | None = None
    sync_log_id: int | None = None


class AutoAriPushResponse(BaseModel):
    outlet_id: int | None = None
    integrations_pushed: int
    successes: int
    failures: int
    results: list[AutoAriPushResultItem] = Field(default_factory=list)


class OtaSyncLogRead(ORMSchema, TimestampSchema):
    id: int
    integration_id: int
    sync_type: str
    status: str
    start_date: date
    end_date: date
    room_types_count: int
    days_count: int
    external_reference: str | None
    message: str
