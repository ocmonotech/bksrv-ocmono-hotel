from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class ReservationStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    CHECKED_IN = "checked_in"
    CHECKED_OUT = "checked_out"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class PreCheckInStatus(str, enum.Enum):
    NONE = "none"
    SUBMITTED = "submitted"
    REVIEWED = "reviewed"


class ExpressCheckoutStatus(str, enum.Enum):
    NONE = "none"
    SUBMITTED = "submitted"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class ReservationSource(str, enum.Enum):
    DIRECT = "direct"
    WALK_IN = "walk_in"
    PHONE = "phone"
    EMAIL = "email"
    CORPORATE = "corporate"
    OTA_BOOKING_COM = "ota_booking_com"
    OTA_MMT = "ota_mmt"
    OTA_EXPEDIA = "ota_expedia"


class FolioEntryType(str, enum.Enum):
    ROOM_CHARGE = "room_charge"
    TAX = "tax"
    DEPOSIT = "deposit"
    PAYMENT = "payment"
    POS_CHARGE = "pos_charge"
    SPA_CHARGE = "spa_charge"
    BANQUET_CHARGE = "banquet_charge"
    ADJUSTMENT = "adjustment"
    REFUND = "refund"
    PACKAGE_CREDIT = "package_credit"
    MINIBAR_CHARGE = "minibar_charge"


class FolioStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class InclusionType(str, enum.Enum):
    BREAKFAST = "breakfast"
    LUNCH = "lunch"
    DINNER = "dinner"
    CAFE = "cafe"
    SPA = "spa"
    PARKING = "parking"
    OTHER = "other"


class CreditScope(str, enum.Enum):
    STAY = "stay"
    NIGHT = "night"


class RoomBlockType(str, enum.Enum):
    MAINTENANCE = "maintenance"
    HOLD = "hold"
    VIP = "vip"
    OTHER = "other"


class GuaranteeType(str, enum.Enum):
    NONE = "none"
    DEPOSIT = "deposit"
    CARD_HOLD = "card_hold"


class PaymentTender(str, enum.Enum):
    CASH = "cash"
    CARD = "card"
    UPI = "upi"
    OTHER = "other"
    POINTS = "points"


class DepositStatus(str, enum.Enum):
    PENDING = "pending"
    CAPTURED = "captured"
    REFUNDED = "refunded"
    FORFEITED = "forfeited"
    HELD = "held"


class CashierShiftStatus(str, enum.Enum):
    OPEN = "open"
    CLOSED = "closed"


class CityLedgerStatus(str, enum.Enum):
    OPEN = "open"
    PARTIAL = "partial"
    SETTLED = "settled"
    WRITTEN_OFF = "written_off"


class RatePlan(Base, BaseMixin, TenantBrandMixin):
    """Nightly rate rule for a room type — seasonal, channel-specific, or default rack."""

    __tablename__ = "rate_plans"
    __table_args__ = (
        UniqueConstraint("tenant_id", "code", name="uq_rate_plan_tenant_code"),
    )

    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    rate_per_night: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    source: Mapped[Optional[ReservationSource]] = mapped_column(Enum(ReservationSource), nullable=True)
    valid_from: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    valid_to: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    min_nights: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    cancellation_fee_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    no_show_fee_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    default_guarantee: Mapped[GuaranteeType] = mapped_column(
        Enum(GuaranteeType), default=GuaranteeType.NONE, nullable=False
    )
    allows_day_use: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    day_use_rate_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=50, nullable=False)
    included_adults: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    included_children: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    extra_adult_rate: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    extra_child_rate: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    inclusions: Mapped[list["RatePlanInclusion"]] = relationship(
        back_populates="rate_plan",
        cascade="all, delete-orphan",
    )


