from __future__ import annotations

import enum
from datetime import date, datetime

from pydantic import BaseModel, Field, field_validator, model_validator

from app.common.response import MessageResponse, ORMSchema, TimestampSchema
from app.modules.pms.models import (
    CreditScope,
    DepositStatus,
    FolioEntryType,
    FolioStatus,
    GuaranteeType,
    InclusionType,
    PaymentTender,
    ReservationSource,
    ReservationStatus,
    RoomBlockType,
)


class ReservationCreate(BaseModel):
    outlet_id: int
    guest_name: str = Field(min_length=1, max_length=255)
    guest_email: str | None = None
    guest_mobile: str = Field(min_length=6, max_length=32)
    customer_id: int | None = None
    room_type_id: int
    room_id: int | None = None
    check_in_date: date
    check_out_date: date
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    source: ReservationSource = ReservationSource.DIRECT
    rate_plan_id: int | None = None
    rate_per_night: float = Field(ge=0)
    deposit_amount: float = Field(default=0, ge=0)
    notes: str | None = None
    auto_confirm: bool = False
    group_id: int | None = None
    guest_id_document: str | None = Field(default=None, max_length=64)
    early_check_in: bool = False
    late_check_out: bool = False
    day_use: bool = False
    guarantee_type: GuaranteeType = GuaranteeType.NONE

    @field_validator("check_out_date")
    @classmethod
    def checkout_not_before_checkin(cls, v: date, info) -> date:
        check_in = info.data.get("check_in_date")
        if check_in and v < check_in:
            raise ValueError("check_out_date cannot be before check_in_date")
        return v

    @model_validator(mode="after")
    def day_use_and_stay_rules(self) -> "ReservationCreate":
        if self.day_use and self.late_check_out:
            raise ValueError("Day use cannot be combined with late check-out")
        if not self.day_use and self.check_out_date <= self.check_in_date:
            raise ValueError("check_out_date must be after check_in_date")
        return self


class ReservationUpdate(BaseModel):
    guest_name: str | None = Field(default=None, min_length=1, max_length=255)
    guest_email: str | None = None
    guest_mobile: str | None = Field(default=None, min_length=6, max_length=32)
    room_type_id: int | None = None
    room_id: int | None = None
    check_in_date: date | None = None
    check_out_date: date | None = None
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)
    rate_per_night: float | None = Field(default=None, ge=0)
    deposit_amount: float | None = Field(default=None, ge=0)
    notes: str | None = None
    group_id: int | None = None
    guest_id_document: str | None = Field(default=None, max_length=64)
    early_check_in: bool | None = None
    late_check_out: bool | None = None
    day_use: bool | None = None
    guarantee_type: GuaranteeType | None = None
    deposit_status: DepositStatus | None = None


class CheckInRequest(BaseModel):
    room_id: int
    notes: str | None = None


class CheckOutRequest(BaseModel):
    notes: str | None = None
    force_settle: bool = False


class WalkInCreate(ReservationCreate):
    source: ReservationSource = ReservationSource.WALK_IN
    auto_confirm: bool = True
    immediate_check_in: bool = False


class CancelReservationRequest(BaseModel):
    reason: str | None = None


class FolioChargeCreate(BaseModel):
    entry_type: FolioEntryType = FolioEntryType.ADJUSTMENT
    description: str = Field(min_length=1, max_length=255)
    amount: float


class FolioEmailRequest(BaseModel):
    to_email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=500)


class FolioEmailResponse(MessageResponse):
    reservation_id: int
    folio_number: str
    sent_to: str


class FrontDeskReadinessItem(BaseModel):
    reservation_id: int
    confirmation_number: str
    guest_name: str
    status: ReservationStatus
    room_type_id: int
    room_type_name: str | None = None
    room_id: int | None = None
    room_number: str | None = None
    room_status: str | None = None
    readiness: str  # ready | not_ready | unassigned
    clean_rooms_available: int = 0
    pre_check_in_status: str = "none"
    estimated_arrival_time: str | None = None
    guest_id_document: str | None = None
    guest_id_document_type: str | None = None


class FrontDeskReadinessResponse(BaseModel):
    outlet_id: int
    business_date: date
    arrivals_total: int
    ready_count: int
    not_ready_count: int
    unassigned_count: int
    clean_inventory: int
    pre_check_in_submitted_count: int = 0
    items: list[FrontDeskReadinessItem]


class FolioPaymentCreate(BaseModel):
    description: str | None = Field(default=None, max_length=255)
    amount: float = Field(gt=0)
    tender: PaymentTender = PaymentTender.CASH
    loyalty_points: int | None = Field(default=None, ge=1)


class ReservationRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    confirmation_number: str
    guest_name: str
    guest_email: str | None
    guest_mobile: str
    customer_id: int | None
    room_type_id: int
    room_id: int | None
    room_number: str | None = None
    room_type_name: str | None = None
    check_in_date: date
    check_out_date: date
    nights: int = 0
    adults: int
    children: int
    status: ReservationStatus
    source: ReservationSource
    rate_plan_id: int | None = None
    rate_plan_name: str | None = None
    package_inclusions: list["RatePlanInclusionRead"] = Field(default_factory=list)
    package_entitlements: list["PackageEntitlementRead"] = Field(default_factory=list)
    group_id: int | None = None
    guest_id_document: str | None = None
    guest_id_document_type: str | None = None
    estimated_arrival_time: str | None = None
    pre_check_in_status: str = "none"
    pre_check_in_at: datetime | None = None
    pre_check_in_notes: str | None = None
    pre_check_in_reviewed_at: datetime | None = None
    express_checkout_status: str = "none"
    express_checkout_at: datetime | None = None
    express_checkout_notes: str | None = None
    estimated_departure_time: str | None = None
    express_checkout_reviewed_at: datetime | None = None
    early_check_in: bool = False
    late_check_out: bool = False
    day_use: bool = False
    guarantee_type: GuaranteeType = GuaranteeType.NONE
    deposit_status: DepositStatus = DepositStatus.PENDING
    rate_per_night: float
    total_amount: float
    deposit_amount: float
    payment_provider: str | None = None
    payment_hold_ref: str | None = None
    payment_auth_code: str | None = None
    card_last4: str | None = None
    hold_expires_at: datetime | None = None
    notes: str | None
    checked_in_at: datetime | None
    checked_out_at: datetime | None
    reminder_sent_at: datetime | None = None
    created_by: int | None


class CardHoldRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    card_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    hold_days: int = Field(default=7, ge=1, le=30)
    notes: str | None = None
    simulate_decline: bool = False


class CardHoldReleaseRequest(BaseModel):
    notes: str | None = None


class FolioEntryRead(ORMSchema, TimestampSchema):
    id: int
    entry_type: FolioEntryType
    description: str
    amount: float
    pos_order_id: int | None
    spa_booking_id: int | None = None
    posted_by: int | None


class FolioRead(ORMSchema, TimestampSchema):
    id: int
    reservation_id: int | None = None
    group_id: int | None = None
    folio_number: str
    status: FolioStatus
    balance: float
    entries: list[FolioEntryRead] = Field(default_factory=list)


class FolioTransferToMasterRequest(BaseModel):
    reservation_id: int
    amount: float = Field(gt=0)
    description: str | None = Field(default=None, max_length=255)


class CityLedgerTransferRequest(BaseModel):
    amount: float = Field(gt=0)
    company_name: str = Field(min_length=1, max_length=255)
    notes: str | None = Field(default=None, max_length=500)


class CityLedgerSettleRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    tender: PaymentTender = PaymentTender.OTHER
    notes: str | None = Field(default=None, max_length=500)


class CityLedgerWriteOffRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=500)


class CityLedgerRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    reservation_id: int | None
    group_id: int | None = None
    folio_id: int | None
    reference: str
    company_name: str
    guest_name: str | None
    original_amount: float
    balance: float
    status: str
    notes: str | None
    created_by: int | None
    settled_at: datetime | None
    settled_by: int | None
    confirmation_number: str | None = None
    group_code: str | None = None


class CityLedgerTransferResponse(BaseModel):
    folio: FolioRead
    city_ledger: CityLedgerRead
    message: str


class ReservationDetailRead(ReservationRead):
    folio: FolioRead | None = None
    city_ledger_entries: list[CityLedgerRead] = Field(default_factory=list)


class RoomTypeAvailability(BaseModel):
    room_type_id: int
    room_type_name: str
    total_rooms: int
    available_rooms: int
    base_rate: float
    resolved_rate: float
    rate_plan_id: int | None = None
    rate_plan_name: str | None = None
    rate_plan_code: str | None = None
    package_inclusions: list["RatePlanInclusionRead"] = Field(default_factory=list)


class AvailabilityResponse(BaseModel):
    outlet_id: int
    check_in_date: date
    check_out_date: date
    source: ReservationSource | None = None
    room_types: list[RoomTypeAvailability]


class PmsDashboard(BaseModel):
    outlet_id: int | None
    arrivals_today: int
    departures_today: int
    in_house: int
    total_rooms: int
    occupied_rooms: int
    occupancy_rate: float
    pending_reservations: int