class RatePlanInclusion(Base, BaseMixin, TenantBrandMixin):
    """Package add-on bundled with a rate plan — breakfast, spa access, café credit, etc."""

    __tablename__ = "rate_plan_inclusions"

    rate_plan_id: Mapped[int] = mapped_column(
        ForeignKey("rate_plans.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    inclusion_type: Mapped[InclusionType] = mapped_column(Enum(InclusionType), nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    price_per_night: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    is_included: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    credit_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    credit_scope: Mapped[CreditScope] = mapped_column(
        Enum(
            CreditScope,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=16,
        ),
        default=CreditScope.STAY,
        nullable=False,
    )
    qty_per_stay: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty_per_night: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    rate_plan: Mapped["RatePlan"] = relationship(back_populates="inclusions")


class ReservationPackageEntitlement(Base, BaseMixin, TenantBrandMixin):
    """Snapshotted package benefit for a stay — redeemable ₹ credit and/or quantity."""

    __tablename__ = "reservation_package_entitlements"

    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("guest_reservations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    source_inclusion_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rate_plan_inclusions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    inclusion_type: Mapped[InclusionType] = mapped_column(
        Enum(InclusionType, native_enum=False, length=32),
        nullable=False,
    )
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    credit_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    credit_used: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    qty_total: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    qty_used: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    reservation: Mapped["GuestReservation"] = relationship(back_populates="package_entitlements")


class PackageEntitlementClaimChannel(str, enum.Enum):
    STAFF = "staff"
    GUEST_QR = "guest_qr"


class PackageEntitlementClaim(Base, BaseMixin, TenantBrandMixin):
    """Audit row when a qty-based package cover is claimed (breakfast, café, etc.)."""

    __tablename__ = "package_entitlement_claims"

    entitlement_id: Mapped[int] = mapped_column(
        ForeignKey("reservation_package_entitlements.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("guest_reservations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    claim_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    qty: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    channel: Mapped[str] = mapped_column(String(16), default=PackageEntitlementClaimChannel.STAFF.value, nullable=False)
    claimed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)


class GuestReservation(Base, BaseMixin, TenantBrandMixin):
    """Lodging reservation — distinct from restaurant table bookings."""

    __tablename__ = "guest_reservations"
    __table_args__ = (
        UniqueConstraint("tenant_id", "confirmation_number", name="uq_guest_res_tenant_confirmation"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    confirmation_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_mobile: Mapped[str] = mapped_column(String(32), nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True, nullable=False)
    room_id: Mapped[Optional[int]] = mapped_column(ForeignKey("hotel_rooms.id"), nullable=True, index=True)
    check_in_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    check_out_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    adults: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    children: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    status: Mapped[ReservationStatus] = mapped_column(
        Enum(ReservationStatus), default=ReservationStatus.PENDING, index=True
    )
    source: Mapped[ReservationSource] = mapped_column(
        Enum(ReservationSource), default=ReservationSource.DIRECT
    )
    rate_plan_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("rate_plans.id"),
        nullable=True,
        index=True,
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reservation_groups.id"),
        nullable=True,
        index=True,
    )
    guest_id_document: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    guest_id_document_type: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    estimated_arrival_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    pre_check_in_status: Mapped[str] = mapped_column(
        String(16), default=PreCheckInStatus.NONE.value, nullable=False
    )
    pre_check_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    pre_check_in_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    pre_check_in_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    express_checkout_status: Mapped[str] = mapped_column(
        String(16), default=ExpressCheckoutStatus.NONE.value, nullable=False
    )
    express_checkout_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    express_checkout_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_departure_time: Mapped[Optional[str]] = mapped_column(String(16), nullable=True)
    express_checkout_reviewed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    early_check_in: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    late_check_out: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    day_use: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    guarantee_type: Mapped[GuaranteeType] = mapped_column(
        Enum(GuaranteeType), default=GuaranteeType.NONE, nullable=False
    )
    deposit_status: Mapped[DepositStatus] = mapped_column(
        Enum(DepositStatus), default=DepositStatus.PENDING, nullable=False
    )
    rate_per_night: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    deposit_amount: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    payment_provider: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    payment_hold_ref: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    payment_auth_code: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    card_last4: Mapped[Optional[str]] = mapped_column(String(4), nullable=True)
    hold_expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    addons_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    checked_in_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checked_out_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    folio: Mapped[Optional["GuestFolio"]] = relationship(back_populates="reservation", uselist=False)
    group: Mapped[Optional["ReservationGroup"]] = relationship(back_populates="reservations")
    package_entitlements: Mapped[list["ReservationPackageEntitlement"]] = relationship(
        back_populates="reservation",
        cascade="all, delete-orphan",
    )


class RoomBlock(Base, BaseMixin, TenantBrandMixin):
    """Blocks a room from sale for maintenance, holds, VIP, etc."""

    __tablename__ = "room_blocks"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("hotel_rooms.id"), index=True, nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    end_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    block_type: Mapped[RoomBlockType] = mapped_column(Enum(RoomBlockType), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class ReservationGroup(Base, BaseMixin, TenantBrandMixin):
    """Groups multiple room stays under one booking (group/rooming list)."""

    __tablename__ = "reservation_groups"
    __table_args__ = (
        UniqueConstraint("tenant_id", "group_code", name="uq_reservation_group_tenant_code"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    group_code: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    company_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    billing_instructions_json: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    shared_deposit: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    reservations: Mapped[list["GuestReservation"]] = relationship(back_populates="group")
    master_folio: Mapped[Optional["GuestFolio"]] = relationship(
        back_populates="group",
        uselist=False,
    )


class NightAuditLog(Base, BaseMixin, TenantBrandMixin):
    """Record of a night-audit run for an outlet business date."""

    __tablename__ = "night_audit_logs"
    __table_args__ = (
        UniqueConstraint(
            "tenant_id",
            "outlet_id",
            "business_date",
            name="uq_night_audit_tenant_outlet_date",
        ),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    business_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    ran_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    rooms_posted: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    no_shows_marked: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    arrivals_expected: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, default="{}", nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class CashierShift(Base, BaseMixin, TenantBrandMixin):
    """Front-desk cash drawer shift — open float, tender totals, close variance."""

    __tablename__ = "cashier_shifts"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    status: Mapped[CashierShiftStatus] = mapped_column(
        Enum(CashierShiftStatus, native_enum=False, length=16),
        default=CashierShiftStatus.OPEN,
        index=True,
        nullable=False,
    )
    opened_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    opened_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    closed_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    opening_float: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    declared_cash: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    expected_cash: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    cash_variance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    tender_cash: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tender_card: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tender_upi: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    tender_other: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    payments_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    refunds_total: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)


class CityLedgerEntry(Base, BaseMixin, TenantBrandMixin):
    """Accounts-receivable posting when folio balance is transferred off the guest bill."""

    __tablename__ = "city_ledger_entries"
    __table_args__ = (
        UniqueConstraint("tenant_id", "reference", name="uq_city_ledger_tenant_reference"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("guest_reservations.id"), nullable=True, index=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reservation_groups.id"), nullable=True, index=True
    )
    folio_id: Mapped[Optional[int]] = mapped_column(ForeignKey("guest_folios.id"), nullable=True, index=True)
    reference: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    original_amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    status: Mapped[CityLedgerStatus] = mapped_column(
        Enum(CityLedgerStatus, native_enum=False, length=16),
        default=CityLedgerStatus.OPEN,
        index=True,
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class GuestFolio(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "guest_folios"
    __table_args__ = (
        UniqueConstraint("tenant_id", "folio_number", name="uq_guest_folio_tenant_number"),
    )

    # Room folio (one per reservation) OR group master folio (one per group).
    reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("guest_reservations.id"), unique=True, nullable=True
    )
    group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("reservation_groups.id"), unique=True, nullable=True, index=True
    )
    folio_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    status: Mapped[FolioStatus] = mapped_column(Enum(FolioStatus), default=FolioStatus.OPEN)
    balance: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)

    reservation: Mapped[Optional["GuestReservation"]] = relationship(back_populates="folio")
    group: Mapped[Optional["ReservationGroup"]] = relationship(back_populates="master_folio")
    entries: Mapped[list["FolioEntry"]] = relationship(
        back_populates="folio",
        cascade="all, delete-orphan",
        order_by="FolioEntry.created_at",
    )


class FolioEntry(Base, BaseMixin):
    __tablename__ = "folio_entries"

    folio_id: Mapped[int] = mapped_column(ForeignKey("guest_folios.id"), index=True, nullable=False)
    entry_type: Mapped[FolioEntryType] = mapped_column(Enum(FolioEntryType), nullable=False)
    description: Mapped[str] = mapped_column(String(255), nullable=False)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    pos_order_id: Mapped[Optional[int]] = mapped_column(ForeignKey("pos_orders.id"), nullable=True)
    spa_booking_id: Mapped[Optional[int]] = mapped_column(ForeignKey("spa_bookings.id"), nullable=True, index=True)
    banquet_booking_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("banquet_bookings.id"), nullable=True, index=True
    )
    posted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    folio: Mapped["GuestFolio"] = relationship(back_populates="entries")


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


class GuestServiceRequest(Base, BaseMixin, TenantBrandMixin):
    """In-room guest service request from room QR hub."""

    __tablename__ = "guest_service_requests"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("hotel_rooms.id"), index=True, nullable=False)
    room_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("guest_reservations.id"), nullable=True, index=True
    )
    category: Mapped[GuestServiceRequestCategory] = mapped_column(
        Enum(
            GuestServiceRequestCategory,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=32,
        ),
        nullable=False,
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guest_mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[GuestServiceRequestStatus] = mapped_column(
        Enum(
            GuestServiceRequestStatus,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=16,
        ),
        default=GuestServiceRequestStatus.OPEN,
        nullable=False,
    )
    linked_task_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("housekeeping_tasks.id"), nullable=True, index=True
    )
    linked_ticket_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("maintenance_tickets.id"), nullable=True, index=True
    )
    fulfilled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    fulfilled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    staff_reply: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    guest_notified_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