class AssignRoomRequest(BaseModel):
    room_id: int


class MoveRoomRequest(BaseModel):
    room_id: int
    rate_delta: float | None = None
    notes: str | None = None


class StayModifierUpdate(BaseModel):
    early_check_in: bool | None = None
    late_check_out: bool | None = None
    day_use: bool | None = None
    check_out_date: date | None = None


class CaptureDepositRequest(BaseModel):
    notes: str | None = None


class RefundDepositRequest(BaseModel):
    amount: float | None = Field(default=None, gt=0)
    notes: str | None = None


class TapeChartSegment(BaseModel):
    kind: str  # reservation | block
    id: int
    start_date: date
    end_date: date
    label: str
    status: str | None = None
    block_type: RoomBlockType | None = None
    guest_name: str | None = None
    confirmation_number: str | None = None
    reservation_id: int | None = None


class TapeChartRoomRow(BaseModel):
    room_id: int
    room_number: str
    room_type_id: int
    room_type_name: str | None = None
    hk_status: str
    segments: list[TapeChartSegment] = Field(default_factory=list)


class TapeChartResponse(BaseModel):
    outlet_id: int
    from_date: date
    to_date: date
    rooms: list[TapeChartRoomRow]


class PickupDay(BaseModel):
    date: date
    total_rooms: int
    sold: int
    blocked: int
    available: int
    occupancy_percent: float
    arrivals: int
    departures: int


class PickupCalendarResponse(BaseModel):
    outlet_id: int
    from_date: date
    to_date: date
    total_rooms: int
    days: list[PickupDay]


class RateInventoryRoomType(BaseModel):
    room_type_id: int
    room_type_name: str
    total_rooms: int


class RateInventoryCell(BaseModel):
    date: date
    room_type_id: int
    room_type_name: str
    total_rooms: int
    sold: int
    blocked: int
    available: int
    rate: float
    rate_plan_id: int | None = None
    rate_plan_name: str | None = None
    rate_plan_code: str | None = None
    stop_sell: bool = False
    rate_overridden: bool = False
    cta: bool = False
    ctd: bool = False
    min_stay: int | None = None
    max_stay: int | None = None


class RateInventoryOverrideUpsert(BaseModel):
    outlet_id: int
    room_type_id: int
    date: date
    stop_sell: bool | None = None
    rate: float | None = Field(default=None, ge=0)
    clear_rate: bool = False
    cta: bool | None = None
    ctd: bool | None = None
    min_stay: int | None = Field(default=None, ge=0, le=30)
    max_stay: int | None = Field(default=None, ge=0, le=90)
    clear_min_stay: bool = False
    clear_max_stay: bool = False

    @model_validator(mode="after")
    def validate_stay_bounds(self):
        if (
            self.min_stay is not None
            and self.max_stay is not None
            and self.min_stay > 0
            and self.max_stay > 0
            and self.min_stay > self.max_stay
        ):
            raise ValueError("min_stay cannot exceed max_stay")
        return self


class FolioEntryVoidRequest(BaseModel):
    reason: str | None = Field(default=None, max_length=255)


class SpecialRequestFulfillResponse(MessageResponse):
    reservation_id: int
    fulfilled_count: int


class RateInventoryCalendarResponse(BaseModel):
    outlet_id: int
    from_date: date
    to_date: date
    room_types: list[RateInventoryRoomType]
    dates: list[date]
    cells: list[RateInventoryCell]


class RoomBlockCreate(BaseModel):
    outlet_id: int
    room_id: int
    start_date: date
    end_date: date
    block_type: RoomBlockType
    reason: str | None = None

    @field_validator("end_date")
    @classmethod
    def end_after_start(cls, v: date, info) -> date:
        start = info.data.get("start_date")
        if start and v <= start:
            raise ValueError("end_date must be after start_date")
        return v


class RoomBlockUpdate(BaseModel):
    start_date: date | None = None
    end_date: date | None = None
    block_type: RoomBlockType | None = None
    reason: str | None = None
    is_active: bool | None = None


class RoomBlockRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    room_id: int
    room_number: str | None = None
    start_date: date
    end_date: date
    block_type: RoomBlockType
    reason: str | None
    created_by: int | None


class ReservationGroupCreate(BaseModel):
    outlet_id: int
    name: str = Field(min_length=1, max_length=255)
    group_code: str | None = Field(default=None, max_length=32)
    company_name: str | None = Field(default=None, max_length=255)
    shared_deposit: float = Field(default=0, ge=0)
    notes: str | None = None
    customer_id: int | None = None
    billing_instructions: dict[str, str] | None = None


class GroupBillingInstructions(BaseModel):
    room_rate: str = "room"
    pos: str = "master"
    minibar: str = "room"
    spa: str = "master"
    banquet: str = "master"
    other: str = "master"


class ReservationGroupUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=255)
    company_name: str | None = Field(default=None, max_length=255)
    notes: str | None = None
    billing_instructions: dict[str, str] | None = None


class GroupFolioSweepRequest(BaseModel):
    reservation_ids: list[int] | None = None
    include_zero: bool = False


class GroupFolioCloseRequest(BaseModel):
    force_settle: bool = False


class GroupRoomingStay(BaseModel):
    guest_name: str = Field(min_length=1, max_length=255)
    guest_mobile: str = Field(min_length=6, max_length=32)
    guest_email: str | None = None
    room_type_id: int
    room_id: int | None = None
    check_in_date: date
    check_out_date: date
    adults: int = Field(default=1, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    rate_plan_id: int | None = None
    rate_per_night: float = Field(default=0, ge=0)
    notes: str | None = None

    @field_validator("check_out_date")
    @classmethod
    def checkout_after_checkin(cls, v: date, info) -> date:
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("check_out_date must be after check_in_date")
        return v


class GroupRoomingCreate(BaseModel):
    stays: list[GroupRoomingStay] = Field(min_length=1)
    auto_confirm: bool = True


class ReservationGroupRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    group_code: str
    name: str
    company_name: str | None = None
    shared_deposit: float
    notes: str | None
    customer_id: int | None
    created_by: int | None
    billing_instructions: GroupBillingInstructions = Field(default_factory=GroupBillingInstructions)
    reservations: list[ReservationRead] = Field(default_factory=list)
    master_folio: FolioRead | None = None
    room_folios_balance: float = 0
    combined_balance: float = 0


class NightAuditRunRequest(BaseModel):
    outlet_id: int
    business_date: date
    force: bool = False


class NightAuditLogRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    business_date: date
    ran_at: datetime
    rooms_posted: int
    no_shows_marked: int
    arrivals_expected: int
    summary_json: str
    created_by: int | None


class NightAuditResult(BaseModel):
    log: NightAuditLogRead
    rooms_posted: int
    no_shows_marked: int
    arrivals_expected: int
    daily_tasks_created: int = 0


class TenderMixRead(BaseModel):
    cash: float = 0
    card: float = 0
    upi: float = 0
    other: float = 0
    total: float = 0


class AccountsDayBookNightAuditInfo(BaseModel):
    ran: bool = False
    ran_at: datetime | None = None
    rooms_posted: int = 0
    no_shows_marked: int = 0
    arrivals_expected: int = 0


class AccountsGstRateBucket(BaseModel):
    rate_percent: float
    taxable: float = 0
    tax: float = 0


class AccountsDayBookLine(BaseModel):
    business_date: date
    outlet_id: int
    source: str
    voucher_type: str
    entry_type: str
    reference: str | None = None
    guest_or_party: str | None = None
    description: str | None = None
    account_hint: str
    debit: float = 0
    credit: float = 0
    amount_signed: float = 0
    taxable_amount: float | None = None
    tax_amount: float | None = None
    tax_rate_percent: float | None = None
    tax_label: str | None = None
    tender: str | None = None
    posted_at: datetime | None = None
    external_id: str


class AccountsDayBookSummary(BaseModel):
    folio_charges_ex_tax: float = 0
    folio_tax: float = 0
    folio_payments: float = 0
    folio_refunds: float = 0
    pos_taxable: float = 0
    pos_gst: float = 0
    pos_payments_excl_room_charge: float = 0
    by_entry_type: dict[str, float] = Field(default_factory=dict)
    by_gst_rate: list[AccountsGstRateBucket] = Field(default_factory=list)
    tender_mix: TenderMixRead = Field(default_factory=TenderMixRead)


class AccountsDayBookRead(BaseModel):
    outlet_id: int
    business_date: date
    tax_label: str = "GST"
    tax_percent_default: float = 12.0
    night_audit: AccountsDayBookNightAuditInfo = Field(
        default_factory=AccountsDayBookNightAuditInfo
    )
    summary: AccountsDayBookSummary = Field(default_factory=AccountsDayBookSummary)
    lines: list[AccountsDayBookLine] = Field(default_factory=list)


class CashierShiftOpenRequest(BaseModel):
    outlet_id: int
    opening_float: float = Field(default=0, ge=0)
    notes: str | None = Field(default=None, max_length=500)


class CashierShiftCloseRequest(BaseModel):
    declared_cash: float = Field(ge=0)
    notes: str | None = Field(default=None, max_length=500)


class CashierShiftRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    outlet_id: int
    status: str
    opened_at: datetime
    closed_at: datetime | None
    opened_by: int | None
    closed_by: int | None
    opening_float: float
    declared_cash: float | None = None
    expected_cash: float | None = None
    cash_variance: float | None = None
    tender_cash: float = 0
    tender_card: float = 0
    tender_upi: float = 0
    tender_other: float = 0
    payments_total: float = 0
    refunds_total: float = 0
    notes: str | None = None
    # Live (or frozen) tender mix for the shift window
    tender_mix: TenderMixRead = Field(default_factory=TenderMixRead)
    expected_cash_live: float = 0


class PmsReportsSummary(BaseModel):
    outlet_id: int
    from_date: date
    to_date: date
    room_nights_sold: int
    room_nights_available: int
    occupancy: float
    adr: float
    revpar: float
    arrivals: int
    departures: int
    cancels: int
    no_shows: int
    room_revenue: float
    payments_collected: float = 0
    tender_mix: TenderMixRead = Field(default_factory=TenderMixRead)


class GuestStayHistoryRead(BaseModel):
    customer_id: int | None = None
    guest_mobile: str | None = None
    stays: list[ReservationRead] = Field(default_factory=list)


class InHouseGuestRead(BaseModel):
    reservation_id: int
    confirmation_number: str
    guest_name: str
    room_number: str | None = None
    room_type_name: str | None = None
    outlet_id: int


class PostToRoomRequest(BaseModel):
    bill_id: int
    reservation_id: int
    amount: float | None = Field(default=None, gt=0)
    description: str | None = Field(default=None, max_length=255)
    target: str = Field(default="auto", max_length=16)  # room | master | auto


class PostToRoomResponse(BaseModel):
    reservation_id: int
    bill_id: int
    amount: float
    folio: FolioRead


class RatePlanCreate(BaseModel):
    room_type_id: int
    name: str = Field(min_length=1, max_length=100)
    code: str = Field(min_length=1, max_length=32)
    rate_per_night: float = Field(gt=0)
    is_default: bool = False
    source: ReservationSource | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    min_nights: int = Field(default=1, ge=1, le=30)
    description: str | None = Field(default=None, max_length=255)
    cancellation_fee_percent: float = Field(default=0, ge=0, le=100)
    no_show_fee_percent: float = Field(default=0, ge=0, le=100)
    default_guarantee: GuaranteeType = GuaranteeType.NONE
    allows_day_use: bool = True
    day_use_rate_percent: float = Field(default=50, ge=1, le=100)
    included_adults: int = Field(default=2, ge=1, le=20)
    included_children: int = Field(default=0, ge=0, le=20)
    extra_adult_rate: float = Field(default=0, ge=0)
    extra_child_rate: float = Field(default=0, ge=0)
    inclusions: list["RatePlanInclusionCreate"] = Field(default_factory=list)

    @field_validator("valid_to")
    @classmethod
    def valid_to_after_from(cls, v: date | None, info) -> date | None:
        valid_from = info.data.get("valid_from")
        if v and valid_from and v < valid_from:
            raise ValueError("valid_to must be on or after valid_from")
        return v


class RatePlanUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=100)
    rate_per_night: float | None = Field(default=None, gt=0)
    is_default: bool | None = None
    source: ReservationSource | None = None
    valid_from: date | None = None
    valid_to: date | None = None
    min_nights: int | None = Field(default=None, ge=1, le=30)
    description: str | None = Field(default=None, max_length=255)
    cancellation_fee_percent: float | None = Field(default=None, ge=0, le=100)
    no_show_fee_percent: float | None = Field(default=None, ge=0, le=100)
    default_guarantee: GuaranteeType | None = None
    allows_day_use: bool | None = None
    day_use_rate_percent: float | None = Field(default=None, ge=1, le=100)
    included_adults: int | None = Field(default=None, ge=1, le=20)
    included_children: int | None = Field(default=None, ge=0, le=20)
    extra_adult_rate: float | None = Field(default=None, ge=0)
    extra_child_rate: float | None = Field(default=None, ge=0)
    is_active: bool | None = None
    inclusions: list["RatePlanInclusionCreate"] | None = None


class RatePlanRead(ORMSchema, TimestampSchema):
    id: int
    tenant_id: int
    brand_id: int | None
    room_type_id: int
    room_type_name: str | None = None
    name: str
    code: str
    rate_per_night: float
    effective_rate_per_night: float = 0
    is_default: bool
    source: ReservationSource | None
    valid_from: date | None
    valid_to: date | None
    min_nights: int
    description: str | None
    cancellation_fee_percent: float = 0
    no_show_fee_percent: float = 0
    default_guarantee: GuaranteeType = GuaranteeType.NONE
    allows_day_use: bool = True
    day_use_rate_percent: float = 50
    included_adults: int = 2
    included_children: int = 0
    extra_adult_rate: float = 0
    extra_child_rate: float = 0
    is_active: bool
    inclusions: list["RatePlanInclusionRead"] = Field(default_factory=list)


class RatePlanInclusionCreate(BaseModel):
    inclusion_type: InclusionType
    name: str = Field(min_length=1, max_length=128)
    price_per_night: float = Field(default=0, ge=0)
    is_included: bool = True
    credit_amount: float = Field(default=0, ge=0)
    credit_scope: CreditScope = CreditScope.STAY
    qty_per_stay: int = Field(default=0, ge=0, le=999)
    qty_per_night: int = Field(default=0, ge=0, le=99)


class RatePlanInclusionRead(ORMSchema, TimestampSchema):
    id: int
    rate_plan_id: int
    inclusion_type: InclusionType
    name: str
    price_per_night: float
    is_included: bool
    credit_amount: float = 0
    credit_scope: CreditScope = CreditScope.STAY
    qty_per_stay: int = 0
    qty_per_night: int = 0


class PackageEntitlementRead(ORMSchema, TimestampSchema):
    id: int
    reservation_id: int
    source_inclusion_id: int | None = None
    inclusion_type: InclusionType
    name: str
    credit_total: float
    credit_used: float
    credit_remaining: float = 0
    qty_total: int
    qty_used: int
    qty_remaining: int = 0
    claimed_today: int = 0
    can_claim: bool = False


class PackageEntitlementClaimRequest(BaseModel):
    qty: int = Field(default=1, ge=1, le=20)
    notes: str | None = Field(default=None, max_length=255)


class PackageEntitlementClaimRead(BaseModel):
    id: int
    entitlement_id: int
    reservation_id: int
    claim_date: date
    qty: int
    channel: str
    claimed_by: int | None = None
    notes: str | None = None
    message: str
    entitlement: PackageEntitlementRead


class PublicRoomHubClaimRequest(BaseModel):
    outlet_id: int
    room_number: str = Field(min_length=1, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    entitlement_id: int
    qty: int = Field(default=1, ge=1, le=20)
    notes: str | None = Field(default=None, max_length=255)


class PublicRoomTypeRead(BaseModel):
    id: int
    outlet_id: int
    name: str
    description: str | None = None
    base_rate: float
    max_occupancy: int
    amenities: str | None = None
    amenities_list: list[str] = Field(default_factory=list)
    image_url: str | None = None
    gallery_urls: list[str] = Field(default_factory=list)
    bed_type: str | None = None
    room_size_sqft: int | None = None


class PublicAddonRead(BaseModel):
    code: str
    name: str
    description: str
    price: float
    unit: str
    max_quantity: int | None = None


class PublicAddonSelection(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    quantity: int = Field(default=1, ge=0, le=20)


class PublicAddonLineRead(BaseModel):
    code: str
    name: str
    unit: str
    unit_price: float
    quantity: int
    nights: int
    total: float
    description: str


class PublicReservationCreate(BaseModel):
    outlet_id: int
    room_type_id: int
    check_in_date: date
    check_out_date: date
    guest_name: str = Field(min_length=1, max_length=255)
    guest_mobile: str = Field(min_length=6, max_length=32)
    guest_email: str | None = None
    adults: int = Field(default=2, ge=1, le=20)
    children: int = Field(default=0, ge=0, le=20)
    notes: str | None = None
    card_last4: str | None = Field(default=None, min_length=4, max_length=4, pattern=r"^\d{4}$")
    payment_provider: str | None = Field(
        default=None,
        description="razorpay | phonepe | cashfree | ccavenue | paytm",
    )
    hold_amount: float | None = Field(default=None, gt=0)
    hold_days: int = Field(default=7, ge=1, le=30)
    addons: list[PublicAddonSelection] = Field(default_factory=list)

    @field_validator("check_out_date")
    @classmethod
    def checkout_after_checkin(cls, v: date, info) -> date:
        check_in = info.data.get("check_in_date")
        if check_in and v <= check_in:
            raise ValueError("check_out_date must be after check_in_date")
        return v


class PublicReservationResponse(BaseModel):
    reservation_id: int
    confirmation_number: str
    message: str
    status: ReservationStatus
    total_amount: float
    nights: int
    deposit_status: str | None = None
    deposit_amount: float | None = None
    payment_hold_ref: str | None = None
    card_last4: str | None = None
    hold_expires_at: datetime | None = None
    guarantee_type: str | None = None
    addons: list[PublicAddonLineRead] = Field(default_factory=list)
    addons_total: float = 0
    room_total: float | None = None


class PublicReservationLookupRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)


class PublicReservationStatus(BaseModel):
    confirmation_number: str
    guest_name: str
    guest_mobile: str
    guest_email: str | None = None
    outlet_id: int
    outlet_name: str | None = None
    room_type_name: str | None = None
    room_number: str | None = None
    check_in_date: date
    check_out_date: date
    nights: int
    adults: int
    children: int
    status: ReservationStatus
    total_amount: float
    rate_per_night: float
    rate_plan_name: str | None = None
    deposit_status: str | None = None
    deposit_amount: float | None = None
    payment_hold_ref: str | None = None
    card_last4: str | None = None
    hold_expires_at: datetime | None = None
    guarantee_type: str | None = None
    can_place_hold: bool = False
    can_cancel: bool = False
    can_modify_stay: bool = False
    early_check_in: bool = False
    late_check_out: bool = False
    day_use: bool = False
    can_request_early_check_in: bool = False
    can_request_late_check_out: bool = False
    can_add_special_request: bool = False
    special_requests: list[str] = []
    can_submit_feedback: bool = False
    feedback_rating: int | None = None
    feedback_comment: str | None = None
    folio_number: str | None = None
    folio_balance: float | None = None
    has_folio: bool = False
    can_email_folio: bool = False
    addons: list[PublicAddonLineRead] = Field(default_factory=list)
    addons_total: float = 0
    can_pre_check_in: bool = False
    pre_check_in_status: str = "none"
    pre_check_in_at: datetime | None = None
    guest_id_document: str | None = None
    guest_id_document_type: str | None = None
    estimated_arrival_time: str | None = None
    pre_check_in_notes: str | None = None
    message: str


class PublicPreCheckInRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    guest_name: str | None = Field(default=None, min_length=1, max_length=255)
    guest_email: str | None = Field(default=None, max_length=255)
    guest_id_document_type: str = Field(min_length=2, max_length=32)
    guest_id_document: str = Field(min_length=3, max_length=64)
    estimated_arrival_time: str | None = Field(default=None, max_length=16)
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)
    early_check_in: bool | None = None
    notes: str | None = Field(default=None, max_length=500)


class PreCheckInReviewRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=255)


class PublicCardHoldCreate(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    card_last4: str = Field(min_length=4, max_length=4, pattern=r"^\d{4}$")
    hold_amount: float | None = Field(default=None, gt=0)
    hold_days: int = Field(default=7, ge=1, le=30)


class PublicCancelRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    reason: str | None = Field(default=None, max_length=255)


class PublicModifyStayRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    check_in_date: date | None = None
    check_out_date: date | None = None
    adults: int | None = Field(default=None, ge=1, le=20)
    children: int | None = Field(default=None, ge=0, le=20)
    note: str | None = Field(default=None, max_length=255)


class PublicStayModifiersRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    early_check_in: bool | None = None
    late_check_out: bool | None = None
    note: str | None = Field(default=None, max_length=255)


class PublicSpecialRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    request: str = Field(min_length=3, max_length=500)


class PublicStayFeedbackRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    rating: int = Field(ge=1, le=5)
    comment: str | None = Field(default=None, max_length=500)


class PublicFolioEmailRequest(BaseModel):
    confirmation_number: str = Field(min_length=3, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    to_email: str | None = Field(default=None, max_length=255)
    note: str | None = Field(default=None, max_length=500)


class ReservationConfirmRequest(BaseModel):
    send_sms: bool = False
    send_email: bool = False
    send_whatsapp: bool = False


class PmsNotificationKind(str, enum.Enum):
    REQUEST_RECEIVED = "request_received"
    CONFIRMATION = "confirmation"
    REMINDER = "reminder"
    THANK_YOU = "thank_you"
    CANCELLATION = "cancellation"


class PmsNotificationRequest(BaseModel):
    kind: PmsNotificationKind = PmsNotificationKind.CONFIRMATION
    send_sms: bool = True
    send_email: bool = True
    send_whatsapp: bool = True


class PmsNotificationResponse(MessageResponse):
    reservation_id: int
    sent_channels: list[str]
    message_preview: str


class PmsReminderBatchResult(BaseModel):
    message: str
    reminders_sent: int
    tenants_processed: int
    reservations_checked: int


class GuestServiceRequestCategory(str, enum.Enum):
    TOWELS = "towels"
    BEDSHEETS = "bedsheets"
    TOILETRIES = "toiletries"
    HOUSEKEEPING = "housekeeping"
    WIFI_HELP = "wifi_help"
    MAINTENANCE_ISSUE = "maintenance_issue"
    OTHER = "other"


class GuestServiceRequestStatus(str, enum.Enum):
    OPEN = "open"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"


class PublicRoomHubWifi(BaseModel):
    ssid: str = ""
    password: str = ""
    notes: str = ""


class PublicServiceCatalogItem(BaseModel):
    code: GuestServiceRequestCategory
    label: str
    description: str


class PublicRoomHubResponse(BaseModel):
    outlet_id: int
    outlet_name: str
    room_id: int
    room_number: str
    floor: str | None = None
    guest_name: str | None = None
    reservation_id: int | None = None
    is_checked_in: bool = False
    # Unlocked when guest_mobile matches the checked-in stay
    stay_unlocked: bool = False
    confirmation_number: str | None = None
    check_in_date: date | None = None
    check_out_date: date | None = None
    nights: int | None = None
    room_type_name: str | None = None
    folio_balance: float | None = None
    folio_number: str | None = None
    has_folio: bool = False
    status: str | None = None
    wifi: PublicRoomHubWifi = Field(default_factory=PublicRoomHubWifi)
    service_catalog: list[PublicServiceCatalogItem] = Field(default_factory=list)
    menu_url_path: str
    spa_url_path: str | None = None
    booking_url_path: str | None = None
    package_entitlements: list[PackageEntitlementRead] = Field(default_factory=list)
    can_express_checkout: bool = False
    express_checkout_status: str = "none"
    express_checkout_at: datetime | None = None
    express_checkout_notes: str | None = None
    estimated_departure_time: str | None = None
    balance_due: bool = False
    upsell_catalog: list[PublicAddonRead] = Field(default_factory=list)
    purchased_addons: list[PublicAddonLineRead] = Field(default_factory=list)


class PublicRoomHubUpsellRequest(BaseModel):
    outlet_id: int
    room_number: str = Field(min_length=1, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    code: str = Field(min_length=1, max_length=32)
    quantity: int = Field(default=1, ge=1, le=20)


class PublicExpressCheckoutRequest(BaseModel):
    outlet_id: int
    room_number: str = Field(min_length=1, max_length=32)
    guest_mobile: str = Field(min_length=6, max_length=32)
    notes: str | None = Field(default=None, max_length=500)
    estimated_departure_time: str | None = Field(default=None, max_length=16)


class ExpressCheckoutCompleteRequest(BaseModel):
    force_settle: bool = False
    notes: str | None = Field(default=None, max_length=255)


class PublicServiceRequestCreate(BaseModel):
    outlet_id: int
    room_number: str = Field(min_length=1, max_length=32)
    category: GuestServiceRequestCategory
    notes: str | None = Field(default=None, max_length=500)
    guest_mobile: str | None = Field(default=None, max_length=32)


class PublicServiceRequestResponse(BaseModel):
    id: int
    room_number: str
    category: GuestServiceRequestCategory
    status: GuestServiceRequestStatus
    message: str


class GuestServiceRequestRead(ORMSchema, TimestampSchema):
    id: int
    outlet_id: int
    room_id: int
    room_number: str
    reservation_id: int | None = None
    guest_name: str | None = None
    category: GuestServiceRequestCategory
    notes: str | None = None
    guest_mobile: str | None = None
    status: GuestServiceRequestStatus
    linked_task_id: int | None = None
    linked_ticket_id: int | None = None
    fulfilled_at: datetime | None = None
    fulfilled_by: int | None = None
    staff_reply: str | None = None
    guest_notified_at: datetime | None = None


class GuestServiceRequestFulfillRequest(BaseModel):
    staff_reply: str | None = Field(default=None, max_length=500)
    notify_guest: bool = True


class GuestServiceRequestFulfillResponse(MessageResponse):
    id: int
    status: GuestServiceRequestStatus
    notified: bool = False
    staff_reply: str | None = None


class PublicGuestServiceRequestRead(BaseModel):
    id: int
    room_number: str
    category: GuestServiceRequestCategory
    category_label: str
    notes: str | None = None
    status: GuestServiceRequestStatus
    staff_reply: str | None = None
    created_at: datetime | None = None
    fulfilled_at: datetime | None = None
    guest_notified_at: datetime | None = None
