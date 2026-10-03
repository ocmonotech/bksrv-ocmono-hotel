from __future__ import annotations

import random
import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.housekeeping.models import HotelRoom, RoomStatus, RoomType, RoomTypeAmenity
from app.modules.housekeeping.room_catalog import parse_amenities, parse_gallery_urls
from app.modules.housekeeping.schemas import RoomStatusUpdate
from app.modules.pms.booking_addons import (
    DEFAULT_PUBLIC_ADDONS,
    addon_total,
    dump_addon_lines,
    parse_addon_lines,
    resolve_addon_lines,
)
from app.modules.housekeeping import service as hk_service
from app.modules.outlets.models import Outlet
from app.modules.users.models import User
from app.modules.pms.models import (
    CashierShift,
    CashierShiftStatus,
    CityLedgerEntry,
    CityLedgerStatus,
    CreditScope,
    DepositStatus,
    FolioEntry,
    FolioEntryType,
    FolioStatus,
    GuaranteeType,
    GuestFolio,
    GuestReservation,
    GuestServiceRequest,
    GuestServiceRequestCategory as GuestServiceRequestCategoryModel,
    GuestServiceRequestStatus as GuestServiceRequestStatusModel,
    InclusionType,
    NightAuditLog,
    PaymentTender,
    RatePlan,
    RatePlanInclusion,
    ReservationGroup,
    ReservationPackageEntitlement,
    PackageEntitlementClaim,
    PackageEntitlementClaimChannel,
    ReservationSource,
    ReservationStatus,
    PreCheckInStatus,
    ExpressCheckoutStatus,
    RoomBlock,
    RoomBlockType,
)
from app.modules.pms.schemas import (
    AssignRoomRequest,
    AvailabilityResponse,
    CancelReservationRequest,
    CaptureDepositRequest,
    CardHoldReleaseRequest,
    CardHoldRequest,
    CashierShiftCloseRequest,
    CashierShiftOpenRequest,
    CashierShiftRead,
    CheckInRequest,
    CheckOutRequest,
    CityLedgerRead,
    CityLedgerSettleRequest,
    CityLedgerTransferRequest,
    CityLedgerTransferResponse,
    CityLedgerWriteOffRequest,
    FolioChargeCreate,
    FolioEmailRequest,
    FolioEmailResponse,
    FolioEntryRead,
    FolioEntryVoidRequest,
    FolioPaymentCreate,
    FolioRead,
    FrontDeskReadinessItem,
    FrontDeskReadinessResponse,
    FolioTransferToMasterRequest,
    GroupBillingInstructions,
    GroupFolioCloseRequest,
    GroupFolioSweepRequest,
    GroupRoomingCreate,
    GuestStayHistoryRead,
    InHouseGuestRead,
    MoveRoomRequest,
    NightAuditLogRead,
    NightAuditResult,
    NightAuditRunRequest,
    AccountsDayBookLine,
    AccountsDayBookNightAuditInfo,
    AccountsDayBookRead,
    AccountsDayBookSummary,
    AccountsGstRateBucket,
    PackageEntitlementRead,
    PackageEntitlementClaimRequest,
    PackageEntitlementClaimRead,
    PublicRoomHubClaimRequest,
    PublicExpressCheckoutRequest,
    ExpressCheckoutCompleteRequest,
    PublicRoomHubUpsellRequest,
    PmsDashboard,
    PmsReportsSummary,
    PickupCalendarResponse,
    PickupDay,
    RateInventoryCalendarResponse,
    RateInventoryCell,
    RateInventoryOverrideUpsert,
    RateInventoryRoomType,
    SpecialRequestFulfillResponse,
    TenderMixRead,
    PostToRoomRequest,
    PostToRoomResponse,
    PublicAddonLineRead,
    PublicAddonRead,
    PublicReservationCreate,
    PublicReservationResponse,
    PublicReservationStatus,
    PublicPreCheckInRequest,
    PreCheckInReviewRequest,
    PublicCardHoldCreate,
    PublicCancelRequest,
    PublicFolioEmailRequest,
    PublicModifyStayRequest,
    PublicStayModifiersRequest,
    PublicSpecialRequest,
    PublicStayFeedbackRequest,
    PublicRoomHubResponse,
    PublicRoomHubWifi,
    PublicRoomTypeRead,
    PublicServiceCatalogItem,
    PublicServiceRequestCreate,
    PublicServiceRequestResponse,
    PublicGuestServiceRequestRead,
    GuestServiceRequestCategory,
    GuestServiceRequestFulfillRequest,
    GuestServiceRequestFulfillResponse,
    GuestServiceRequestRead,
    GuestServiceRequestStatus,
    PmsNotificationKind,
    PmsNotificationRequest,
    PmsNotificationResponse,
    PmsReminderBatchResult,
    RatePlanCreate,
    RatePlanInclusionCreate,
    RatePlanInclusionRead,
    RatePlanRead,
    RatePlanUpdate,
    RefundDepositRequest,
    ReservationCreate,
    ReservationDetailRead,
    ReservationGroupCreate,
    ReservationGroupRead,
    ReservationGroupUpdate,
    ReservationRead,
    ReservationUpdate,
    RoomBlockCreate,
    RoomBlockRead,
    RoomBlockUpdate,
    RoomTypeAvailability,
    StayModifierUpdate,
    TapeChartResponse,
    TapeChartRoomRow,
    TapeChartSegment,
    WalkInCreate,
)


ACTIVE_STATUSES = {
    ReservationStatus.PENDING,
    ReservationStatus.CONFIRMED,
    ReservationStatus.CHECKED_IN,
}

GUEST_SPECIAL_REQUEST_PREFIX = "Guest special request:"
GUEST_FEEDBACK_PREFIX = "Guest feedback:"


def _parse_guest_special_requests(notes: str | None) -> list[str]:
    if not notes:
        return []
    out: list[str] = []
    for raw in notes.splitlines():
        line = raw.strip()
        if line.lower().startswith(GUEST_SPECIAL_REQUEST_PREFIX.lower()):
            text = line[len(GUEST_SPECIAL_REQUEST_PREFIX) :].strip()
            if text:
                out.append(text)
    return out


def _parse_guest_feedback(notes: str | None) -> tuple[int | None, str | None]:
    import re

    if not notes:
        return None, None
    for raw in notes.splitlines():
        line = raw.strip()
        if not line.lower().startswith(GUEST_FEEDBACK_PREFIX.lower()):
            continue
        payload = line[len(GUEST_FEEDBACK_PREFIX) :].strip()
        match = re.match(r"^(\d)\s*/\s*5(?:\s*[—\-]\s*(.+))?$", payload)
        if not match:
            continue
        rating = int(match.group(1))
        if 1 <= rating <= 5:
            comment = (match.group(2) or "").strip() or None
            return rating, comment
    return None, None


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if not outlet:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_room(db: Session, tenant_id: int, room_id: int) -> HotelRoom:
    room = (
        db.query(HotelRoom)
        .filter(HotelRoom.id == room_id, HotelRoom.tenant_id == tenant_id, HotelRoom.is_active.is_(True))
        .first()
    )
    if not room:
        raise NotFoundError("Room not found")
    return room


def _get_room_type(db: Session, tenant_id: int, room_type_id: int) -> RoomType:
    room_type = (
        db.query(RoomType)
        .filter(RoomType.id == room_type_id, RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .first()
    )
    if not room_type:
        raise NotFoundError("Room type not found")
    return room_type


def _get_reservation(db: Session, tenant_id: int, reservation_id: int) -> GuestReservation:
    reservation = (
        db.query(GuestReservation)
        .options(
            joinedload(GuestReservation.folio).joinedload(GuestFolio.entries),
        )
        .filter(
            GuestReservation.id == reservation_id,
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )
    if not reservation:
        raise NotFoundError("Reservation not found")
    return reservation


def _nights_between(check_in: date, check_out: date) -> int:
    return max((check_out - check_in).days, 1)


DEFAULT_DAY_USE_RATE_PERCENT = 50.0


def _day_use_percent_for_plan(plan: RatePlan | None) -> float:
    if plan is None:
        return DEFAULT_DAY_USE_RATE_PERCENT
    return float(getattr(plan, "day_use_rate_percent", None) or DEFAULT_DAY_USE_RATE_PERCENT)


def _normalize_day_use_dates(check_in: date, check_out: date, day_use: bool) -> tuple[date, date]:
    """Day-use occupies one inventory night: check-in D, check-out D+1."""
    if not day_use:
        return check_in, check_out
    return check_in, check_in + timedelta(days=1)


def _calc_total(
    rate_per_night: float,
    check_in: date,
    check_out: date,
    *,
    day_use: bool = False,
    day_use_percent: float = DEFAULT_DAY_USE_RATE_PERCENT,
) -> float:
    if day_use:
        return round(float(rate_per_night) * (float(day_use_percent) / 100.0), 2)
    return round(float(rate_per_night) * _nights_between(check_in, check_out), 2)


DEFAULT_INCLUDED_ADULTS = 2
DEFAULT_INCLUDED_CHILDREN = 0


def _occupancy_pricing(plan: RatePlan | None) -> tuple[int, int, float, float]:
    """Return (included_adults, included_children, extra_adult_rate, extra_child_rate)."""
    if plan is None:
        return DEFAULT_INCLUDED_ADULTS, DEFAULT_INCLUDED_CHILDREN, 0.0, 0.0
    return (
        int(getattr(plan, "included_adults", None) or DEFAULT_INCLUDED_ADULTS),
        int(getattr(plan, "included_children", None) or DEFAULT_INCLUDED_CHILDREN),
        float(getattr(plan, "extra_adult_rate", None) or 0),
        float(getattr(plan, "extra_child_rate", None) or 0),
    )


def _extra_person_nightly(adults: int, children: int, plan: RatePlan | None) -> float:
    included_adults, included_children, adult_rate, child_rate = _occupancy_pricing(plan)
    extra_adults = max(0, int(adults) - included_adults)
    extra_children = max(0, int(children) - included_children)
    return round(extra_adults * adult_rate + extra_children * child_rate, 2)


def _calc_extra_person_total(
    adults: int,
    children: int,
    check_in: date,
    check_out: date,
    plan: RatePlan | None,
    *,
    day_use: bool = False,
) -> float:
    nightly = _extra_person_nightly(adults, children, plan)
    if nightly <= 0:
        return 0.0
    # Day-use: charge extras once (full nightly surcharge, not day-use %).
    if day_use:
        return nightly
    return round(nightly * _nights_between(check_in, check_out), 2)


def _reservation_stay_total(
    rate_per_night: float,
    check_in: date,
    check_out: date,
    adults: int,
    children: int,
    plan: RatePlan | None,
    *,
    day_use: bool = False,
) -> float:
    room = _calc_total(
        rate_per_night,
        check_in,
        check_out,
        day_use=day_use,
        day_use_percent=_day_use_percent_for_plan(plan),
    )
    extras = _calc_extra_person_total(
        adults, children, check_in, check_out, plan, day_use=day_use
    )
    return round(room + extras, 2)


def _assert_party_fits_room_type(room_type: RoomType, adults: int, children: int) -> None:
    party = int(adults) + int(children)
    max_occ = int(getattr(room_type, "max_occupancy", None) or 0)
    if max_occ and party > max_occ:
        raise ConflictError(
            f"Party size {party} exceeds max occupancy ({max_occ}) for {room_type.name}"
        )


def _plan_matches_stay(
    plan: RatePlan,
    check_in: date,
    nights: int,
    source: ReservationSource | None,
) -> bool:
    if plan.valid_from and check_in < plan.valid_from:
        return False
    if plan.valid_to and check_in > plan.valid_to:
        return False
    if plan.min_nights > nights:
        return False
    if plan.source is not None and (source is None or plan.source != source):
        return False
    return True


def _plan_priority(
    plan: RatePlan,
    source: ReservationSource | None,
    *,
    has_inclusions: bool = False,
) -> tuple[int, int, int, int, float]:
    source_match = 1 if plan.source and source and plan.source == source else 0
    seasonal = 1 if plan.valid_from or plan.valid_to else 0
    default = 1 if plan.is_default else 0
    rack_preferred = 1 if not has_inclusions else 0
    return (source_match, seasonal, default, rack_preferred, float(plan.rate_per_night))


def _list_plan_inclusions(db: Session, plan_id: int) -> list[RatePlanInclusion]:
    return (
        db.query(RatePlanInclusion)
        .filter(
            RatePlanInclusion.rate_plan_id == plan_id,
            RatePlanInclusion.is_active.is_(True),
        )
        .order_by(RatePlanInclusion.id)
        .all()
    )


def _inclusion_surcharge(inclusions: list[RatePlanInclusion]) -> float:
    return round(sum(float(item.price_per_night) for item in inclusions), 2)


def _plan_effective_rate(plan: RatePlan, inclusions: list[RatePlanInclusion]) -> float:
    return round(float(plan.rate_per_night) + _inclusion_surcharge(inclusions), 2)


def _inclusion_to_read(inclusion: RatePlanInclusion) -> RatePlanInclusionRead:
    return RatePlanInclusionRead(
        id=inclusion.id,
        rate_plan_id=inclusion.rate_plan_id,
        inclusion_type=inclusion.inclusion_type,
        name=inclusion.name,
        price_per_night=float(inclusion.price_per_night),
        is_included=inclusion.is_included,
        credit_amount=float(getattr(inclusion, "credit_amount", 0) or 0),
        credit_scope=getattr(inclusion, "credit_scope", None) or CreditScope.STAY,
        qty_per_stay=int(getattr(inclusion, "qty_per_stay", 0) or 0),
        qty_per_night=int(getattr(inclusion, "qty_per_night", 0) or 0),
        is_active=inclusion.is_active,
        created_at=inclusion.created_at,
        updated_at=inclusion.updated_at,
    )


def resolve_rate(
    db: Session,
    tenant_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
    source: ReservationSource | None = None,
) -> tuple[float, RatePlan | None]:
    nights = _nights_between(check_in, check_out)
    plans = (
        db.query(RatePlan)
        .filter(
            RatePlan.tenant_id == tenant_id,
            RatePlan.room_type_id == room_type_id,
            RatePlan.is_active.is_(True),
        )
        .all()
    )
    matching = [plan for plan in plans if _plan_matches_stay(plan, check_in, nights, source)]
    if matching:
        matching.sort(
            key=lambda plan: _plan_priority(
                plan,
                source,
                has_inclusions=bool(_list_plan_inclusions(db, plan.id)),
            ),
            reverse=True,
        )
        best = matching[0]
        inclusions = _list_plan_inclusions(db, best.id)
        return _plan_effective_rate(best, inclusions), best

    room_type = _get_room_type(db, tenant_id, room_type_id)
    return float(room_type.base_rate), None


def _next_confirmation_number(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"RES-{year}-"
    count = (
        db.query(func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.confirmation_number.like(f"{prefix}%"),
        )
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:05d}"


def _next_folio_number(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"FOL-{year}-"
    count = (
        db.query(func.count(GuestFolio.id))
        .filter(GuestFolio.tenant_id == tenant_id, GuestFolio.folio_number.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:05d}"


def _dates_overlap(start_a: date, end_a: date, start_b: date, end_b: date) -> bool:
    return start_a < end_b and start_b < end_a


def _blocked_room_ids(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    check_in: date,
    check_out: date,
    exclude_block_id: int | None = None,
) -> set[int]:
    q = db.query(RoomBlock.room_id).filter(
        RoomBlock.tenant_id == tenant_id,
        RoomBlock.outlet_id == outlet_id,
        RoomBlock.is_active.is_(True),
        RoomBlock.room_id.isnot(None),
        RoomBlock.start_date < check_out,
        RoomBlock.end_date > check_in,
    )
    if exclude_block_id:
        q = q.filter(RoomBlock.id != exclude_block_id)
    return {row[0] for row in q.all() if row[0] is not None}


def _blocked_counts_by_type(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    check_in: date,
    check_out: date,
    exclude_block_id: int | None = None,
) -> dict[int, int]:
    blocked_ids = _blocked_room_ids(
        db, tenant_id, outlet_id, check_in, check_out, exclude_block_id=exclude_block_id
    )
    if not blocked_ids:
        return {}
    rows = (
        db.query(HotelRoom.room_type_id, func.count(HotelRoom.id))
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.id.in_(blocked_ids),
            HotelRoom.is_active.is_(True),
        )
        .group_by(HotelRoom.room_type_id)
        .all()
    )
    return {row[0]: row[1] for row in rows}


def _occupied_room_ids(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> set[int]:
    q = db.query(GuestReservation.room_id).filter(
        GuestReservation.tenant_id == tenant_id,
        GuestReservation.outlet_id == outlet_id,
        GuestReservation.is_active.is_(True),
        GuestReservation.status.in_(list(ACTIVE_STATUSES)),
        GuestReservation.room_id.isnot(None),
        GuestReservation.check_in_date < check_out,
        GuestReservation.check_out_date > check_in,
    )
    if exclude_reservation_id:
        q = q.filter(GuestReservation.id != exclude_reservation_id)
    occupied = {row[0] for row in q.all() if row[0] is not None}
    occupied |= _blocked_room_ids(db, tenant_id, outlet_id, check_in, check_out)
    return occupied


def _reserved_counts_by_type(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    check_in: date,
    check_out: date,
    exclude_reservation_id: int | None = None,
) -> dict[int, int]:
    q = (
        db.query(GuestReservation.room_type_id, func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status.in_(list(ACTIVE_STATUSES)),
            GuestReservation.check_in_date < check_out,
            GuestReservation.check_out_date > check_in,
        )
        .group_by(GuestReservation.room_type_id)
    )
    if exclude_reservation_id:
        q = q.filter(GuestReservation.id != exclude_reservation_id)
    counts = {row[0]: row[1] for row in q.all()}
    blocked = _blocked_counts_by_type(db, tenant_id, outlet_id, check_in, check_out)
    for room_type_id, blocked_count in blocked.items():
        counts[room_type_id] = counts.get(room_type_id, 0) + blocked_count
    return counts


def _inventory_override_cell(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    on_date: date,
) -> dict:
    from app.modules.settings.service import get_pms_inventory_overrides

    overrides = get_pms_inventory_overrides(db, tenant_id, outlet_id)
    cell = overrides.get(f"{room_type_id}:{on_date.isoformat()}") or {}
    return cell if isinstance(cell, dict) else {}


def _assert_no_stop_sell(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
) -> None:
    cursor = check_in
    while cursor < check_out:
        cell = _inventory_override_cell(db, tenant_id, outlet_id, room_type_id, cursor)
        if cell.get("stop_sell"):
            raise ConflictError(f"Room type is stop-sold on {cursor.isoformat()}")
        cursor += timedelta(days=1)


def _assert_stay_restrictions(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
) -> None:
    """Enforce CTA / CTD / min-max stay from inventory calendar overrides."""
    arrival = _inventory_override_cell(db, tenant_id, outlet_id, room_type_id, check_in)
    if arrival.get("cta"):
        raise ConflictError(f"Closed to arrival on {check_in.isoformat()}")

    departure = _inventory_override_cell(db, tenant_id, outlet_id, room_type_id, check_out)
    if departure.get("ctd"):
        raise ConflictError(f"Closed to departure on {check_out.isoformat()}")

    nights = _nights_between(check_in, check_out)
    min_required = 0
    max_allowed: int | None = None

    if arrival.get("min_stay"):
        try:
            min_required = max(min_required, int(arrival["min_stay"]))
        except (TypeError, ValueError):
            pass
    if arrival.get("max_stay") is not None:
        try:
            max_allowed = int(arrival["max_stay"])
        except (TypeError, ValueError):
            max_allowed = None

    cursor = check_in
    while cursor < check_out:
        cell = _inventory_override_cell(db, tenant_id, outlet_id, room_type_id, cursor)
        if cell.get("min_stay"):
            try:
                min_required = max(min_required, int(cell["min_stay"]))
            except (TypeError, ValueError):
                pass
        cursor += timedelta(days=1)

    if min_required and nights < min_required:
        raise ConflictError(f"Minimum stay is {min_required} night(s) for these dates")
    if max_allowed is not None and max_allowed > 0 and nights > max_allowed:
        raise ConflictError(f"Maximum stay is {max_allowed} night(s) for arrival {check_in.isoformat()}")


def _apply_daily_rate_override(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    check_in: date,
    rate: float,
) -> float:
    cell = _inventory_override_cell(db, tenant_id, outlet_id, room_type_id, check_in)
    if "rate" in cell:
        try:
            return float(cell["rate"])
        except (TypeError, ValueError):
            return rate
    return rate


def _validate_availability(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    room_type_id: int,
    check_in: date,
    check_out: date,
    room_id: int | None = None,
    exclude_reservation_id: int | None = None,
) -> None:
    total_rooms = (
        db.query(func.count(HotelRoom.id))
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.room_type_id == room_type_id,
            HotelRoom.is_active.is_(True),
            HotelRoom.status.notin_([RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE]),
        )
        .scalar()
        or 0
    )
    if total_rooms == 0:
        raise ConflictError("No rooms configured for this room type at the outlet")

    _assert_no_stop_sell(db, tenant_id, outlet_id, room_type_id, check_in, check_out)
    _assert_stay_restrictions(db, tenant_id, outlet_id, room_type_id, check_in, check_out)

    reserved = _reserved_counts_by_type(db, tenant_id, outlet_id, check_in, check_out, exclude_reservation_id)
    if reserved.get(room_type_id, 0) >= total_rooms:
        raise ConflictError("No availability for selected room type and dates")

    if room_id is not None:
        occupied = _occupied_room_ids(
            db, tenant_id, outlet_id, check_in, check_out, exclude_reservation_id
        )
        if room_id in occupied:
            raise ConflictError("Selected room is not available for these dates")
        room = _get_room(db, tenant_id, room_id)
        if room.room_type_id != room_type_id:
            raise ConflictError("Room does not match selected room type")
        if room.outlet_id != outlet_id:
            raise ConflictError("Room does not belong to this outlet")


def _create_folio(db: Session, tenant_id: int, brand_id: int | None, reservation: GuestReservation) -> GuestFolio:
    folio = GuestFolio(
        tenant_id=tenant_id,
        brand_id=brand_id,
        reservation_id=reservation.id,
        folio_number=_next_folio_number(db, tenant_id),
        status=FolioStatus.OPEN,
        balance=0,
    )
    db.add(folio)
    db.flush()
    return folio


def _payment_description(tender: PaymentTender, description: str | None) -> str:
    label = {
        PaymentTender.CASH: "Cash",
        PaymentTender.CARD: "Card",
        PaymentTender.UPI: "UPI",
        PaymentTender.OTHER: "Other",
        PaymentTender.POINTS: "Loyalty points",
    }[tender]
    note = (description or "").strip()
    if not note or note.lower() in {"payment received", "payment", f"payment · {label.lower()}"}:
        return f"Payment · {label}"
    if note.lower().startswith("payment ·"):
        return note[:255]
    return f"Payment · {label} — {note}"[:255]


def _parse_payment_tender(description: str) -> PaymentTender:
    text = (description or "").strip().lower()
    if "· cash" in text or text.startswith("cash") or " tender cash" in text:
        return PaymentTender.CASH
    if "· card" in text or "card payment" in text or text.startswith("card"):
        return PaymentTender.CARD
    if "· upi" in text or "upi payment" in text or text.startswith("upi"):
        return PaymentTender.UPI
    if "· other" in text:
        return PaymentTender.OTHER
    if "loyalty" in text or "· points" in text or "points" in text:
        return PaymentTender.POINTS
    return PaymentTender.OTHER


_FOLIO_CREDIT_TYPES = {
    FolioEntryType.PAYMENT,
    FolioEntryType.DEPOSIT,
    FolioEntryType.REFUND,
    FolioEntryType.PACKAGE_CREDIT,
}

_FNB_PACKAGE_TYPES = {
    InclusionType.BREAKFAST,
    InclusionType.LUNCH,
    InclusionType.DINNER,
    InclusionType.CAFE,
    InclusionType.OTHER,
}


def _add_folio_entry(
    db: Session,
    folio: GuestFolio,
    entry_type: FolioEntryType,
    description: str,
    amount: float,
    posted_by: int | None = None,
    pos_order_id: int | None = None,
    spa_booking_id: int | None = None,
    banquet_booking_id: int | None = None,
) -> FolioEntry:
    signed = amount if entry_type in _FOLIO_CREDIT_TYPES else amount
    if entry_type in _FOLIO_CREDIT_TYPES:
        folio.balance = float(folio.balance) - abs(amount)
    else:
        folio.balance = float(folio.balance) + abs(amount)

    entry = FolioEntry(
        folio_id=folio.id,
        entry_type=entry_type,
        description=description,
        amount=signed,
        posted_by=posted_by,
        pos_order_id=pos_order_id,
        spa_booking_id=spa_booking_id,
        banquet_booking_id=banquet_booking_id,
    )
    db.add(entry)
    db.flush()
    return entry


_QTY_CLAIMABLE_TYPES = {
    InclusionType.BREAKFAST,
    InclusionType.LUNCH,
    InclusionType.DINNER,
    InclusionType.CAFE,
    InclusionType.SPA,
}


def _claimed_today_qty(
    db: Session,
    entitlement_id: int,
    claim_date: date | None = None,
) -> int:
    day = claim_date or date.today()
    total = (
        db.query(func.coalesce(func.sum(PackageEntitlementClaim.qty), 0))
        .filter(
            PackageEntitlementClaim.entitlement_id == entitlement_id,
            PackageEntitlementClaim.claim_date == day,
            PackageEntitlementClaim.is_active.is_(True),
        )
        .scalar()
    )
    return int(total or 0)


def _entitlement_to_read(
    row: ReservationPackageEntitlement,
    *,
    claimed_today: int = 0,
) -> PackageEntitlementRead:
    credit_total = float(row.credit_total or 0)
    credit_used = float(row.credit_used or 0)
    qty_total = int(row.qty_total or 0)
    qty_used = int(row.qty_used or 0)
    qty_remaining = max(qty_total - qty_used, 0)
    can_claim = qty_remaining > 0 and row.inclusion_type in _QTY_CLAIMABLE_TYPES
    return PackageEntitlementRead(
        id=row.id,
        reservation_id=row.reservation_id,
        source_inclusion_id=row.source_inclusion_id,
        inclusion_type=row.inclusion_type,
        name=row.name,
        credit_total=credit_total,
        credit_used=credit_used,
        credit_remaining=round(max(credit_total - credit_used, 0), 2),
        qty_total=qty_total,
        qty_used=qty_used,
        qty_remaining=qty_remaining,
        claimed_today=claimed_today,
        can_claim=can_claim,
        is_active=row.is_active,
        created_at=row.created_at,
        updated_at=row.updated_at,
    )


def _list_reservation_entitlement_reads(
    db: Session,
    reservation_id: int,
) -> list[PackageEntitlementRead]:
    rows = _list_reservation_entitlements(db, reservation_id)
    today = date.today()
    return [
        _entitlement_to_read(row, claimed_today=_claimed_today_qty(db, row.id, today))
        for row in rows
    ]


def claim_package_entitlement(
    db: Session,
    *,
    tenant_id: int,
    entitlement_id: int,
    qty: int = 1,
    channel: str = PackageEntitlementClaimChannel.STAFF.value,
    claimed_by: int | None = None,
    notes: str | None = None,
    reservation: GuestReservation | None = None,
) -> PackageEntitlementClaimRead:
    row = (
        db.query(ReservationPackageEntitlement)
        .filter(
            ReservationPackageEntitlement.id == entitlement_id,
            ReservationPackageEntitlement.tenant_id == tenant_id,
            ReservationPackageEntitlement.is_active.is_(True),
        )
        .first()
    )
    if row is None:
        raise NotFoundError("Package entitlement not found")
    if reservation is not None and row.reservation_id != reservation.id:
        raise ConflictError("Entitlement does not belong to this stay")
    if row.inclusion_type not in _QTY_CLAIMABLE_TYPES:
        raise ConflictError("This package benefit is not claimable as covers")
    qty = max(int(qty or 1), 1)
    remaining = max(int(row.qty_total or 0) - int(row.qty_used or 0), 0)
    if qty > remaining:
        raise ConflictError(f"Only {remaining} cover(s) remaining on this package")

    stay = reservation or _get_reservation(db, tenant_id, row.reservation_id)
    if stay.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Guests must be checked in to claim package covers")

    claim_day = date.today()
    claim = PackageEntitlementClaim(
        tenant_id=tenant_id,
        brand_id=stay.brand_id,
        entitlement_id=row.id,
        reservation_id=stay.id,
        claim_date=claim_day,
        qty=qty,
        channel=channel,
        claimed_by=claimed_by,
        notes=(notes or "").strip() or None,
    )
    row.qty_used = int(row.qty_used or 0) + qty
    db.add(claim)
    db.commit()
    db.refresh(row)
    db.refresh(claim)
    return PackageEntitlementClaimRead(
        id=claim.id,
        entitlement_id=row.id,
        reservation_id=stay.id,
        claim_date=claim.claim_date,
        qty=claim.qty,
        channel=claim.channel,
        claimed_by=claim.claimed_by,
        notes=claim.notes,
        message=f"Claimed {qty} × {row.name}",
        entitlement=_entitlement_to_read(
            row,
            claimed_today=_claimed_today_qty(db, row.id, claim_day),
        ),
    )


def staff_claim_package_entitlement(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    entitlement_id: int,
    data: PackageEntitlementClaimRequest,
) -> PackageEntitlementClaimRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    return claim_package_entitlement(
        db,
        tenant_id=tenant_id,
        entitlement_id=entitlement_id,
        qty=data.qty,
        channel=PackageEntitlementClaimChannel.STAFF.value,
        claimed_by=user_id,
        notes=data.notes,
        reservation=reservation,
    )


def public_claim_package_entitlement(
    db: Session,
    data: PublicRoomHubClaimRequest,
) -> PackageEntitlementClaimRead:
    outlet, room = _find_outlet_room(db, data.outlet_id, data.room_number)
    reservation = _checked_in_reservation_for_room(
        db, outlet.tenant_id, outlet.id, room.id
    )
    if reservation is None:
        raise ConflictError("No checked-in guest in this room")
    if not _mobiles_match(reservation.guest_mobile or "", data.guest_mobile):
        raise NotFoundError("Stay not found for this mobile")
    return claim_package_entitlement(
        db,
        tenant_id=outlet.tenant_id,
        entitlement_id=data.entitlement_id,
        qty=data.qty,
        channel=PackageEntitlementClaimChannel.GUEST_QR.value,
        claimed_by=None,
        notes=data.notes,
        reservation=reservation,
    )


def _list_reservation_entitlements(
    db: Session,
    reservation_id: int,
) -> list[ReservationPackageEntitlement]:
    return (
        db.query(ReservationPackageEntitlement)
        .filter(
            ReservationPackageEntitlement.reservation_id == reservation_id,
            ReservationPackageEntitlement.is_active.is_(True),
        )
        .order_by(ReservationPackageEntitlement.id)
        .all()
    )


def _credit_total_for_inclusion(
    inclusion: RatePlanInclusion,
    nights: int,
) -> float:
    credit_amount = float(inclusion.credit_amount or 0)
    scope = inclusion.credit_scope or CreditScope.STAY
    if credit_amount > 0:
        if scope == CreditScope.NIGHT:
            return round(credit_amount * max(nights, 1), 2)
        return round(credit_amount, 2)

    # Bundled nightly inclusion value becomes a redeemable credit at check-in.
    price = float(inclusion.price_per_night or 0)
    if inclusion.is_included and price > 0 and inclusion.inclusion_type in (
        *_FNB_PACKAGE_TYPES,
        InclusionType.SPA,
    ):
        return round(price * max(nights, 1), 2)
    return 0.0


def _qty_total_for_inclusion(
    inclusion: RatePlanInclusion,
    reservation: GuestReservation,
    nights: int,
) -> int:
    if int(inclusion.qty_per_stay or 0) > 0:
        return int(inclusion.qty_per_stay)
    if int(inclusion.qty_per_night or 0) > 0:
        return int(inclusion.qty_per_night) * max(nights, 1)
    if inclusion.inclusion_type == InclusionType.BREAKFAST and inclusion.is_included:
        return max(int(reservation.adults or 1), 1) * max(nights, 1)
    if inclusion.inclusion_type == InclusionType.SPA and int(inclusion.qty_per_stay or 0) == 0:
        if inclusion.is_included and float(inclusion.credit_amount or 0) == 0:
            return max(nights, 1)
    return 0


def _ensure_package_entitlements(
    db: Session,
    reservation: GuestReservation,
) -> list[ReservationPackageEntitlement]:
    existing = _list_reservation_entitlements(db, reservation.id)
    if existing:
        return existing
    if not reservation.rate_plan_id:
        return []

    nights = _nights_between(reservation.check_in_date, reservation.check_out_date)
    if bool(reservation.day_use):
        nights = 1

    created: list[ReservationPackageEntitlement] = []
    for inclusion in _list_plan_inclusions(db, reservation.rate_plan_id):
        credit_total = _credit_total_for_inclusion(inclusion, nights)
        qty_total = _qty_total_for_inclusion(inclusion, reservation, nights)
        if credit_total <= 0 and qty_total <= 0:
            continue
        row = ReservationPackageEntitlement(
            tenant_id=reservation.tenant_id,
            brand_id=reservation.brand_id,
            reservation_id=reservation.id,
            source_inclusion_id=inclusion.id,
            inclusion_type=inclusion.inclusion_type,
            name=inclusion.name,
            credit_total=credit_total,
            credit_used=0,
            qty_total=qty_total,
            qty_used=0,
        )
        db.add(row)
        created.append(row)
    if created:
        db.flush()
    return created


def _apply_package_credits(
    db: Session,
    reservation: GuestReservation,
    amount: float,
    inclusion_types: set[InclusionType],
    posted_by: int | None = None,
    pos_order_id: int | None = None,
    spa_booking_id: int | None = None,
) -> float:
    """Draw down package ₹ credits and post PACKAGE_CREDIT folio lines. Returns amount covered."""
    if amount <= 0 or not reservation.folio:
        return 0.0

    remaining = round(float(amount), 2)
    applied = 0.0
    entitlements = [
        row
        for row in _list_reservation_entitlements(db, reservation.id)
        if row.inclusion_type in inclusion_types
        and float(row.credit_total or 0) - float(row.credit_used or 0) > 0.009
    ]
    for row in entitlements:
        if remaining <= 0.009:
            break
        available = round(float(row.credit_total) - float(row.credit_used), 2)
        use = round(min(available, remaining), 2)
        if use <= 0:
            continue
        row.credit_used = round(float(row.credit_used) + use, 2)
        if int(row.qty_total or 0) > int(row.qty_used or 0):
            row.qty_used = int(row.qty_used or 0) + 1
        _add_folio_entry(
            db,
            reservation.folio,
            FolioEntryType.PACKAGE_CREDIT,
            f"Package credit — {row.name}",
            use,
            posted_by=posted_by,
            pos_order_id=pos_order_id,
            spa_booking_id=spa_booking_id,
        )
        remaining = round(remaining - use, 2)
        applied = round(applied + use, 2)
    return applied


def _post_room_charges(
    db: Session,
    folio: GuestFolio,
    reservation: GuestReservation,
    posted_by: int | None,
) -> None:
    from app.modules.settings.service import get_pms_tax_config

    tax_cfg = get_pms_tax_config(db, reservation.tenant_id, reservation.outlet_id)
    tax_percent = float(tax_cfg.get("tax_percent", 12.0))
    tax_label = str(tax_cfg.get("tax_label", "GST"))

    plan = db.get(RatePlan, reservation.rate_plan_id) if reservation.rate_plan_id else None
    nights = _nights_between(reservation.check_in_date, reservation.check_out_date)
    for night in range(nights):
        night_date = reservation.check_in_date + timedelta(days=night)
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.ROOM_CHARGE,
            f"Room charge — {night_date.isoformat()}",
            float(reservation.rate_per_night),
            posted_by=posted_by,
        )
        extra = _extra_person_nightly(reservation.adults, reservation.children, plan)
        if extra > 0:
            _add_folio_entry(
                db,
                folio,
                FolioEntryType.ADJUSTMENT,
                f"Extra person — {night_date.isoformat()}",
                extra,
                posted_by=posted_by,
            )
    tax = round(float(reservation.total_amount) * (tax_percent / 100.0), 2)
    if tax > 0:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.TAX,
            f"{tax_label} {tax_percent:g}%",
            tax,
            posted_by=posted_by,
        )


def _post_night_room_charge(
    db: Session,
    folio: GuestFolio,
    reservation: GuestReservation,
    business_date: date,
    posted_by: int | None,
) -> bool:
    """Post a single night room charge + proportional tax if not already posted."""
    from app.modules.settings.service import get_pms_tax_config

    desc = f"Room charge — {business_date.isoformat()}"
    existing = next((e for e in folio.entries if e.description == desc), None)
    if existing:
        return False

    tax_cfg = get_pms_tax_config(db, reservation.tenant_id, reservation.outlet_id)
    tax_percent = float(tax_cfg.get("tax_percent", 12.0))
    tax_label = str(tax_cfg.get("tax_label", "GST"))
    plan = db.get(RatePlan, reservation.rate_plan_id) if reservation.rate_plan_id else None
    rate = float(reservation.rate_per_night)
    extra = _extra_person_nightly(reservation.adults, reservation.children, plan)
    _add_folio_entry(db, folio, FolioEntryType.ROOM_CHARGE, desc, rate, posted_by=posted_by)
    if extra > 0:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.ADJUSTMENT,
            f"Extra person — {business_date.isoformat()}",
            extra,
            posted_by=posted_by,
        )
    tax = round((rate + extra) * (tax_percent / 100.0), 2)
    if tax > 0:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.TAX,
            f"{tax_label} {tax_percent:g}% — {business_date.isoformat()}",
            tax,
            posted_by=posted_by,
        )
    return True


def _ensure_folio(db: Session, reservation: GuestReservation) -> GuestFolio:
    if reservation.folio:
        return reservation.folio
    return _create_folio(db, reservation.tenant_id, reservation.brand_id, reservation)


def _post_rate_plan_fee(
    db: Session,
    reservation: GuestReservation,
    fee_percent: float,
    description: str,
    posted_by: int | None = None,
) -> None:
    if fee_percent <= 0:
        return
    amount = round(float(reservation.total_amount) * (float(fee_percent) / 100.0), 2)
    if amount <= 0:
        return
    folio = _ensure_folio(db, reservation)
    if folio.status != FolioStatus.OPEN:
        folio.status = FolioStatus.OPEN
    _add_folio_entry(
        db,
        folio,
        FolioEntryType.ADJUSTMENT,
        description,
        amount,
        posted_by=posted_by,
    )


def _reservation_to_read(db: Session, reservation: GuestReservation) -> ReservationRead:
    room_number = None
    room_type_name = None
    if reservation.room_id:
        room = db.get(HotelRoom, reservation.room_id)
        room_number = room.room_number if room else None
    room_type = db.get(RoomType, reservation.room_type_id)
    room_type_name = room_type.name if room_type else None

    rate_plan_name = None
    package_inclusions: list[RatePlanInclusionRead] = []
    if reservation.rate_plan_id:
        plan = db.get(RatePlan, reservation.rate_plan_id)
        if plan:
            rate_plan_name = plan.name
            package_inclusions = [
                _inclusion_to_read(item) for item in _list_plan_inclusions(db, plan.id)
            ]

    package_entitlements = [
        _entitlement_to_read(
            item,
            claimed_today=_claimed_today_qty(db, item.id),
        )
        for item in _list_reservation_entitlements(db, reservation.id)
    ]

    return ReservationRead(
        id=reservation.id,
        tenant_id=reservation.tenant_id,
        brand_id=reservation.brand_id,
        outlet_id=reservation.outlet_id,
        confirmation_number=reservation.confirmation_number,
        guest_name=reservation.guest_name,
        guest_email=reservation.guest_email,
        guest_mobile=reservation.guest_mobile,
        customer_id=reservation.customer_id,
        room_type_id=reservation.room_type_id,
        room_id=reservation.room_id,
        room_number=room_number,
        room_type_name=room_type_name,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        nights=0 if bool(reservation.day_use) else _nights_between(reservation.check_in_date, reservation.check_out_date),
        adults=reservation.adults,
        children=reservation.children,
        status=reservation.status,
        source=reservation.source,
        rate_plan_id=reservation.rate_plan_id,
        rate_plan_name=rate_plan_name,
        package_inclusions=package_inclusions,
        package_entitlements=package_entitlements,
        group_id=reservation.group_id,
        guest_id_document=reservation.guest_id_document,
        guest_id_document_type=getattr(reservation, "guest_id_document_type", None),
        estimated_arrival_time=getattr(reservation, "estimated_arrival_time", None),
        pre_check_in_status=getattr(reservation, "pre_check_in_status", None) or PreCheckInStatus.NONE.value,
        pre_check_in_at=getattr(reservation, "pre_check_in_at", None),
        pre_check_in_notes=getattr(reservation, "pre_check_in_notes", None),
        pre_check_in_reviewed_at=getattr(reservation, "pre_check_in_reviewed_at", None),
        express_checkout_status=getattr(reservation, "express_checkout_status", None)
        or ExpressCheckoutStatus.NONE.value,
        express_checkout_at=getattr(reservation, "express_checkout_at", None),
        express_checkout_notes=getattr(reservation, "express_checkout_notes", None),
        estimated_departure_time=getattr(reservation, "estimated_departure_time", None),
        express_checkout_reviewed_at=getattr(reservation, "express_checkout_reviewed_at", None),
        early_check_in=bool(reservation.early_check_in),
        late_check_out=bool(reservation.late_check_out),
        day_use=bool(reservation.day_use),
        guarantee_type=reservation.guarantee_type or GuaranteeType.NONE,
        deposit_status=reservation.deposit_status or DepositStatus.PENDING,
        rate_per_night=float(reservation.rate_per_night),
        total_amount=float(reservation.total_amount),
        deposit_amount=float(reservation.deposit_amount),
        payment_provider=getattr(reservation, "payment_provider", None),
        payment_hold_ref=getattr(reservation, "payment_hold_ref", None),
        payment_auth_code=getattr(reservation, "payment_auth_code", None),
        card_last4=getattr(reservation, "card_last4", None),
        hold_expires_at=getattr(reservation, "hold_expires_at", None),
        notes=reservation.notes,
        checked_in_at=reservation.checked_in_at,
        checked_out_at=reservation.checked_out_at,
        reminder_sent_at=reservation.reminder_sent_at,
        created_by=reservation.created_by,
        created_at=reservation.created_at,
        updated_at=reservation.updated_at,
    )


def _folio_to_read(folio: GuestFolio) -> FolioRead:
    return FolioRead(
        id=folio.id,
        reservation_id=folio.reservation_id,
        group_id=getattr(folio, "group_id", None),
        folio_number=folio.folio_number,
        status=folio.status,
        balance=float(folio.balance),
        entries=[FolioEntryRead.model_validate(e) for e in folio.entries],
        created_at=folio.created_at,
        updated_at=folio.updated_at,
    )


def _create_group_master_folio(
    db: Session,
    tenant_id: int,
    brand_id: int | None,
    group: ReservationGroup,
) -> GuestFolio:
    existing = (
        db.query(GuestFolio)
        .filter(GuestFolio.group_id == group.id, GuestFolio.is_active.is_(True))
        .first()
    )
    if existing:
        return existing
    folio = GuestFolio(
        tenant_id=tenant_id,
        brand_id=brand_id,
        reservation_id=None,
        group_id=group.id,
        folio_number=_next_folio_number(db, tenant_id),
        status=FolioStatus.OPEN,
        balance=0,
    )
    db.add(folio)
    db.flush()
    return folio


def _ensure_group_master_folio(db: Session, group: ReservationGroup) -> GuestFolio:
    if group.master_folio is not None:
        return group.master_folio
    return _create_group_master_folio(db, group.tenant_id, group.brand_id, group)


def _get_group_entity(db: Session, tenant_id: int, group_id: int) -> ReservationGroup:
    group = (
        db.query(ReservationGroup)
        .options(joinedload(ReservationGroup.master_folio).joinedload(GuestFolio.entries))
        .filter(
            ReservationGroup.id == group_id,
            ReservationGroup.tenant_id == tenant_id,
            ReservationGroup.is_active.is_(True),
        )
        .first()
    )
    if group is None:
        raise NotFoundError("Reservation group not found")
    return group


def get_dashboard(db: Session, tenant_id: int, outlet_id: int | None = None) -> PmsDashboard:
    today = date.today()
    base = db.query(GuestReservation).filter(
        GuestReservation.tenant_id == tenant_id,
        GuestReservation.is_active.is_(True),
    )
    if outlet_id:
        base = base.filter(GuestReservation.outlet_id == outlet_id)

    arrivals = base.filter(
        GuestReservation.check_in_date == today,
        GuestReservation.status.in_([ReservationStatus.CONFIRMED, ReservationStatus.PENDING]),
    ).count()
    departures = base.filter(
        GuestReservation.check_out_date == today,
        GuestReservation.status == ReservationStatus.CHECKED_IN,
    ).count()
    in_house = base.filter(GuestReservation.status == ReservationStatus.CHECKED_IN).count()
    pending = base.filter(GuestReservation.status == ReservationStatus.PENDING).count()

    room_q = db.query(HotelRoom).filter(HotelRoom.tenant_id == tenant_id, HotelRoom.is_active.is_(True))
    if outlet_id:
        room_q = room_q.filter(HotelRoom.outlet_id == outlet_id)
    total_rooms = room_q.count()
    occupied = room_q.filter(HotelRoom.status == RoomStatus.OCCUPIED).count()
    occupancy = round((occupied / total_rooms * 100) if total_rooms else 0, 1)

    return PmsDashboard(
        outlet_id=outlet_id,
        arrivals_today=arrivals,
        departures_today=departures,
        in_house=in_house,
        total_rooms=total_rooms,
        occupied_rooms=occupied,
        occupancy_rate=occupancy,
        pending_reservations=pending,
    )


def get_front_desk_readiness(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    business_date: date | None = None,
) -> FrontDeskReadinessResponse:
    _get_outlet(db, tenant_id, outlet_id)
    day = business_date or date.today()
    arrivals = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.check_in_date == day,
            GuestReservation.status.in_(
                [ReservationStatus.CONFIRMED, ReservationStatus.PENDING]
            ),
        )
        .order_by(GuestReservation.guest_name.asc())
        .all()
    )
    rooms = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
        )
        .all()
    )
    rooms_by_id = {r.id: r for r in rooms}
    clean_by_type: dict[int, int] = {}
    for room in rooms:
        if room.status == RoomStatus.VACANT_CLEAN and room.room_type_id is not None:
            clean_by_type[room.room_type_id] = clean_by_type.get(room.room_type_id, 0) + 1

    items: list[FrontDeskReadinessItem] = []
    ready_count = 0
    not_ready_count = 0
    unassigned_count = 0
    pre_check_in_submitted_count = 0
    for reservation in arrivals:
        room = rooms_by_id.get(reservation.room_id) if reservation.room_id else None
        room_type = db.get(RoomType, reservation.room_type_id)
        clean_available = clean_by_type.get(reservation.room_type_id, 0)
        if room is None:
            readiness = "unassigned"
            unassigned_count += 1
        elif room.status == RoomStatus.VACANT_CLEAN:
            readiness = "ready"
            ready_count += 1
        else:
            readiness = "not_ready"
            not_ready_count += 1
        pre_status = getattr(reservation, "pre_check_in_status", None) or PreCheckInStatus.NONE.value
        if pre_status == PreCheckInStatus.SUBMITTED.value:
            pre_check_in_submitted_count += 1
        items.append(
            FrontDeskReadinessItem(
                reservation_id=reservation.id,
                confirmation_number=reservation.confirmation_number,
                guest_name=reservation.guest_name,
                status=reservation.status,
                room_type_id=reservation.room_type_id,
                room_type_name=room_type.name if room_type else None,
                room_id=reservation.room_id,
                room_number=room.room_number if room else None,
                room_status=room.status.value if room else None,
                readiness=readiness,
                clean_rooms_available=clean_available,
                pre_check_in_status=pre_status,
                estimated_arrival_time=getattr(reservation, "estimated_arrival_time", None),
                guest_id_document=reservation.guest_id_document,
                guest_id_document_type=getattr(reservation, "guest_id_document_type", None),
            )
        )

    return FrontDeskReadinessResponse(
        outlet_id=outlet_id,
        business_date=day,
        arrivals_total=len(items),
        ready_count=ready_count,
        not_ready_count=not_ready_count,
        unassigned_count=unassigned_count,
        clean_inventory=sum(clean_by_type.values()),
        pre_check_in_submitted_count=pre_check_in_submitted_count,
        items=items,
    )


def get_availability(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    check_in: date,
    check_out: date,
    source: ReservationSource | None = None,
) -> AvailabilityResponse:
    _get_outlet(db, tenant_id, outlet_id)
    if check_out <= check_in:
        raise ConflictError("check_out_date must be after check_in_date")

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    reserved = _reserved_counts_by_type(db, tenant_id, outlet_id, check_in, check_out)
    results: list[RoomTypeAvailability] = []

    for room_type in room_types:
        total = (
            db.query(func.count(HotelRoom.id))
            .filter(
                HotelRoom.tenant_id == tenant_id,
                HotelRoom.outlet_id == outlet_id,
                HotelRoom.room_type_id == room_type.id,
                HotelRoom.is_active.is_(True),
                HotelRoom.status.notin_([RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE]),
            )
            .scalar()
            or 0
        )
        if total == 0:
            continue
        booked = reserved.get(room_type.id, 0)
        resolved_rate, matched_plan = resolve_rate(
            db, tenant_id, room_type.id, check_in, check_out, source
        )
        resolved_rate = _apply_daily_rate_override(
            db, tenant_id, outlet_id, room_type.id, check_in, resolved_rate
        )
        plan_inclusions = _list_plan_inclusions(db, matched_plan.id) if matched_plan else []
        available = max(total - booked, 0)
        try:
            _assert_no_stop_sell(db, tenant_id, outlet_id, room_type.id, check_in, check_out)
            _assert_stay_restrictions(db, tenant_id, outlet_id, room_type.id, check_in, check_out)
        except ConflictError:
            available = 0
        results.append(
            RoomTypeAvailability(
                room_type_id=room_type.id,
                room_type_name=room_type.name,
                total_rooms=total,
                available_rooms=available,
                base_rate=float(room_type.base_rate),
                resolved_rate=resolved_rate,
                rate_plan_id=matched_plan.id if matched_plan else None,
                rate_plan_name=matched_plan.name if matched_plan else None,
                rate_plan_code=matched_plan.code if matched_plan else None,
                package_inclusions=[_inclusion_to_read(item) for item in plan_inclusions],
            )
        )

    return AvailabilityResponse(
        outlet_id=outlet_id,
        check_in_date=check_in,
        check_out_date=check_out,
        source=source,
        room_types=results,
    )


def list_reservations(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    status: ReservationStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    search: str | None = None,
) -> tuple[list[ReservationRead], int]:
    q = db.query(GuestReservation).filter(
        GuestReservation.tenant_id == tenant_id,
        GuestReservation.is_active.is_(True),
    )
    if outlet_id:
        q = q.filter(GuestReservation.outlet_id == outlet_id)
    if status:
        q = q.filter(GuestReservation.status == status)
    if from_date:
        q = q.filter(GuestReservation.check_out_date >= from_date)
    if to_date:
        q = q.filter(GuestReservation.check_in_date <= to_date)
    if search:
        term = f"%{search.strip()}%"
        q = q.filter(
            or_(
                GuestReservation.guest_name.ilike(term),
                GuestReservation.guest_mobile.ilike(term),
                GuestReservation.confirmation_number.ilike(term),
            )
        )
    q = q.order_by(GuestReservation.check_in_date.desc(), GuestReservation.id.desc())
    rows, total = paginate_query(q, page, page_size)
    return [_reservation_to_read(db, row) for row in rows], total


def get_reservation(db: Session, tenant_id: int, reservation_id: int) -> ReservationDetailRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    base = _reservation_to_read(db, reservation)
    folio = _folio_to_read(reservation.folio) if reservation.folio else None
    city_rows = (
        db.query(CityLedgerEntry)
        .filter(
            CityLedgerEntry.tenant_id == tenant_id,
            CityLedgerEntry.reservation_id == reservation_id,
            CityLedgerEntry.is_active.is_(True),
        )
        .order_by(CityLedgerEntry.created_at.desc())
        .all()
    )
    return ReservationDetailRead(
        **base.model_dump(),
        folio=folio,
        city_ledger_entries=[_city_ledger_to_read(row, reservation.confirmation_number) for row in city_rows],
    )


def create_reservation(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: ReservationCreate,
    default_brand_id: int | None = None,
) -> ReservationRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    room_type = _get_room_type(db, tenant_id, data.room_type_id)
    _assert_party_fits_room_type(room_type, data.adults, data.children)

    check_in, check_out = _normalize_day_use_dates(
        data.check_in_date, data.check_out_date, data.day_use
    )
    if data.day_use and data.late_check_out:
        raise ConflictError("Day use cannot be combined with late check-out")

    _validate_availability(
        db,
        tenant_id,
        data.outlet_id,
        data.room_type_id,
        check_in,
        check_out,
        data.room_id,
    )

    rate = data.rate_per_night
    rate_plan_id = data.rate_plan_id
    matched_plan: RatePlan | None = None
    if data.rate_plan_id is not None:
        plan = _get_rate_plan(db, tenant_id, data.rate_plan_id)
        if plan.room_type_id != data.room_type_id:
            raise ConflictError("Rate plan does not match selected room type")
        if data.day_use and not bool(getattr(plan, "allows_day_use", True)):
            raise ConflictError("Selected rate plan does not allow day use")
        inclusions = _list_plan_inclusions(db, plan.id)
        rate = _plan_effective_rate(plan, inclusions)
        matched_plan = plan
    elif rate <= 0:
        rate, matched_plan = resolve_rate(
            db,
            tenant_id,
            data.room_type_id,
            check_in,
            check_out,
            data.source,
        )
        rate_plan_id = matched_plan.id if matched_plan else None
        if data.day_use and matched_plan and not bool(getattr(matched_plan, "allows_day_use", True)):
            raise ConflictError("Resolved rate plan does not allow day use")

    rate = _apply_daily_rate_override(
        db, tenant_id, data.outlet_id, data.room_type_id, check_in, float(rate)
    )

    day_use_percent = _day_use_percent_for_plan(matched_plan)
    total = _reservation_stay_total(
        rate,
        check_in,
        check_out,
        data.adults,
        data.children,
        matched_plan,
        day_use=data.day_use,
    )
    status = ReservationStatus.CONFIRMED if data.auto_confirm else ReservationStatus.PENDING

    notes = data.notes
    if data.day_use:
        day_note = f"Day use ({day_use_percent:g}% of nightly rate)"
        notes = f"{notes}\n{day_note}".strip() if notes else day_note
    extra_total = _calc_extra_person_total(
        data.adults, data.children, check_in, check_out, matched_plan, day_use=data.day_use
    )
    if extra_total > 0:
        extra_note = f"Extra person charges: ₹{extra_total:,.2f}"
        notes = f"{notes}\n{extra_note}".strip() if notes else extra_note

    reservation = GuestReservation(
        tenant_id=tenant_id,
        brand_id=default_brand_id,
        outlet_id=data.outlet_id,
        confirmation_number=_next_confirmation_number(db, tenant_id),
        guest_name=data.guest_name.strip(),
        guest_email=data.guest_email,
        guest_mobile=data.guest_mobile.strip(),
        customer_id=data.customer_id,
        room_type_id=data.room_type_id,
        room_id=data.room_id,
        check_in_date=check_in,
        check_out_date=check_out,
        adults=data.adults,
        children=data.children,
        status=status,
        source=data.source,
        rate_plan_id=rate_plan_id,
        group_id=data.group_id,
        guest_id_document=data.guest_id_document,
        early_check_in=data.early_check_in,
        late_check_out=False if data.day_use else data.late_check_out,
        day_use=data.day_use,
        guarantee_type=data.guarantee_type,
        deposit_status=DepositStatus.PENDING,
        rate_per_night=rate,
        total_amount=total,
        deposit_amount=data.deposit_amount,
        notes=notes,
        created_by=user_id,
    )
    db.add(reservation)
    db.flush()

    folio = _create_folio(db, tenant_id, default_brand_id, reservation)
    # Cash/advance deposits post immediately; card holds wait until capture.
    if data.deposit_amount > 0 and data.guarantee_type != GuaranteeType.CARD_HOLD:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.DEPOSIT,
            "Advance deposit",
            data.deposit_amount,
            posted_by=user_id,
        )

    db.commit()
    db.refresh(reservation)
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, data.outlet_id)
    return _reservation_to_read(db, reservation)


def update_reservation(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: ReservationUpdate,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status in {ReservationStatus.CHECKED_OUT, ReservationStatus.CANCELLED, ReservationStatus.NO_SHOW}:
        raise ConflictError("Cannot modify a closed reservation")

    payload = data.model_dump(exclude_unset=True)
    check_in = payload.get("check_in_date", reservation.check_in_date)
    check_out = payload.get("check_out_date", reservation.check_out_date)
    room_type_id = payload.get("room_type_id", reservation.room_type_id)
    room_id = payload.get("room_id", reservation.room_id)

    if any(k in payload for k in ("check_in_date", "check_out_date", "room_type_id", "room_id")):
        _validate_availability(
            db,
            tenant_id,
            reservation.outlet_id,
            room_type_id,
            check_in,
            check_out,
            room_id,
            exclude_reservation_id=reservation.id,
        )

    for key, value in payload.items():
        setattr(reservation, key, value)

    if any(
        k in payload
        for k in ("adults", "children", "room_type_id", "check_in_date", "check_out_date")
    ):
        room_type = _get_room_type(db, tenant_id, reservation.room_type_id)
        _assert_party_fits_room_type(room_type, reservation.adults, reservation.children)

    if any(
        k in payload
        for k in (
            "rate_per_night",
            "check_in_date",
            "check_out_date",
            "adults",
            "children",
            "rate_plan_id",
        )
    ):
        plan = db.get(RatePlan, reservation.rate_plan_id) if reservation.rate_plan_id else None
        reservation.total_amount = _reservation_stay_total(
            float(reservation.rate_per_night),
            reservation.check_in_date,
            reservation.check_out_date,
            reservation.adults,
            reservation.children,
            plan,
            day_use=bool(reservation.day_use),
        )

    db.commit()
    db.refresh(reservation)
    if any(k in payload for k in ("check_in_date", "check_out_date", "room_type_id", "room_id")):
        from app.modules.pms.ota_hooks import notify_lodging_availability_changed

        notify_lodging_availability_changed(tenant_id, reservation.outlet_id)
    return _reservation_to_read(db, reservation)


def confirm_reservation(db: Session, tenant_id: int, reservation_id: int) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status != ReservationStatus.PENDING:
        raise ConflictError("Only pending reservations can be confirmed")
    _validate_availability(
        db,
        tenant_id,
        reservation.outlet_id,
        reservation.room_type_id,
        reservation.check_in_date,
        reservation.check_out_date,
        reservation.room_id,
        exclude_reservation_id=reservation.id,
    )
    reservation.status = ReservationStatus.CONFIRMED
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def check_in_reservation(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: CheckInRequest,
) -> ReservationDetailRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status not in {ReservationStatus.CONFIRMED, ReservationStatus.PENDING}:
        raise ConflictError("Reservation must be confirmed before check-in")

    room = _get_room(db, tenant_id, data.room_id)
    if room.outlet_id != reservation.outlet_id:
        raise ConflictError("Room belongs to a different outlet")
    if room.status not in {RoomStatus.VACANT_CLEAN, RoomStatus.VACANT_DIRTY}:
        raise ConflictError(f"Room is not ready for check-in (status: {room.status.value})")

    target_type_id = room.room_type_id
    _validate_availability(
        db,
        tenant_id,
        reservation.outlet_id,
        target_type_id,
        reservation.check_in_date,
        reservation.check_out_date,
        data.room_id,
        exclude_reservation_id=reservation.id,
    )

    if target_type_id != reservation.room_type_id:
        old_type = reservation.room_type_id
        reservation.room_type_id = target_type_id
        reservation.notes = (
            (reservation.notes or "")
            + f"\nRoom type upgrade/change on check-in: {old_type} → {target_type_id}"
        ).strip()

    reservation.room_id = data.room_id
    reservation.status = ReservationStatus.CHECKED_IN
    reservation.checked_in_at = datetime.utcnow()
    if data.notes:
        reservation.notes = (reservation.notes or "") + f"\nCheck-in: {data.notes}"

    if not reservation.folio:
        _create_folio(db, tenant_id, reservation.brand_id, reservation)

    folio = reservation.folio
    existing_charges = [e for e in folio.entries if e.entry_type == FolioEntryType.ROOM_CHARGE]
    if not existing_charges:
        _post_room_charges(db, folio, reservation, user_id)

    _ensure_package_entitlements(db, reservation)

    # Drop leftover departure cleans from a previous guest on this room.
    from app.modules.housekeeping.models import HousekeepingTaskType

    hk_service.skip_open_room_tasks(
        db,
        data.room_id,
        [HousekeepingTaskType.CHECKOUT],
        reason=f"Skipped — guest checked in ({reservation.confirmation_number})",
    )

    hk_service.update_room_status(
        db,
        tenant_id,
        data.room_id,
        RoomStatusUpdate(
            status=RoomStatus.OCCUPIED,
            guest_name=reservation.guest_name,
            checkout_date=reservation.check_out_date,
            notes=reservation.notes,
        ),
    )

    db.commit()
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, reservation.outlet_id)
    return get_reservation(db, tenant_id, reservation_id)


def check_out_reservation(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: CheckOutRequest,
) -> ReservationDetailRead:
    from app.modules.settings.service import get_pms_tax_config

    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Guest is not checked in")
    if not reservation.room_id:
        raise ConflictError("No room assigned to this reservation")

    tax_cfg = get_pms_tax_config(db, tenant_id, reservation.outlet_id)
    if (
        tax_cfg.get("require_zero_balance_checkout")
        and reservation.folio
        and float(reservation.folio.balance) > 0.01
        and not data.force_settle
    ):
        raise ConflictError("Folio balance must be settled before checkout")

    reservation.status = ReservationStatus.CHECKED_OUT
    reservation.checked_out_at = datetime.utcnow()
    if data.notes:
        reservation.notes = (reservation.notes or "") + f"\nCheck-out: {data.notes}"

    if reservation.folio and reservation.folio.status == FolioStatus.OPEN:
        reservation.folio.status = FolioStatus.CLOSED

    room = _get_room(db, tenant_id, reservation.room_id)
    from app.modules.housekeeping.models import HousekeepingTaskType

    # Stayover daily cleans no longer apply after departure.
    hk_service.skip_open_room_tasks(
        db,
        reservation.room_id,
        [HousekeepingTaskType.DAILY],
        reason=f"Skipped — guest checked out ({reservation.confirmation_number})",
    )
    hk_service.update_room_status(
        db,
        tenant_id,
        reservation.room_id,
        RoomStatusUpdate(
            status=RoomStatus.CHECKOUT_PENDING,
            guest_name=None,
            checkout_date=None,
            notes=f"Departure clean · {reservation.confirmation_number}",
        ),
    )
    # Ensure departure housekeeping task exists (update_room_status also auto-creates).
    hk_service.ensure_room_task(
        db,
        tenant_id,
        room,
        HousekeepingTaskType.CHECKOUT,
        notes=f"Checkout · {reservation.confirmation_number} · {reservation.guest_name}",
    )

    from app.modules.loyalty import service as loyalty_service

    loyalty_service.earn_from_pms_checkout(db, tenant_id, reservation, user_id=user_id)

    db.commit()
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, reservation.outlet_id)
    return get_reservation(db, tenant_id, reservation_id)


def cancel_reservation(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: CancelReservationRequest,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status in {ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT}:
        raise ConflictError("Cannot cancel an active or completed stay")
    if reservation.status == ReservationStatus.CANCELLED:
        raise ConflictError("Reservation is already cancelled")

    if reservation.deposit_status == DepositStatus.HELD and reservation.payment_hold_ref:
        hold_ref = reservation.payment_hold_ref
        reservation.deposit_status = DepositStatus.PENDING
        reservation.payment_hold_ref = None
        reservation.payment_auth_code = None
        reservation.hold_expires_at = None
        reservation.notes = (reservation.notes or "") + f"\nCard hold released on cancel ({hold_ref})"

    reservation.status = ReservationStatus.CANCELLED
    if data.reason:
        reservation.notes = (reservation.notes or "") + f"\nCancelled: {data.reason}"
    if reservation.rate_plan_id:
        plan = db.get(RatePlan, reservation.rate_plan_id)
        if plan and float(plan.cancellation_fee_percent or 0) > 0:
            _post_rate_plan_fee(
                db,
                reservation,
                float(plan.cancellation_fee_percent),
                f"Cancellation fee ({float(plan.cancellation_fee_percent):g}%)",
            )
    db.commit()
    db.refresh(reservation)
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, reservation.outlet_id)
    return _reservation_to_read(db, reservation)


def mark_no_show(db: Session, tenant_id: int, reservation_id: int) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status != ReservationStatus.CONFIRMED:
        raise ConflictError("Only confirmed reservations can be marked no-show")
    reservation.status = ReservationStatus.NO_SHOW
    if reservation.rate_plan_id:
        plan = db.get(RatePlan, reservation.rate_plan_id)
        if plan and float(plan.no_show_fee_percent or 0) > 0:
            _post_rate_plan_fee(
                db,
                reservation,
                float(plan.no_show_fee_percent),
                f"No-show fee ({float(plan.no_show_fee_percent):g}%)",
            )
    db.commit()
    db.refresh(reservation)
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, reservation.outlet_id)
    return _reservation_to_read(db, reservation)


def add_folio_charge(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: FolioChargeCreate,
) -> FolioRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if not reservation.folio:
        raise NotFoundError("Folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Folio is closed")
    _add_folio_entry(
        db,
        reservation.folio,
        data.entry_type,
        data.description,
        data.amount,
        posted_by=user_id,
    )
    db.commit()
    db.refresh(reservation.folio)
    return _folio_to_read(reservation.folio)


def add_folio_payment(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: FolioPaymentCreate,
) -> FolioRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if not reservation.folio:
        raise NotFoundError("Folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Folio is closed")

    if data.tender == PaymentTender.POINTS:
        customer_id = reservation.customer_id
        if not customer_id and reservation.guest_mobile:
            from app.modules.customers.models import Customer

            match = (
                db.query(Customer)
                .filter(Customer.tenant_id == tenant_id, Customer.mobile == reservation.guest_mobile)
                .first()
            )
            if match:
                customer_id = match.id
                reservation.customer_id = match.id
        if not customer_id:
            raise ConflictError("Link a customer to redeem loyalty points on the folio")
        if not data.loyalty_points:
            raise ConflictError("loyalty_points is required for points tender")
        from app.modules.loyalty import service as loyalty_service

        loyalty_service.burn_for_folio_payment(
            db,
            tenant_id,
            customer_id=customer_id,
            reservation_id=reservation.id,
            points=int(data.loyalty_points),
            amount=float(data.amount),
            outlet_id=reservation.outlet_id,
            brand_id=reservation.brand_id,
            user_id=user_id,
        )

    _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.PAYMENT,
        _payment_description(data.tender, data.description),
        data.amount,
        posted_by=user_id,
    )
    db.commit()
    db.refresh(reservation.folio)
    return _folio_to_read(reservation.folio)


def void_folio_entry(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    entry_id: int,
    data: FolioEntryVoidRequest | None = None,
) -> FolioRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if not reservation.folio:
        raise NotFoundError("Folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Folio is closed")

    entry = (
        db.query(FolioEntry)
        .filter(
            FolioEntry.id == entry_id,
            FolioEntry.folio_id == reservation.folio.id,
            FolioEntry.is_active.is_(True),
        )
        .first()
    )
    if entry is None:
        raise NotFoundError("Folio entry not found")

    desc = entry.description or ""
    if "[VOIDED]" in desc.upper() or desc.upper().startswith("VOID #"):
        raise ConflictError("Entry is already voided")

    void_marker = f"VOID #{entry.id}:"
    already = any(
        (e.description or "").startswith(void_marker)
        for e in reservation.folio.entries
        if e.is_active
    )
    if already:
        raise ConflictError("Entry is already voided")

    amount = abs(float(entry.amount))
    reason = (data.reason if data else None) or "Staff void"
    void_desc = f"{void_marker} {desc}"[:220]
    if reason:
        void_desc = f"{void_desc} ({reason})"[:255]

    credit_types = _FOLIO_CREDIT_TYPES
    if entry.entry_type in credit_types:
        _add_folio_entry(
            db,
            reservation.folio,
            FolioEntryType.ADJUSTMENT,
            void_desc,
            amount,
            posted_by=user_id,
        )
    else:
        _add_folio_entry(
            db,
            reservation.folio,
            FolioEntryType.REFUND,
            void_desc,
            amount,
            posted_by=user_id,
        )

    entry.description = f"{desc} [VOIDED]"[:255]
    db.commit()
    db.refresh(reservation.folio)
    return _folio_to_read(reservation.folio)


def fulfill_guest_special_requests(
    db: Session,
    tenant_id: int,
    reservation_id: int,
) -> SpecialRequestFulfillResponse:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    notes = reservation.notes or ""
    if not notes.strip():
        return SpecialRequestFulfillResponse(
            message="No open special requests",
            reservation_id=reservation.id,
            fulfilled_count=0,
        )

    open_prefix = "guest special request:"
    fulfilled_prefix = "Fulfilled special request:"
    lines = notes.split("\n")
    changed = 0
    next_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if stripped.lower().startswith(open_prefix):
            rest = stripped[len(open_prefix) :].strip()
            next_lines.append(f"{fulfilled_prefix} {rest}".rstrip())
            changed += 1
        else:
            next_lines.append(line)
    if changed:
        reservation.notes = "\n".join(next_lines)
        db.commit()
    return SpecialRequestFulfillResponse(
        message=f"Fulfilled {changed} special request(s)",
        reservation_id=reservation.id,
        fulfilled_count=changed,
    )


def get_folio(db: Session, tenant_id: int, reservation_id: int) -> FolioRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if not reservation.folio:
        raise NotFoundError("Folio not found")
    return _folio_to_read(reservation.folio)


def _folio_pdf_context(db: Session, tenant_id: int, reservation_id: int):
    from app.modules.pms.folio_pdf import build_simple_pdf, folio_statement_lines

    reservation = (
        db.query(GuestReservation)
        .options(joinedload(GuestReservation.folio).joinedload(GuestFolio.entries))
        .filter(
            GuestReservation.id == reservation_id,
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )
    if not reservation:
        raise NotFoundError("Reservation not found")
    if not reservation.folio:
        raise NotFoundError("Folio not found")

    outlet = _get_outlet(db, tenant_id, reservation.outlet_id)
    room_number = None
    if reservation.room_id:
        room = db.get(HotelRoom, reservation.room_id)
        room_number = room.room_number if room else None
    room_type = db.get(RoomType, reservation.room_type_id)
    entries = sorted(reservation.folio.entries, key=lambda e: e.id)
    lines = folio_statement_lines(
        outlet_name=outlet.outlet_name,
        folio_number=reservation.folio.folio_number,
        confirmation_number=reservation.confirmation_number,
        guest_name=reservation.guest_name,
        guest_email=reservation.guest_email,
        guest_mobile=reservation.guest_mobile,
        room_number=room_number,
        room_type_name=room_type.name if room_type else None,
        check_in=reservation.check_in_date,
        check_out=reservation.check_out_date,
        folio_status=reservation.folio.status.value,
        balance=float(reservation.folio.balance),
        entries=[
            (e.entry_type.value, e.description, float(e.amount), e.created_at)
            for e in entries
        ],
    )
    pdf_bytes = build_simple_pdf(
        lines,
        title=f"Guest Folio {reservation.folio.folio_number}",
    )
    filename = f"folio-{reservation.folio.folio_number}.pdf"
    return reservation, lines, pdf_bytes, filename


def build_folio_pdf(
    db: Session,
    tenant_id: int,
    reservation_id: int,
) -> tuple[bytes, str]:
    _, _, pdf_bytes, filename = _folio_pdf_context(db, tenant_id, reservation_id)
    return pdf_bytes, filename


async def email_folio_statement(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: FolioEmailRequest | None = None,
) -> FolioEmailResponse:
    from app.modules.communications import service as comms_service
    from app.modules.communications.models import MessageChannel
    from app.modules.communications.schemas import EmailSendRequest

    reservation, lines, _pdf_bytes, _filename = _folio_pdf_context(
        db, tenant_id, reservation_id
    )
    to_email = (data.to_email if data and data.to_email else None) or reservation.guest_email
    if not to_email:
        raise ConflictError("Guest email is required to email the folio")

    if not comms_service.is_channel_enabled(
        db,
        tenant_id,
        MessageChannel.EMAIL,
        brand_id=reservation.brand_id,
        outlet_id=reservation.outlet_id,
    ):
        raise ConflictError("Email channel is not enabled for this outlet")

    outlet = _get_outlet(db, tenant_id, reservation.outlet_id)
    note = (data.note if data and data.note else "").strip()
    body_parts = [
        f"Hi {reservation.guest_name},",
        "",
        f"Please find your guest folio statement for {outlet.outlet_name} "
        f"(confirmation {reservation.confirmation_number}).",
        "",
        *lines,
    ]
    if note:
        body_parts.extend(["", f"Note: {note}"])
    body_parts.extend(
        [
            "",
            "You can also download a printable PDF from the guest booking portal.",
            "",
            "Thank you,",
            outlet.outlet_name,
        ]
    )
    body = "\n".join(body_parts)
    subject = f"Guest folio {reservation.folio.folio_number} — {reservation.confirmation_number}"

    await comms_service.send_mock_email(
        db,
        tenant_id,
        user_id,
        EmailSendRequest(
            receiver=to_email,
            subject=subject,
            message_text=body,
            outlet_id=reservation.outlet_id,
            customer_id=reservation.customer_id,
            brand_id=reservation.brand_id,
        ),
        default_brand_id=reservation.brand_id,
    )
    reservation.notes = (reservation.notes or "") + f"\nFolio emailed to {to_email}"
    db.commit()

    return FolioEmailResponse(
        message=f"Folio statement emailed to {to_email}",
        reservation_id=reservation.id,
        folio_number=reservation.folio.folio_number,
        sent_to=to_email,
    )


def post_spa_booking_to_folio(
    db: Session,
    tenant_id: int,
    user_id: int | None,
    booking_id: int,
) -> FolioEntry:
    from app.modules.spa.models import SpaBooking, SpaBookingStatus

    booking = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(SpaBooking.id == booking_id, SpaBooking.tenant_id == tenant_id, SpaBooking.is_active.is_(True))
        .first()
    )
    if booking is None:
        raise NotFoundError("Spa booking not found")
    if not booking.guest_reservation_id:
        raise ConflictError("Spa booking is not linked to a guest reservation")
    if not booking.charge_to_folio:
        raise ConflictError("Spa booking is not marked for folio charging")
    if booking.folio_posted_at is not None:
        raise ConflictError("Spa charge is already posted to folio")
    if booking.status != SpaBookingStatus.COMPLETED:
        raise ConflictError("Only completed spa bookings can be posted to folio")
    if float(booking.price) <= 0:
        raise ConflictError("Spa booking has no charge amount")

    reservation = _get_reservation(db, tenant_id, booking.guest_reservation_id)
    if reservation.status not in {ReservationStatus.CHECKED_IN, ReservationStatus.CONFIRMED}:
        raise ConflictError("Guest must be checked in or confirmed to post spa charges")
    if not reservation.folio:
        raise NotFoundError("Guest folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    duplicate = (
        db.query(FolioEntry)
        .filter(FolioEntry.folio_id == reservation.folio.id, FolioEntry.spa_booking_id == booking.id)
        .first()
    )
    if duplicate:
        raise ConflictError("Spa charge is already on the guest folio")

    service_name = booking.service.name if booking.service else "Spa service"
    description = f"{service_name} — {booking.booking_number}"
    if booking.party_size > 1:
        description = f"{description} (×{booking.party_size})"

    entry = _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.SPA_CHARGE,
        description,
        float(booking.price),
        posted_by=user_id,
        spa_booking_id=booking.id,
    )
    _ensure_package_entitlements(db, reservation)
    _apply_package_credits(
        db,
        reservation,
        float(booking.price),
        {InclusionType.SPA},
        posted_by=user_id,
        spa_booking_id=booking.id,
    )
    booking.folio_posted_at = datetime.utcnow()
    db.flush()
    return entry


def post_banquet_deposit_to_folio(
    db: Session,
    tenant_id: int,
    user_id: int | None,
    booking_id: int,
) -> FolioEntry:
    from app.modules.banquet.models import BanquetBooking

    booking = (
        db.query(BanquetBooking)
        .options(joinedload(BanquetBooking.venue))
        .filter(BanquetBooking.id == booking_id, BanquetBooking.tenant_id == tenant_id, BanquetBooking.is_active.is_(True))
        .first()
    )
    if booking is None:
        raise NotFoundError("Banquet booking not found")
    if not booking.guest_reservation_id:
        raise ConflictError("Banquet booking is not linked to a guest reservation")
    if float(booking.advance_paid) <= 0:
        raise ConflictError("Banquet booking has no advance deposit to post")
    if booking.deposit_folio_posted_at is not None:
        raise ConflictError("Banquet deposit is already posted to folio")

    reservation = _get_reservation(db, tenant_id, booking.guest_reservation_id)
    if reservation.status not in {ReservationStatus.CHECKED_IN, ReservationStatus.CONFIRMED}:
        raise ConflictError("Guest must be checked in or confirmed to post banquet deposits")
    if not reservation.folio:
        raise NotFoundError("Guest folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    duplicate = (
        db.query(FolioEntry)
        .filter(
            FolioEntry.folio_id == reservation.folio.id,
            FolioEntry.banquet_booking_id == booking.id,
            FolioEntry.entry_type == FolioEntryType.DEPOSIT,
        )
        .first()
    )
    if duplicate:
        raise ConflictError("Banquet deposit is already on the guest folio")

    venue_name = booking.venue.name if booking.venue else "Banquet venue"
    description = f"Banquet deposit — {venue_name} ({booking.booking_number})"
    entry = _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.DEPOSIT,
        description,
        float(booking.advance_paid),
        posted_by=user_id,
        banquet_booking_id=booking.id,
    )
    booking.deposit_folio_posted_at = datetime.utcnow()
    db.flush()
    return entry


def post_banquet_booking_to_folio(
    db: Session,
    tenant_id: int,
    user_id: int | None,
    booking_id: int,
) -> FolioEntry:
    from app.modules.banquet.models import BanquetBooking, BanquetBookingStatus

    booking = (
        db.query(BanquetBooking)
        .options(joinedload(BanquetBooking.venue))
        .filter(BanquetBooking.id == booking_id, BanquetBooking.tenant_id == tenant_id, BanquetBooking.is_active.is_(True))
        .first()
    )
    if booking is None:
        raise NotFoundError("Banquet booking not found")
    if not booking.guest_reservation_id:
        raise ConflictError("Banquet booking is not linked to a guest reservation")
    if not booking.charge_to_folio:
        raise ConflictError("Banquet booking is not marked for folio charging")
    if booking.folio_posted_at is not None:
        raise ConflictError("Banquet charge is already posted to folio")
    if booking.status != BanquetBookingStatus.COMPLETED:
        raise ConflictError("Only completed banquet bookings can be posted to folio")
    if float(booking.estimated_amount) <= 0:
        raise ConflictError("Banquet booking has no charge amount")

    reservation = _get_reservation(db, tenant_id, booking.guest_reservation_id)
    if reservation.status not in {ReservationStatus.CHECKED_IN, ReservationStatus.CONFIRMED}:
        raise ConflictError("Guest must be checked in or confirmed to post banquet charges")
    if not reservation.folio:
        raise NotFoundError("Guest folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    duplicate = (
        db.query(FolioEntry)
        .filter(
            FolioEntry.folio_id == reservation.folio.id,
            FolioEntry.banquet_booking_id == booking.id,
            FolioEntry.entry_type == FolioEntryType.BANQUET_CHARGE,
        )
        .first()
    )
    if duplicate:
        raise ConflictError("Banquet charge is already on the guest folio")

    venue_name = booking.venue.name if booking.venue else "Banquet venue"
    description = f"{booking.title} — {venue_name} ({booking.booking_number})"
    entry = _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.BANQUET_CHARGE,
        description,
        float(booking.estimated_amount),
        posted_by=user_id,
        banquet_booking_id=booking.id,
    )
    booking.folio_posted_at = datetime.utcnow()
    db.flush()
    return entry


def list_in_house_guests(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
) -> list[InHouseGuestRead]:
    q = db.query(GuestReservation).filter(
        GuestReservation.tenant_id == tenant_id,
        GuestReservation.is_active.is_(True),
        GuestReservation.status == ReservationStatus.CHECKED_IN,
    )
    if outlet_id:
        q = q.filter(GuestReservation.outlet_id == outlet_id)
    q = q.order_by(GuestReservation.guest_name)

    results: list[InHouseGuestRead] = []
    for reservation in q.all():
        room_number = None
        room_type_name = None
        if reservation.room_id:
            room = db.get(HotelRoom, reservation.room_id)
            room_number = room.room_number if room else None
        room_type = db.get(RoomType, reservation.room_type_id)
        room_type_name = room_type.name if room_type else None
        results.append(
            InHouseGuestRead(
                reservation_id=reservation.id,
                confirmation_number=reservation.confirmation_number,
                guest_name=reservation.guest_name,
                room_number=room_number,
                room_type_name=room_type_name,
                outlet_id=reservation.outlet_id,
            )
        )
    return results


def _normalize_mobile_digits(value: str) -> str:
    return "".join(ch for ch in value if ch.isdigit())


def verify_public_room_guest(db: Session, data) -> "PublicRoomVerifyResponse":
    from app.modules.menu.schemas import PublicRoomVerifyResponse

    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    room_key = data.room_number.strip().upper()
    room = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == outlet.tenant_id,
            HotelRoom.outlet_id == outlet.id,
            HotelRoom.is_active.is_(True),
            func.upper(HotelRoom.room_number) == room_key,
        )
        .first()
    )
    if room is None:
        raise NotFoundError("Room not found at this property")

    reservation = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == outlet.tenant_id,
            GuestReservation.outlet_id == outlet.id,
            GuestReservation.room_id == room.id,
            GuestReservation.status == ReservationStatus.CHECKED_IN,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )
    if reservation is None:
        raise ConflictError("No checked-in guest for this room")

    provided = _normalize_mobile_digits(data.guest_mobile)
    stored = _normalize_mobile_digits(reservation.guest_mobile or "")
    if not provided or not stored:
        raise ConflictError("Mobile number does not match this stay")
    if provided != stored and not (len(provided) >= 4 and stored.endswith(provided[-4:])):
        raise ConflictError("Mobile number does not match this stay")

    return PublicRoomVerifyResponse(
        reservation_id=reservation.id,
        guest_name=reservation.guest_name,
        room_number=room.room_number,
        confirmation_number=reservation.confirmation_number,
    )


def post_bill_to_room(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: PostToRoomRequest,
) -> PostToRoomResponse:
    from app.modules.pos.models import (
        Bill,
        BillPaymentStatus,
        Order,
        Payment,
        PaymentMode,
        PaymentRecordStatus,
    )
    from app.modules.tables.models import RestaurantTable, TableStatus

    reservation = _get_reservation(db, tenant_id, data.reservation_id)
    if reservation.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Guest must be checked in to post charges to room")
    if not reservation.folio:
        raise NotFoundError("Folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    target = (data.target or "auto").strip().lower()
    charge_folio = reservation.folio
    post_to_master = False
    if reservation.group_id:
        group = _get_group_entity(db, tenant_id, reservation.group_id)
        route = _group_billing_target(group, "pos")
        if target == "master" or (target == "auto" and route == "master"):
            master = _ensure_group_master_folio(db, group)
            if master.status != FolioStatus.OPEN:
                raise ConflictError("Group master folio is closed")
            charge_folio = master
            post_to_master = True
        elif target not in {"room", "auto", "master"}:
            raise ConflictError("target must be room, master, or auto")

    bill = (
        db.query(Bill)
        .filter(Bill.id == data.bill_id, Bill.tenant_id == tenant_id)
        .with_for_update()
        .first()
    )
    if bill is None:
        raise NotFoundError("Bill not found")
    if bill.payment_status == BillPaymentStatus.CANCELLED:
        raise ConflictError("Bill is cancelled")
    if bill.payment_status == BillPaymentStatus.PAID:
        raise ConflictError("Bill is already fully paid")

    duplicate = (
        db.query(FolioEntry)
        .filter(
            FolioEntry.folio_id == charge_folio.id,
            FolioEntry.pos_order_id == bill.order_id,
        )
        .first()
    )
    if duplicate:
        raise ConflictError("This bill is already posted to the guest folio")

    paid_total = (
        db.query(func.coalesce(func.sum(Payment.amount), 0))
        .filter(Payment.bill_id == bill.id, Payment.status == PaymentRecordStatus.SUCCESS)
        .scalar()
    )
    paid_total = float(paid_total or 0)
    amount_due = round(float(bill.grand_total) - paid_total, 2)
    if amount_due <= 0:
        raise ConflictError("Nothing due on this bill")

    amount = round(float(data.amount), 2) if data.amount is not None else amount_due
    if amount <= 0 or amount > amount_due + 0.01:
        raise ConflictError("Invalid payment amount for this bill")

    room_label = "—"
    if reservation.room_id:
        room = db.get(HotelRoom, reservation.room_id)
        if room:
            room_label = room.room_number

    description = data.description or f"Restaurant — {bill.bill_number}"
    if post_to_master:
        description = f"{description} · to master ({reservation.guest_name})"
    reference = f"Room {room_label} · {charge_folio.folio_number}"

    payment = Payment(
        bill_id=bill.id,
        payment_mode=PaymentMode.ROOM_CHARGE,
        amount=amount,
        reference_number=reference,
        status=PaymentRecordStatus.SUCCESS,
    )
    db.add(payment)
    db.flush()

    new_paid = round(paid_total + amount, 2)
    if new_paid >= float(bill.grand_total):
        bill.payment_status = BillPaymentStatus.PAID
        order = db.get(Order, bill.order_id)
        if order and order.table_id:
            table = db.get(RestaurantTable, order.table_id)
            if table:
                table.status = TableStatus.AVAILABLE
                table.current_order_id = None
                table.assigned_waiter_id = None
                table.occupied_since = None
    elif new_paid > 0:
        bill.payment_status = BillPaymentStatus.PARTIAL

    _add_folio_entry(
        db,
        charge_folio,
        FolioEntryType.POS_CHARGE,
        description,
        amount,
        posted_by=user_id,
        pos_order_id=bill.order_id,
    )

    if not post_to_master:
        _ensure_package_entitlements(db, reservation)
        _apply_package_credits(
            db,
            reservation,
            amount,
            _FNB_PACKAGE_TYPES,
            posted_by=user_id,
            pos_order_id=bill.order_id,
        )

    db.commit()
    db.refresh(charge_folio)
    return PostToRoomResponse(
        reservation_id=reservation.id,
        bill_id=bill.id,
        amount=amount,
        folio=_folio_to_read(charge_folio),
    )


def _rate_plan_to_read(db: Session, plan: RatePlan) -> RatePlanRead:
    room_type = db.get(RoomType, plan.room_type_id)
    inclusions = _list_plan_inclusions(db, plan.id)
    return RatePlanRead(
        id=plan.id,
        tenant_id=plan.tenant_id,
        brand_id=plan.brand_id,
        room_type_id=plan.room_type_id,
        room_type_name=room_type.name if room_type else None,
        name=plan.name,
        code=plan.code,
        rate_per_night=float(plan.rate_per_night),
        effective_rate_per_night=_plan_effective_rate(plan, inclusions),
        is_default=plan.is_default,
        source=plan.source,
        valid_from=plan.valid_from,
        valid_to=plan.valid_to,
        min_nights=plan.min_nights,
        description=plan.description,
        cancellation_fee_percent=float(plan.cancellation_fee_percent or 0),
        no_show_fee_percent=float(plan.no_show_fee_percent or 0),
        default_guarantee=plan.default_guarantee or GuaranteeType.NONE,
        allows_day_use=bool(getattr(plan, "allows_day_use", True)),
        day_use_rate_percent=float(
            getattr(plan, "day_use_rate_percent", None) or DEFAULT_DAY_USE_RATE_PERCENT
        ),
        included_adults=int(getattr(plan, "included_adults", None) or DEFAULT_INCLUDED_ADULTS),
        included_children=int(getattr(plan, "included_children", None) or DEFAULT_INCLUDED_CHILDREN),
        extra_adult_rate=float(getattr(plan, "extra_adult_rate", None) or 0),
        extra_child_rate=float(getattr(plan, "extra_child_rate", None) or 0),
        is_active=plan.is_active,
        inclusions=[_inclusion_to_read(item) for item in inclusions],
        created_at=plan.created_at,
        updated_at=plan.updated_at,
    )


def _get_rate_plan(db: Session, tenant_id: int, plan_id: int) -> RatePlan:
    plan = (
        db.query(RatePlan)
        .filter(RatePlan.id == plan_id, RatePlan.tenant_id == tenant_id, RatePlan.is_active.is_(True))
        .first()
    )
    if plan is None:
        raise NotFoundError("Rate plan not found")
    return plan


def _clear_default_rate_plans(db: Session, tenant_id: int, room_type_id: int, except_id: int | None = None) -> None:
    query = db.query(RatePlan).filter(
        RatePlan.tenant_id == tenant_id,
        RatePlan.room_type_id == room_type_id,
        RatePlan.is_default.is_(True),
    )
    if except_id is not None:
        query = query.filter(RatePlan.id != except_id)
    for plan in query.all():
        plan.is_default = False


def list_rate_plans(
    db: Session,
    tenant_id: int,
    room_type_id: int | None = None,
) -> list[RatePlanRead]:
    q = db.query(RatePlan).filter(RatePlan.tenant_id == tenant_id, RatePlan.is_active.is_(True))
    if room_type_id:
        q = q.filter(RatePlan.room_type_id == room_type_id)
    plans = q.order_by(RatePlan.room_type_id, RatePlan.name).all()
    return [_rate_plan_to_read(db, plan) for plan in plans]


def create_rate_plan(
    db: Session,
    tenant_id: int,
    data: RatePlanCreate,
    default_brand_id: int | None = None,
) -> RatePlanRead:
    _get_room_type(db, tenant_id, data.room_type_id)

    existing = (
        db.query(RatePlan)
        .filter(RatePlan.tenant_id == tenant_id, RatePlan.code == data.code.strip().upper())
        .first()
    )
    if existing:
        raise ConflictError("Rate plan code already exists")

    if data.is_default:
        _clear_default_rate_plans(db, tenant_id, data.room_type_id)

    plan = RatePlan(
        tenant_id=tenant_id,
        brand_id=default_brand_id,
        room_type_id=data.room_type_id,
        name=data.name.strip(),
        code=data.code.strip().upper(),
        rate_per_night=data.rate_per_night,
        is_default=data.is_default,
        source=data.source,
        valid_from=data.valid_from,
        valid_to=data.valid_to,
        min_nights=data.min_nights,
        description=data.description,
        cancellation_fee_percent=data.cancellation_fee_percent,
        no_show_fee_percent=data.no_show_fee_percent,
        default_guarantee=data.default_guarantee,
        allows_day_use=data.allows_day_use,
        day_use_rate_percent=data.day_use_rate_percent,
        included_adults=data.included_adults,
        included_children=data.included_children,
        extra_adult_rate=data.extra_adult_rate,
        extra_child_rate=data.extra_child_rate,
    )
    db.add(plan)
    db.flush()
    for inclusion in data.inclusions:
        db.add(
            RatePlanInclusion(
                tenant_id=tenant_id,
                brand_id=default_brand_id,
                rate_plan_id=plan.id,
                inclusion_type=inclusion.inclusion_type,
                name=inclusion.name.strip(),
                price_per_night=inclusion.price_per_night,
                is_included=inclusion.is_included,
                credit_amount=inclusion.credit_amount,
                credit_scope=inclusion.credit_scope,
                qty_per_stay=inclusion.qty_per_stay,
                qty_per_night=inclusion.qty_per_night,
            )
        )
    db.commit()
    db.refresh(plan)
    return _rate_plan_to_read(db, plan)


def update_rate_plan(
    db: Session,
    tenant_id: int,
    plan_id: int,
    data: RatePlanUpdate,
) -> RatePlanRead:
    plan = _get_rate_plan(db, tenant_id, plan_id)
    payload = data.model_dump(exclude_unset=True)
    inclusions_payload = payload.pop("inclusions", None)

    if payload.get("is_default"):
        _clear_default_rate_plans(db, tenant_id, plan.room_type_id, except_id=plan.id)

    for key, value in payload.items():
        setattr(plan, key, value)

    if inclusions_payload is not None:
        for old in _list_plan_inclusions(db, plan.id):
            old.is_active = False
        for inclusion in data.inclusions or []:
            db.add(
                RatePlanInclusion(
                    tenant_id=tenant_id,
                    brand_id=plan.brand_id,
                    rate_plan_id=plan.id,
                    inclusion_type=inclusion.inclusion_type,
                    name=inclusion.name.strip(),
                    price_per_night=inclusion.price_per_night,
                    is_included=inclusion.is_included,
                    credit_amount=inclusion.credit_amount,
                    credit_scope=inclusion.credit_scope,
                    qty_per_stay=inclusion.qty_per_stay,
                    qty_per_night=inclusion.qty_per_night,
                )
            )

    db.commit()
    db.refresh(plan)
    return _rate_plan_to_read(db, plan)


def deactivate_rate_plan(db: Session, tenant_id: int, plan_id: int) -> None:
    plan = _get_rate_plan(db, tenant_id, plan_id)
    plan.is_active = False
    if plan.is_default:
        plan.is_default = False
    db.commit()


def list_rate_plan_inclusions(
    db: Session,
    tenant_id: int,
    plan_id: int,
) -> list[RatePlanInclusionRead]:
    _get_rate_plan(db, tenant_id, plan_id)
    return [_inclusion_to_read(item) for item in _list_plan_inclusions(db, plan_id)]


def create_rate_plan_inclusion(
    db: Session,
    tenant_id: int,
    plan_id: int,
    data: RatePlanInclusionCreate,
    default_brand_id: int | None = None,
) -> RatePlanInclusionRead:
    plan = _get_rate_plan(db, tenant_id, plan_id)
    inclusion = RatePlanInclusion(
        tenant_id=tenant_id,
        brand_id=plan.brand_id or default_brand_id,
        rate_plan_id=plan.id,
        inclusion_type=data.inclusion_type,
        name=data.name.strip(),
        price_per_night=data.price_per_night,
        is_included=data.is_included,
        credit_amount=data.credit_amount,
        credit_scope=data.credit_scope,
        qty_per_stay=data.qty_per_stay,
        qty_per_night=data.qty_per_night,
    )
    db.add(inclusion)
    db.commit()
    db.refresh(inclusion)
    return _inclusion_to_read(inclusion)


def deactivate_rate_plan_inclusion(
    db: Session,
    tenant_id: int,
    plan_id: int,
    inclusion_id: int,
) -> None:
    _get_rate_plan(db, tenant_id, plan_id)
    inclusion = (
        db.query(RatePlanInclusion)
        .filter(
            RatePlanInclusion.id == inclusion_id,
            RatePlanInclusion.rate_plan_id == plan_id,
            RatePlanInclusion.tenant_id == tenant_id,
            RatePlanInclusion.is_active.is_(True),
        )
        .first()
    )
    if inclusion is None:
        raise NotFoundError("Rate plan inclusion not found")
    inclusion.is_active = False
    db.commit()


def list_public_room_types(db: Session, outlet_id: int) -> list[PublicRoomTypeRead]:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    room_type_ids = (
        db.query(HotelRoom.room_type_id)
        .filter(
            HotelRoom.tenant_id == outlet.tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
            HotelRoom.room_type_id.isnot(None),
        )
        .distinct()
        .all()
    )
    ids = [row[0] for row in room_type_ids if row[0] is not None]
    if not ids:
        return []

    room_types = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(
            RoomType.tenant_id == outlet.tenant_id,
            RoomType.id.in_(ids),
            RoomType.is_active.is_(True),
        )
        .order_by(RoomType.name)
        .all()
    )
    from app.modules.housekeeping.room_catalog import serialize_room_type as _ser_rt

    result: list[PublicRoomTypeRead] = []
    for row in room_types:
        serialized = _ser_rt(row, db)
        result.append(
            PublicRoomTypeRead(
                id=row.id,
                outlet_id=outlet_id,
                name=row.name,
                description=row.description,
                base_rate=float(row.base_rate),
                max_occupancy=row.max_occupancy,
                amenities=serialized.amenities,
                amenities_list=serialized.amenities_list,
                image_url=row.image_url,
                gallery_urls=serialized.gallery_urls,
                bed_type=row.bed_type,
                room_size_sqft=row.room_size_sqft,
            )
        )
    return result


def get_public_availability(
    db: Session,
    outlet_id: int,
    check_in: date,
    check_out: date,
) -> AvailabilityResponse:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return get_availability(db, outlet.tenant_id, outlet_id, check_in, check_out, ReservationSource.DIRECT)


def list_public_addons() -> list[PublicAddonRead]:
    return [
        PublicAddonRead(
            code=item.code,
            name=item.name,
            description=item.description,
            price=float(item.price),
            unit=item.unit,
            max_quantity=item.max_quantity,
        )
        for item in DEFAULT_PUBLIC_ADDONS
    ]


def _addon_lines_to_read(raw: str | None) -> list[PublicAddonLineRead]:
    rows = parse_addon_lines(raw)
    result: list[PublicAddonLineRead] = []
    for row in rows:
        try:
            result.append(
                PublicAddonLineRead(
                    code=str(row.get("code") or ""),
                    name=str(row.get("name") or ""),
                    unit=str(row.get("unit") or ""),
                    unit_price=float(row.get("unit_price") or 0),
                    quantity=int(row.get("quantity") or 0),
                    nights=int(row.get("nights") or 0),
                    total=float(row.get("total") or 0),
                    description=str(row.get("description") or ""),
                )
            )
        except (TypeError, ValueError):
            continue
    return result


def _apply_public_addons(
    db: Session,
    reservation: GuestReservation,
    *,
    selections: list | None,
    nights: int,
    adults: int,
    children: int,
    posted_by: int | None,
) -> tuple[list, float]:
    lines = resolve_addon_lines(
        [item.model_dump() if hasattr(item, "model_dump") else dict(item) for item in (selections or [])],
        nights=nights,
        adults=adults,
        children=children,
    )
    if not lines:
        return [], 0.0

    total = addon_total(lines)
    reservation.addons_json = dump_addon_lines(lines)
    reservation.total_amount = round(float(reservation.total_amount or 0) + total, 2)
    summary = ", ".join(f"{line.name}×{line.quantity}" for line in lines)
    reservation.notes = (
        (reservation.notes or "") + f"\nAdd-ons: {summary}"
    ).strip()

    folio = _ensure_folio(db, reservation)
    for line in lines:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.POS_CHARGE,
            line.description,
            line.total,
            posted_by=posted_by,
        )
    db.flush()
    return lines, total


async def submit_public_reservation(
    db: Session,
    data: PublicReservationCreate,
) -> PublicReservationResponse:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    admin = (
        db.query(User)
        .filter(User.tenant_id == outlet.tenant_id, User.is_super_admin.is_(True))
        .first()
    )
    if admin is None:
        admin = (
            db.query(User)
            .filter(User.tenant_id == outlet.tenant_id, User.is_active.is_(True))
            .first()
        )
    if admin is None:
        raise ConflictError("Property is not configured for online room bookings")

    notes = data.notes or "Online room booking request"
    if data.notes and "online" not in data.notes.lower():
        notes = f"{data.notes} (online booking)"

    payload = ReservationCreate(
        outlet_id=data.outlet_id,
        guest_name=data.guest_name,
        guest_email=data.guest_email,
        guest_mobile=data.guest_mobile,
        room_type_id=data.room_type_id,
        check_in_date=data.check_in_date,
        check_out_date=data.check_out_date,
        adults=data.adults,
        children=data.children,
        source=ReservationSource.DIRECT,
        rate_per_night=0,
        notes=notes,
        auto_confirm=False,
    )
    created = create_reservation(db, outlet.tenant_id, admin.id, payload, default_brand_id=outlet.brand_id)
    nights = max((data.check_out_date - data.check_in_date).days, 0)

    entity = (
        db.query(GuestReservation)
        .filter(GuestReservation.id == created.id, GuestReservation.tenant_id == outlet.tenant_id)
        .first()
    )
    addon_lines: list = []
    addons_sum = 0.0
    room_total = float(created.total_amount or 0)
    if entity is not None:
        addon_lines, addons_sum = _apply_public_addons(
            db,
            entity,
            selections=data.addons,
            nights=nights,
            adults=data.adults,
            children=data.children,
            posted_by=admin.id,
        )
        db.commit()
        db.refresh(entity)
        created = _reservation_to_read(db, entity)

    hold_message = ""
    if data.card_last4:
        try:
            hold_amount = data.hold_amount
            if hold_amount is None and float(created.total_amount or 0) > 0:
                hold_amount = round(float(created.total_amount) * 0.2, 2)

            gateway_note = "Online booking card guarantee"
            if data.payment_provider and hold_amount:
                from app.modules.payments import service as payments_service
                from app.modules.payments.models import PaymentProvider
                from app.modules.payments.schemas import OnlineCheckoutCreate

                try:
                    provider = PaymentProvider(data.payment_provider.lower())
                except ValueError as exc:
                    raise ConflictError("Unsupported payment gateway") from exc

                charge = await payments_service.create_online_checkout_charge(
                    db,
                    OnlineCheckoutCreate(
                        outlet_id=data.outlet_id,
                        provider=provider,
                        amount=float(hold_amount),
                        order_id=f"ROOM-{created.confirmation_number}",
                        purpose="room_hold",
                        customer_name=data.guest_name,
                        customer_email=data.guest_email,
                        customer_phone=data.guest_mobile,
                        card_last4=data.card_last4,
                    ),
                )
                gateway_note = (
                    f"Online booking via {provider.value} · "
                    f"{charge.provider_payment_id or charge.provider_order_id}"
                )

            created = place_card_hold(
                db,
                outlet.tenant_id,
                created.id,
                CardHoldRequest(
                    amount=hold_amount,
                    card_last4=data.card_last4,
                    hold_days=data.hold_days,
                    notes=gateway_note,
                ),
            )
            # Guaranteed online stays auto-confirm — pending queue is for unpaid requests.
            created = confirm_reservation(db, outlet.tenant_id, created.id)
            hold_message = (
                f" A card hold of {float(created.deposit_amount or 0):.2f} "
                f"was authorized (····{data.card_last4}) and your stay is confirmed."
            )
        except ConflictError:
            cancel_reservation(
                db,
                outlet.tenant_id,
                created.id,
                CancelReservationRequest(reason="Card authorization declined on online booking"),
            )
            raise

    refreshed = get_reservation(db, outlet.tenant_id, created.id)
    if refreshed.status == ReservationStatus.CONFIRMED:
        message = (
            "Thank you! Your stay is confirmed."
            + (hold_message or " We look forward to welcoming you.")
        )
    else:
        message = (
            "Thank you! Your stay request has been received. "
            "Our front desk team will confirm your reservation shortly. "
            "Add a card guarantee anytime under Pay / My booking to confirm instantly."
            + hold_message
        )

    addon_reads = [
        PublicAddonLineRead(
            code=line.code,
            name=line.name,
            unit=line.unit,
            unit_price=line.unit_price,
            quantity=line.quantity,
            nights=line.nights,
            total=line.total,
            description=line.description,
        )
        for line in addon_lines
    ]
    if not addon_reads and entity is not None:
        addon_reads = _addon_lines_to_read(entity.addons_json)
        addons_sum = round(sum(item.total for item in addon_reads), 2)

    return PublicReservationResponse(
        reservation_id=refreshed.id,
        confirmation_number=refreshed.confirmation_number,
        message=message,
        status=refreshed.status,
        total_amount=refreshed.total_amount,
        nights=nights,
        deposit_status=refreshed.deposit_status.value if refreshed.deposit_status else None,
        deposit_amount=float(refreshed.deposit_amount) if refreshed.deposit_amount is not None else None,
        payment_hold_ref=refreshed.payment_hold_ref,
        card_last4=refreshed.card_last4,
        hold_expires_at=refreshed.hold_expires_at,
        guarantee_type=refreshed.guarantee_type.value if refreshed.guarantee_type else None,
        addons=addon_reads,
        addons_total=addons_sum,
        room_total=room_total,
    )


def _normalize_guest_mobile(value: str) -> str:
    return "".join(ch for ch in (value or "") if ch.isdigit())


def _mobiles_match(stored: str, provided: str) -> bool:
    left = _normalize_guest_mobile(stored)
    right = _normalize_guest_mobile(provided)
    if not left or not right:
        return False
    if left == right:
        return True
    return len(left) >= 10 and len(right) >= 10 and left[-10:] == right[-10:]


def _find_public_reservation(
    db: Session,
    *,
    confirmation_number: str,
    guest_mobile: str,
) -> GuestReservation:
    conf = confirmation_number.strip().upper()
    if len(_normalize_guest_mobile(guest_mobile)) < 6:
        raise NotFoundError("Booking not found")

    reservation = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.confirmation_number == conf,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )
    if reservation is None:
        raise NotFoundError("Booking not found")
    if not _mobiles_match(reservation.guest_mobile, guest_mobile):
        raise NotFoundError("Booking not found")
    return reservation


def _public_reservation_status(
    db: Session,
    reservation: GuestReservation,
    *,
    message: str | None = None,
) -> PublicReservationStatus:
    outlet = db.get(Outlet, reservation.outlet_id)
    room_type = db.get(RoomType, reservation.room_type_id)
    room = db.get(HotelRoom, reservation.room_id) if reservation.room_id else None
    rate_plan = db.get(RatePlan, reservation.rate_plan_id) if reservation.rate_plan_id else None
    nights = max((reservation.check_out_date - reservation.check_in_date).days, 0)
    can_hold = reservation.status in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    } and reservation.deposit_status not in {
        DepositStatus.HELD,
        DepositStatus.CAPTURED,
        DepositStatus.FORFEITED,
        DepositStatus.REFUNDED,
    }
    can_cancel = reservation.status in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    }
    can_modify_stay = can_cancel
    can_request_early_check_in = (
        can_cancel
        and not bool(reservation.early_check_in)
    )
    can_request_late_check_out = (
        reservation.status
        in {
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }
        and not bool(reservation.late_check_out)
        and not bool(reservation.day_use)
    )
    can_add_special_request = reservation.status in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
        ReservationStatus.CHECKED_IN,
    }
    pre_status = getattr(reservation, "pre_check_in_status", None) or PreCheckInStatus.NONE.value
    can_pre_check_in = (
        reservation.status in {ReservationStatus.PENDING, ReservationStatus.CONFIRMED}
        and pre_status != PreCheckInStatus.REVIEWED.value
    )
    special_requests = _parse_guest_special_requests(reservation.notes)
    feedback_rating, feedback_comment = _parse_guest_feedback(reservation.notes)
    can_submit_feedback = (
        reservation.status == ReservationStatus.CHECKED_OUT and feedback_rating is None
    )
    folio = (
        db.query(GuestFolio)
        .filter(
            GuestFolio.reservation_id == reservation.id,
            GuestFolio.is_active.is_(True),
        )
        .first()
    )
    status_message = message or {
        ReservationStatus.PENDING: "Your request is awaiting front-desk confirmation.",
        ReservationStatus.CONFIRMED: "Your stay is confirmed.",
        ReservationStatus.CHECKED_IN: "You are currently checked in.",
        ReservationStatus.CHECKED_OUT: "This stay has been completed.",
        ReservationStatus.CANCELLED: "This booking was cancelled.",
        ReservationStatus.NO_SHOW: "This booking was marked as no-show.",
    }.get(reservation.status, "Booking found.")

    outlet_name = None
    if outlet is not None:
        outlet_name = getattr(outlet, "outlet_name", None) or getattr(outlet, "name", None)

    return PublicReservationStatus(
        confirmation_number=reservation.confirmation_number,
        guest_name=reservation.guest_name,
        guest_mobile=reservation.guest_mobile,
        guest_email=reservation.guest_email,
        outlet_id=reservation.outlet_id,
        outlet_name=outlet_name,
        room_type_name=room_type.name if room_type else None,
        room_number=room.room_number if room else None,
        check_in_date=reservation.check_in_date,
        check_out_date=reservation.check_out_date,
        nights=nights,
        adults=reservation.adults,
        children=reservation.children,
        status=reservation.status,
        total_amount=float(reservation.total_amount or 0),
        rate_per_night=float(reservation.rate_per_night or 0),
        rate_plan_name=rate_plan.name if rate_plan else None,
        deposit_status=reservation.deposit_status.value if reservation.deposit_status else None,
        deposit_amount=float(reservation.deposit_amount) if reservation.deposit_amount is not None else None,
        payment_hold_ref=reservation.payment_hold_ref,
        card_last4=reservation.card_last4,
        hold_expires_at=reservation.hold_expires_at,
        guarantee_type=reservation.guarantee_type.value if reservation.guarantee_type else None,
        can_place_hold=can_hold,
        can_cancel=can_cancel,
        can_modify_stay=can_modify_stay,
        early_check_in=bool(reservation.early_check_in),
        late_check_out=bool(reservation.late_check_out),
        day_use=bool(reservation.day_use),
        can_request_early_check_in=can_request_early_check_in,
        can_request_late_check_out=can_request_late_check_out,
        can_add_special_request=can_add_special_request,
        special_requests=special_requests,
        can_submit_feedback=can_submit_feedback,
        feedback_rating=feedback_rating,
        feedback_comment=feedback_comment,
        folio_number=folio.folio_number if folio else None,
        folio_balance=float(folio.balance) if folio else None,
        has_folio=folio is not None,
        can_email_folio=folio is not None and bool((reservation.guest_email or "").strip()),
        addons=_addon_lines_to_read(getattr(reservation, "addons_json", None)),
        addons_total=round(
            sum(item.total for item in _addon_lines_to_read(getattr(reservation, "addons_json", None))),
            2,
        ),
        can_pre_check_in=can_pre_check_in,
        pre_check_in_status=pre_status,
        pre_check_in_at=getattr(reservation, "pre_check_in_at", None),
        guest_id_document=reservation.guest_id_document,
        guest_id_document_type=getattr(reservation, "guest_id_document_type", None),
        estimated_arrival_time=getattr(reservation, "estimated_arrival_time", None),
        pre_check_in_notes=getattr(reservation, "pre_check_in_notes", None),
        message=status_message,
    )


def submit_public_pre_check_in(
    db: Session,
    data: PublicPreCheckInRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status not in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    }:
        raise ConflictError("Pre-check-in is only available before arrival check-in")
    current = getattr(reservation, "pre_check_in_status", None) or PreCheckInStatus.NONE.value
    if current == PreCheckInStatus.REVIEWED.value:
        raise ConflictError("Front desk has already reviewed your pre-check-in")

    doc_type = data.guest_id_document_type.strip().lower().replace(" ", "_")
    allowed_types = {"passport", "aadhaar", "dl", "voter_id", "other"}
    if doc_type not in allowed_types:
        raise ConflictError("Unsupported ID document type")

    if data.guest_name:
        reservation.guest_name = data.guest_name.strip()
    if data.guest_email is not None:
        reservation.guest_email = (data.guest_email or "").strip() or None
    if data.adults is not None:
        reservation.adults = data.adults
    if data.children is not None:
        reservation.children = data.children
    if data.early_check_in is True:
        reservation.early_check_in = True

    reservation.guest_id_document_type = doc_type
    reservation.guest_id_document = data.guest_id_document.strip()
    reservation.estimated_arrival_time = (
        data.estimated_arrival_time.strip() if data.estimated_arrival_time else None
    )
    reservation.pre_check_in_notes = data.notes.strip() if data.notes else None
    reservation.pre_check_in_status = PreCheckInStatus.SUBMITTED.value
    reservation.pre_check_in_at = datetime.utcnow()

    room_type = _get_room_type(db, reservation.tenant_id, reservation.room_type_id)
    _assert_party_fits_room_type(room_type, reservation.adults, reservation.children)

    db.commit()
    db.refresh(reservation)
    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Pre-check-in received. Present the same ID at the front desk on arrival.",
    )


def review_pre_check_in(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: PreCheckInReviewRequest | None = None,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    current = getattr(reservation, "pre_check_in_status", None) or PreCheckInStatus.NONE.value
    if current != PreCheckInStatus.SUBMITTED.value:
        raise ConflictError("No submitted pre-check-in to review")
    reservation.pre_check_in_status = PreCheckInStatus.REVIEWED.value
    reservation.pre_check_in_reviewed_at = datetime.utcnow()
    if data and data.notes:
        note_line = f"Pre-check-in reviewed: {data.notes.strip()}"
        existing = (reservation.notes or "").strip()
        reservation.notes = f"{existing}\n{note_line}".strip() if existing else note_line
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def lookup_public_reservation(
    db: Session,
    confirmation_number: str,
    guest_mobile: str,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=confirmation_number,
        guest_mobile=guest_mobile,
    )
    return _public_reservation_status(db, reservation)


def place_public_card_hold(
    db: Session,
    data: PublicCardHoldCreate,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status in {
        ReservationStatus.CANCELLED,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.NO_SHOW,
    }:
        raise ConflictError("Cannot place a card hold on this booking")

    place_card_hold(
        db,
        reservation.tenant_id,
        reservation.id,
        CardHoldRequest(
            amount=data.hold_amount,
            card_last4=data.card_last4,
            hold_days=data.hold_days,
            notes="Guest portal card guarantee",
        ),
    )
    # Auto-confirm pending stays once a guarantee hold is in place.
    entity = _get_reservation(db, reservation.tenant_id, reservation.id)
    if entity.status == ReservationStatus.PENDING:
        confirm_reservation(db, reservation.tenant_id, reservation.id)

    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Card hold authorized and your stay is confirmed.",
    )


def cancel_public_reservation(
    db: Session,
    data: PublicCancelRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status not in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    }:
        raise ConflictError("This booking can no longer be cancelled online")

    cancel_reservation(
        db,
        reservation.tenant_id,
        reservation.id,
        CancelReservationRequest(
            reason=data.reason or "Cancelled by guest via booking portal",
        ),
    )
    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Your booking has been cancelled. Any card hold was released.",
    )


def modify_public_reservation(
    db: Session,
    data: PublicModifyStayRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status not in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
    }:
        raise ConflictError("This booking can no longer be modified online")

    payload: dict = {}
    if data.check_in_date is not None:
        payload["check_in_date"] = data.check_in_date
    if data.check_out_date is not None:
        payload["check_out_date"] = data.check_out_date
    if data.adults is not None:
        payload["adults"] = data.adults
    if data.children is not None:
        payload["children"] = data.children

    if not payload:
        raise ConflictError("Provide at least one stay change (dates or guest count)")

    new_check_in = payload.get("check_in_date", reservation.check_in_date)
    new_check_out = payload.get("check_out_date", reservation.check_out_date)
    if new_check_out <= new_check_in and not reservation.day_use:
        raise ConflictError("check_out_date must be after check_in_date")

    previous = (
        f"{reservation.check_in_date.isoformat()}→{reservation.check_out_date.isoformat()} "
        f"({reservation.adults}A/{reservation.children}C)"
    )
    update_reservation(
        db,
        reservation.tenant_id,
        reservation.id,
        ReservationUpdate(**payload),
    )
    entity = _get_reservation(db, reservation.tenant_id, reservation.id)
    updated = (
        f"{entity.check_in_date.isoformat()}→{entity.check_out_date.isoformat()} "
        f"({entity.adults}A/{entity.children}C)"
    )
    note_bits = [f"Guest portal stay change: {previous} → {updated}"]
    if data.note:
        note_bits.append(data.note.strip())
    entity.notes = ((entity.notes or "").rstrip() + "\n" + " | ".join(note_bits)).strip()
    db.commit()

    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Your stay was updated. The folio total reflects the new dates.",
    )


def modify_public_stay_modifiers(
    db: Session,
    data: PublicStayModifiersRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    want_early = data.early_check_in is True
    want_late = data.late_check_out is True
    if not want_early and not want_late:
        raise ConflictError("Request early check-in and/or late check-out")
    if data.early_check_in is False or data.late_check_out is False:
        raise ConflictError("Stay modifiers can only be requested, not cleared, online")

    if want_early:
        if reservation.status not in {
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
        }:
            raise ConflictError("Early check-in can only be requested before arrival")
        if reservation.early_check_in:
            raise ConflictError("Early check-in is already on this booking")

    if want_late:
        if reservation.status not in {
            ReservationStatus.PENDING,
            ReservationStatus.CONFIRMED,
            ReservationStatus.CHECKED_IN,
        }:
            raise ConflictError("Late check-out is not available for this booking")
        if reservation.day_use:
            raise ConflictError("Late check-out is not available for day-use stays")
        if reservation.late_check_out:
            raise ConflictError("Late check-out is already on this booking")

    user_id = _get_system_user_id(db, reservation.tenant_id)
    if user_id is None:
        raise ConflictError("Property is not configured to update stay options")

    mods: dict[str, bool] = {}
    if want_early:
        mods["early_check_in"] = True
    if want_late:
        mods["late_check_out"] = True
    apply_stay_modifiers(
        db,
        reservation.tenant_id,
        user_id,
        reservation.id,
        StayModifierUpdate(**mods),
    )
    entity = _get_reservation(db, reservation.tenant_id, reservation.id)
    bits: list[str] = []
    if want_early:
        bits.append("early check-in")
    if want_late:
        bits.append("late check-out")
    note_line = f"Guest portal requested: {', '.join(bits)}"
    if data.note:
        note_line += f" — {data.note.strip()}"
    entity.notes = ((entity.notes or "").rstrip() + "\n" + note_line).strip()
    db.commit()

    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    label = " and ".join(bits)
    return _public_reservation_status(
        db,
        refreshed,
        message=f"Requested {label}. Front desk has been notified via your booking notes"
        + ("; late check-out may add a half-night charge." if want_late else "."),
    )


def add_public_special_request(
    db: Session,
    data: PublicSpecialRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status not in {
        ReservationStatus.PENDING,
        ReservationStatus.CONFIRMED,
        ReservationStatus.CHECKED_IN,
    }:
        raise ConflictError("Special requests can no longer be added for this booking")

    text = " ".join(data.request.split()).strip()
    if len(text) < 3:
        raise ConflictError("Please provide a more detailed request")

    existing = _parse_guest_special_requests(reservation.notes)
    if text.lower() in {e.lower() for e in existing}:
        raise ConflictError("That special request is already on this booking")
    if len(existing) >= 10:
        raise ConflictError("Maximum special requests reached for this booking")

    line = f"{GUEST_SPECIAL_REQUEST_PREFIX} {text}"
    reservation.notes = ((reservation.notes or "").rstrip() + "\n" + line).strip()
    db.commit()

    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Special request noted. Front desk will see it on your booking.",
    )


def submit_public_stay_feedback(
    db: Session,
    data: PublicStayFeedbackRequest,
) -> PublicReservationStatus:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    if reservation.status != ReservationStatus.CHECKED_OUT:
        raise ConflictError("Feedback is available after checkout")

    existing_rating, _ = _parse_guest_feedback(reservation.notes)
    if existing_rating is not None:
        raise ConflictError("Feedback was already submitted for this stay")

    comment = " ".join((data.comment or "").split()).strip() or None
    line = f"{GUEST_FEEDBACK_PREFIX} {data.rating}/5"
    if comment:
        line = f"{line} — {comment}"
    reservation.notes = ((reservation.notes or "").rstrip() + "\n" + line).strip()
    db.commit()

    refreshed = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    return _public_reservation_status(
        db,
        refreshed,
        message="Thank you for your feedback. We appreciate you staying with us.",
    )


def build_public_folio_pdf(
    db: Session,
    confirmation_number: str,
    guest_mobile: str,
) -> tuple[bytes, str]:
    reservation = _find_public_reservation(
        db,
        confirmation_number=confirmation_number,
        guest_mobile=guest_mobile,
    )
    return build_folio_pdf(db, reservation.tenant_id, reservation.id)


async def email_public_folio_statement(
    db: Session,
    data: PublicFolioEmailRequest,
) -> FolioEmailResponse:
    reservation = _find_public_reservation(
        db,
        confirmation_number=data.confirmation_number,
        guest_mobile=data.guest_mobile,
    )
    user_id = _get_system_user_id(db, reservation.tenant_id)
    if user_id is None:
        raise ConflictError("Property is not configured to email folio statements")

    return await email_folio_statement(
        db,
        reservation.tenant_id,
        user_id,
        reservation.id,
        FolioEmailRequest(
            to_email=data.to_email,
            note=data.note or "Requested by guest via booking portal",
        ),
    )


def _format_stay_dates(check_in: date, check_out: date) -> str:
    return f"{check_in.strftime('%d %b %Y')} → {check_out.strftime('%d %b %Y')}"


def _build_reservation_notification_message(
    reservation: GuestReservation,
    outlet_name: str,
    *,
    room_type_name: str | None,
    kind: PmsNotificationKind,
) -> tuple[str, str]:
    stay = _format_stay_dates(reservation.check_in_date, reservation.check_out_date)
    room_line = f"\nRoom type: {room_type_name}" if room_type_name else ""
    guests_line = f"Guests: {reservation.adults} adult(s)"
    if reservation.children:
        guests_line += f", {reservation.children} child(ren)"
    amount_line = f"\nEstimated total: ₹{float(reservation.total_amount):,.0f}"

    if kind == PmsNotificationKind.REQUEST_RECEIVED:
        body = (
            f"Hi {reservation.guest_name}!\n\n"
            f"We received your stay request at {outlet_name} for {stay} "
            f"(Ref: {reservation.confirmation_number}).{room_line}\n"
            f"{guests_line}.{amount_line}\n"
            f"Our front desk team will confirm your reservation shortly."
        )
        subject = f"Stay request received — {reservation.confirmation_number}"
    elif kind == PmsNotificationKind.REMINDER:
        body = (
            f"Hi {reservation.guest_name}! 👋\n\n"
            f"Reminder: your stay at {outlet_name} is scheduled for {stay} "
            f"(Ref: {reservation.confirmation_number}).{room_line}\n"
            f"{guests_line}.\n"
            f"We look forward to welcoming you!"
        )
        subject = f"Reminder: upcoming stay — {reservation.confirmation_number}"
    elif kind == PmsNotificationKind.THANK_YOU:
        body = (
            f"Hi {reservation.guest_name}!\n\n"
            f"Thank you for staying with us at {outlet_name} "
            f"(Ref: {reservation.confirmation_number}).{room_line}\n"
            f"We hope you enjoyed your visit. You can leave a quick rating "
            f"in the guest portal under My booking.\n"
            f"We would love to welcome you again soon."
        )
        subject = f"Thank you for your stay — {reservation.confirmation_number}"
    elif kind == PmsNotificationKind.CANCELLATION:
        body = (
            f"Hi {reservation.guest_name},\n\n"
            f"Your stay at {outlet_name} for {stay} "
            f"(Ref: {reservation.confirmation_number}) has been cancelled.{room_line}\n"
            f"If this was unexpected, please contact the front desk."
        )
        subject = f"Booking cancelled — {reservation.confirmation_number}"
    else:
        body = (
            f"Hi {reservation.guest_name}! ✨\n\n"
            f"Your stay at {outlet_name} is confirmed for {stay} "
            f"(Ref: {reservation.confirmation_number}).{room_line}\n"
            f"{guests_line}.{amount_line}\n"
            f"See you soon!"
        )
        subject = f"Confirmed: your stay — {reservation.confirmation_number}"
    return body, subject


async def send_reservation_notifications(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    *,
    kind: PmsNotificationKind,
    send_sms: bool = False,
    send_email: bool = False,
    send_whatsapp: bool = False,
) -> PmsNotificationResponse:
    from app.modules.communications import service as comms_service
    from app.modules.communications.models import MessageChannel
    from app.modules.communications.schemas import EmailSendRequest, SmsSendRequest, WhatsAppSendRequest

    if not send_sms and not send_email and not send_whatsapp:
        raise ConflictError("Select at least one notification channel")

    reservation = _get_reservation(db, tenant_id, reservation_id)
    outlet = _get_outlet(db, tenant_id, reservation.outlet_id)
    room_type = db.get(RoomType, reservation.room_type_id)
    body, subject = _build_reservation_notification_message(
        reservation,
        outlet.outlet_name,
        room_type_name=room_type.name if room_type else None,
        kind=kind,
    )
    sent_channels: list[str] = []

    if send_sms and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.SMS, brand_id=reservation.brand_id, outlet_id=reservation.outlet_id
    ):
        await comms_service.send_mock_sms(
            db,
            tenant_id,
            user_id,
            SmsSendRequest(
                receiver=reservation.guest_mobile,
                message_text=body,
                outlet_id=reservation.outlet_id,
                customer_id=reservation.customer_id,
                brand_id=reservation.brand_id,
            ),
            default_brand_id=reservation.brand_id,
        )
        sent_channels.append("sms")

    if send_whatsapp and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.WHATSAPP, brand_id=reservation.brand_id, outlet_id=reservation.outlet_id
    ):
        await comms_service.send_mock_whatsapp(
            db,
            tenant_id,
            user_id,
            WhatsAppSendRequest(
                receiver=reservation.guest_mobile,
                message_text=body,
                outlet_id=reservation.outlet_id,
                customer_id=reservation.customer_id,
                brand_id=reservation.brand_id,
            ),
            default_brand_id=reservation.brand_id,
        )
        sent_channels.append("whatsapp")

    if send_email and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.EMAIL, brand_id=reservation.brand_id, outlet_id=reservation.outlet_id
    ):
        if not reservation.guest_email:
            raise ConflictError("Guest email is required to send email")
        await comms_service.send_mock_email(
            db,
            tenant_id,
            user_id,
            EmailSendRequest(
                receiver=reservation.guest_email,
                subject=subject,
                message_text=body,
                outlet_id=reservation.outlet_id,
                customer_id=reservation.customer_id,
                brand_id=reservation.brand_id,
            ),
            default_brand_id=reservation.brand_id,
        )
        sent_channels.append("email")

    if not sent_channels:
        raise ConflictError("No notification channels are enabled for this outlet")

    db.commit()
    return PmsNotificationResponse(
        message=f"Notification sent via {', '.join(sent_channels)}",
        reservation_id=reservation.id,
        sent_channels=sent_channels,
        message_preview=body,
    )


async def send_public_reservation_acknowledgment(
    db: Session,
    tenant_id: int,
    reservation_id: int,
) -> PmsNotificationResponse | None:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    send_sms = bool(reservation.guest_mobile)
    send_email = bool(reservation.guest_email)
    send_whatsapp = bool(reservation.guest_mobile)
    if not send_sms and not send_email and not send_whatsapp:
        return None

    admin = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_super_admin.is_(True))
        .first()
    )
    if admin is None:
        admin = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
            .first()
        )
    if admin is None:
        return None

    return await send_reservation_notifications(
        db,
        tenant_id,
        admin.id,
        reservation_id,
        kind=PmsNotificationKind.REQUEST_RECEIVED,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )


def build_reservation_automation_payload(reservation: ReservationRead) -> dict:
    return {
        "reservation_id": reservation.id,
        "confirmation_number": reservation.confirmation_number,
        "guest_name": reservation.guest_name,
        "guest_mobile": reservation.guest_mobile,
        "guest_email": reservation.guest_email,
        "room_type_name": reservation.room_type_name,
        "room_type_id": reservation.room_type_id,
        "check_in_date": reservation.check_in_date.isoformat(),
        "check_out_date": reservation.check_out_date.isoformat(),
        "outlet_id": reservation.outlet_id,
        "status": reservation.status.value if hasattr(reservation.status, "value") else reservation.status,
        "total_amount": reservation.total_amount,
    }


DEFAULT_CHECK_IN_TIME = time(14, 0)


def _reservation_check_in_datetime(reservation: GuestReservation) -> datetime:
    return datetime.combine(reservation.check_in_date, DEFAULT_CHECK_IN_TIME)


async def _send_reservation_reminder(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    *,
    config: dict | None = None,
) -> bool:
    from app.modules.settings.service import get_pms_reminder_config

    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.reminder_sent_at is not None:
        return False
    if reservation.status != ReservationStatus.CONFIRMED:
        return False

    reminder_config = config or get_pms_reminder_config(db, tenant_id, reservation.outlet_id)
    if not reminder_config.get("enabled", True):
        return False

    user_id = _get_system_user_id(db, tenant_id)
    if user_id is None:
        return False

    send_sms = reminder_config.get("send_sms", True) and bool(reservation.guest_mobile)
    send_email = reminder_config.get("send_email", True) and bool(reservation.guest_email)
    send_whatsapp = reminder_config.get("send_whatsapp", True) and bool(reservation.guest_mobile)
    if not send_sms and not send_email and not send_whatsapp:
        return False

    await send_reservation_notifications(
        db,
        tenant_id,
        user_id,
        reservation_id,
        kind=PmsNotificationKind.REMINDER,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )
    reservation.reminder_sent_at = datetime.utcnow()
    db.commit()
    return True


def _get_system_user_id(db: Session, tenant_id: int) -> int | None:
    admin = (
        db.query(User)
        .filter(User.tenant_id == tenant_id, User.is_super_admin.is_(True))
        .first()
    )
    if admin is None:
        admin = (
            db.query(User)
            .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
            .first()
        )
    return admin.id if admin else None


def _is_reservation_due(
    reservation: GuestReservation,
    *,
    now: datetime,
    hours_before: int,
    window_minutes: int,
) -> bool:
    target = _reservation_check_in_datetime(reservation)
    window_start = now + timedelta(hours=hours_before) - timedelta(minutes=window_minutes)
    window_end = now + timedelta(hours=hours_before) + timedelta(minutes=window_minutes)
    return window_start <= target <= window_end


def run_due_pms_reminders_all_tenants(
    db: Session,
    *,
    hours_before: int | None = None,
    window_minutes: int | None = None,
) -> PmsReminderBatchResult:
    import asyncio

    from app.core.config import settings
    from app.modules.settings.service import get_pms_reminder_config
    from app.modules.tenants.models import Tenant

    default_hours = hours_before if hours_before is not None else settings.pms_reminder_hours_before
    default_window = window_minutes if window_minutes is not None else settings.pms_reminder_window_minutes
    now = datetime.utcnow()
    max_scan_hours = 168 if hours_before is None else default_hours + 1
    scan_start = (now - timedelta(minutes=default_window + 30)).date()
    scan_end = (now + timedelta(hours=max_scan_hours) + timedelta(minutes=default_window + 30)).date()

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    reminders_sent = 0
    reservations_checked = 0
    config_cache: dict[tuple[int, int], dict] = {}

    for tenant in tenants:
        reservations = (
            db.query(GuestReservation)
            .filter(
                GuestReservation.tenant_id == tenant.id,
                GuestReservation.is_active.is_(True),
                GuestReservation.status == ReservationStatus.CONFIRMED,
                GuestReservation.reminder_sent_at.is_(None),
                GuestReservation.check_in_date >= scan_start,
                GuestReservation.check_in_date <= scan_end,
            )
            .all()
        )
        for reservation in reservations:
            cache_key = (tenant.id, reservation.outlet_id)
            if cache_key not in config_cache:
                config_cache[cache_key] = get_pms_reminder_config(db, tenant.id, reservation.outlet_id)
            reminder_config = config_cache[cache_key]
            if not reminder_config.get("enabled", True):
                continue

            outlet_hours = (
                hours_before
                if hours_before is not None
                else int(reminder_config.get("hours_before", default_hours))
            )
            outlet_window = (
                window_minutes
                if window_minutes is not None
                else int(reminder_config.get("window_minutes", default_window))
            )
            if not _is_reservation_due(
                reservation,
                now=now,
                hours_before=outlet_hours,
                window_minutes=outlet_window,
            ):
                continue

            reservations_checked += 1
            try:
                sent = asyncio.run(
                    _send_reservation_reminder(
                        db,
                        tenant.id,
                        reservation.id,
                        config=reminder_config,
                    )
                )
                if sent:
                    reminders_sent += 1
            except Exception:
                db.rollback()
                continue

    return PmsReminderBatchResult(
        message=f"PMS pre-arrival reminders sent: {reminders_sent}",
        reminders_sent=reminders_sent,
        tenants_processed=len(tenants),
        reservations_checked=reservations_checked,
    )

# ── Tape chart / assign / walk-in / room blocks / move / groups ───────────────


def get_tape_chart(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    from_date: date,
    to_date: date,
) -> TapeChartResponse:
    _get_outlet(db, tenant_id, outlet_id)
    if to_date <= from_date:
        raise ConflictError("to_date must be after from_date")

    rooms = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
        )
        .order_by(HotelRoom.room_number)
        .all()
    )
    room_type_names = {
        rt.id: rt.name
        for rt in db.query(RoomType).filter(RoomType.tenant_id == tenant_id).all()
    }

    display_statuses = list(ACTIVE_STATUSES | {ReservationStatus.CHECKED_OUT})
    reservations = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status.in_(display_statuses),
            GuestReservation.room_id.isnot(None),
            GuestReservation.check_in_date < to_date,
            GuestReservation.check_out_date > from_date,
        )
        .all()
    )
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.tenant_id == tenant_id,
            RoomBlock.outlet_id == outlet_id,
            RoomBlock.is_active.is_(True),
            RoomBlock.start_date < to_date,
            RoomBlock.end_date > from_date,
        )
        .all()
    )

    segments_by_room: dict[int, list[TapeChartSegment]] = {room.id: [] for room in rooms}
    for reservation in reservations:
        if reservation.room_id not in segments_by_room:
            continue
        segments_by_room[reservation.room_id].append(
            TapeChartSegment(
                kind="reservation",
                id=reservation.id,
                start_date=reservation.check_in_date,
                end_date=reservation.check_out_date,
                label=reservation.guest_name,
                status=reservation.status.value,
                guest_name=reservation.guest_name,
                confirmation_number=reservation.confirmation_number,
                reservation_id=reservation.id,
            )
        )
    for block in blocks:
        if block.room_id not in segments_by_room:
            continue
        segments_by_room[block.room_id].append(
            TapeChartSegment(
                kind="block",
                id=block.id,
                start_date=block.start_date,
                end_date=block.end_date,
                label=block.reason or block.block_type.value,
                block_type=block.block_type,
            )
        )

    rows = [
        TapeChartRoomRow(
            room_id=room.id,
            room_number=room.room_number,
            room_type_id=room.room_type_id,
            room_type_name=room_type_names.get(room.room_type_id),
            hk_status=room.status.value if hasattr(room.status, "value") else str(room.status),
            segments=sorted(segments_by_room[room.id], key=lambda s: s.start_date),
        )
        for room in rooms
    ]
    return TapeChartResponse(
        outlet_id=outlet_id,
        from_date=from_date,
        to_date=to_date,
        rooms=rows,
    )


def get_pickup_calendar(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    from_date: date,
    to_date: date,
) -> PickupCalendarResponse:
    """Per-night occupancy pickup: sold vs available inventory by date."""
    _get_outlet(db, tenant_id, outlet_id)
    if to_date < from_date:
        raise ConflictError("to_date must be on or after from_date")
    if (to_date - from_date).days > 62:
        raise ConflictError("Date range cannot exceed 62 days")

    total_rooms = (
        db.query(func.count(HotelRoom.id))
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
            HotelRoom.status.notin_([RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE]),
        )
        .scalar()
        or 0
    )

    sellable_statuses = list(ACTIVE_STATUSES | {ReservationStatus.CHECKED_OUT})
    reservations = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status.in_(sellable_statuses),
            GuestReservation.check_in_date <= to_date,
            GuestReservation.check_out_date > from_date,
        )
        .all()
    )
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.tenant_id == tenant_id,
            RoomBlock.outlet_id == outlet_id,
            RoomBlock.is_active.is_(True),
            RoomBlock.start_date <= to_date,
            RoomBlock.end_date > from_date,
        )
        .all()
    )

    days: list[PickupDay] = []
    cursor = from_date
    while cursor <= to_date:
        sold_rooms: set[int] = set()
        sold_unassigned = 0
        for reservation in reservations:
            # Night inventory: check-in inclusive, check-out exclusive
            if reservation.check_in_date <= cursor < reservation.check_out_date:
                if reservation.room_id:
                    sold_rooms.add(reservation.room_id)
                else:
                    sold_unassigned += 1

        blocked_rooms: set[int] = set()
        for block in blocks:
            if block.start_date <= cursor < block.end_date:
                blocked_rooms.add(block.room_id)

        # Don't double-count a room that is both sold and blocked
        blocked_only = len(blocked_rooms - sold_rooms)
        sold = len(sold_rooms) + sold_unassigned
        capacity = max(total_rooms, sold + blocked_only)
        available = max(capacity - sold - blocked_only, 0)
        occupancy = round((sold / capacity * 100) if capacity else 0.0, 1)

        arrivals = sum(1 for r in reservations if r.check_in_date == cursor)
        departures = sum(1 for r in reservations if r.check_out_date == cursor)

        days.append(
            PickupDay(
                date=cursor,
                total_rooms=capacity,
                sold=sold,
                blocked=blocked_only,
                available=available,
                occupancy_percent=occupancy,
                arrivals=arrivals,
                departures=departures,
            )
        )
        cursor += timedelta(days=1)

    return PickupCalendarResponse(
        outlet_id=outlet_id,
        from_date=from_date,
        to_date=to_date,
        total_rooms=total_rooms,
        days=days,
    )


def get_rate_inventory_calendar(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    from_date: date,
    to_date: date,
    source: ReservationSource | None = None,
) -> RateInventoryCalendarResponse:
    """Per room-type BAR rate + nightly sellable inventory."""
    _get_outlet(db, tenant_id, outlet_id)
    if to_date < from_date:
        raise ConflictError("to_date must be on or after from_date")
    if (to_date - from_date).days > 31:
        raise ConflictError("Date range cannot exceed 31 days")

    rooms = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
            HotelRoom.status.notin_([RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE]),
        )
        .all()
    )
    totals: dict[int, int] = {}
    room_type_ids: set[int] = set()
    room_type_by_room: dict[int, int] = {}
    for room in rooms:
        if room.room_type_id is None:
            continue
        room_type_ids.add(room.room_type_id)
        room_type_by_room[room.id] = room.room_type_id
        totals[room.room_type_id] = totals.get(room.room_type_id, 0) + 1

    room_types = (
        db.query(RoomType)
        .filter(
            RoomType.tenant_id == tenant_id,
            RoomType.id.in_(list(room_type_ids)) if room_type_ids else False,
            RoomType.is_active.is_(True),
        )
        .order_by(RoomType.name)
        .all()
        if room_type_ids
        else []
    )

    sellable_statuses = list(ACTIVE_STATUSES | {ReservationStatus.CHECKED_OUT})
    reservations = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status.in_(sellable_statuses),
            GuestReservation.check_in_date <= to_date,
            GuestReservation.check_out_date > from_date,
        )
        .all()
    )
    blocks = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.tenant_id == tenant_id,
            RoomBlock.outlet_id == outlet_id,
            RoomBlock.is_active.is_(True),
            RoomBlock.start_date <= to_date,
            RoomBlock.end_date > from_date,
        )
        .all()
    )

    rate_cache: dict[tuple[int, date], tuple[float, RatePlan | None]] = {}
    dates: list[date] = []
    cells: list[RateInventoryCell] = []
    from app.modules.settings.service import get_pms_inventory_overrides

    overrides = get_pms_inventory_overrides(db, tenant_id, outlet_id)
    cursor = from_date
    while cursor <= to_date:
        dates.append(cursor)
        sold_by_type: dict[int, int] = {}
        sold_room_ids: set[int] = set()
        for reservation in reservations:
            if reservation.check_in_date <= cursor < reservation.check_out_date:
                sold_by_type[reservation.room_type_id] = sold_by_type.get(reservation.room_type_id, 0) + 1
                if reservation.room_id:
                    sold_room_ids.add(reservation.room_id)

        blocked_by_type: dict[int, int] = {}
        for block in blocks:
            if block.start_date <= cursor < block.end_date:
                if block.room_id in sold_room_ids:
                    continue
                rt_id = room_type_by_room.get(block.room_id)
                if rt_id is None:
                    continue
                blocked_by_type[rt_id] = blocked_by_type.get(rt_id, 0) + 1

        for room_type in room_types:
            cache_key = (room_type.id, cursor)
            if cache_key not in rate_cache:
                rate_cache[cache_key] = resolve_rate(
                    db,
                    tenant_id,
                    room_type.id,
                    cursor,
                    cursor + timedelta(days=1),
                    source,
                )
            rate, plan = rate_cache[cache_key]
            total = totals.get(room_type.id, 0)
            sold = sold_by_type.get(room_type.id, 0)
            blocked = blocked_by_type.get(room_type.id, 0)
            available = max(total - sold - blocked, 0)
            override = overrides.get(f"{room_type.id}:{cursor.isoformat()}") or {}
            stop_sell = bool(override.get("stop_sell"))
            rate_overridden = "rate" in override
            cta = bool(override.get("cta"))
            ctd = bool(override.get("ctd"))
            min_stay = None
            max_stay = None
            if override.get("min_stay"):
                try:
                    min_stay = int(override["min_stay"])
                except (TypeError, ValueError):
                    min_stay = None
            if override.get("max_stay") is not None:
                try:
                    max_stay = int(override["max_stay"])
                except (TypeError, ValueError):
                    max_stay = None
            if rate_overridden:
                rate = float(override["rate"])
            if stop_sell:
                available = 0
            cells.append(
                RateInventoryCell(
                    date=cursor,
                    room_type_id=room_type.id,
                    room_type_name=room_type.name,
                    total_rooms=total,
                    sold=sold,
                    blocked=blocked,
                    available=available,
                    rate=float(rate),
                    rate_plan_id=plan.id if plan else None,
                    rate_plan_name=plan.name if plan else None,
                    rate_plan_code=plan.code if plan else None,
                    stop_sell=stop_sell,
                    rate_overridden=rate_overridden,
                    cta=cta,
                    ctd=ctd,
                    min_stay=min_stay,
                    max_stay=max_stay,
                )
            )
        cursor += timedelta(days=1)

    return RateInventoryCalendarResponse(
        outlet_id=outlet_id,
        from_date=from_date,
        to_date=to_date,
        room_types=[
            RateInventoryRoomType(
                room_type_id=rt.id,
                room_type_name=rt.name,
                total_rooms=totals.get(rt.id, 0),
            )
            for rt in room_types
        ],
        dates=dates,
        cells=cells,
    )


def upsert_rate_inventory_override(
    db: Session,
    tenant_id: int,
    data: RateInventoryOverrideUpsert,
) -> RateInventoryCalendarResponse:
    _get_outlet(db, tenant_id, data.outlet_id)
    room_type = (
        db.query(RoomType)
        .filter(
            RoomType.id == data.room_type_id,
            RoomType.tenant_id == tenant_id,
            RoomType.is_active.is_(True),
        )
        .first()
    )
    if room_type is None:
        raise NotFoundError("Room type not found")

    from app.modules.settings.service import upsert_pms_inventory_override

    upsert_pms_inventory_override(
        db,
        tenant_id,
        data.outlet_id,
        data.room_type_id,
        data.date.isoformat(),
        stop_sell=data.stop_sell,
        rate=data.rate,
        clear_rate=data.clear_rate,
        cta=data.cta,
        ctd=data.ctd,
        min_stay=data.min_stay,
        max_stay=data.max_stay,
        clear_min_stay=data.clear_min_stay,
        clear_max_stay=data.clear_max_stay,
    )
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, data.outlet_id)
    return get_rate_inventory_calendar(
        db,
        tenant_id,
        data.outlet_id,
        data.date,
        data.date,
    )


def assign_room(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: AssignRoomRequest,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status not in {ReservationStatus.PENDING, ReservationStatus.CONFIRMED}:
        raise ConflictError("Only pending or confirmed reservations can be pre-assigned")

    room = _get_room(db, tenant_id, data.room_id)
    if room.outlet_id != reservation.outlet_id:
        raise ConflictError("Room belongs to a different outlet")

    target_type_id = room.room_type_id
    _validate_availability(
        db,
        tenant_id,
        reservation.outlet_id,
        target_type_id,
        reservation.check_in_date,
        reservation.check_out_date,
        data.room_id,
        exclude_reservation_id=reservation.id,
    )
    if target_type_id != reservation.room_type_id:
        old_type = reservation.room_type_id
        reservation.room_type_id = target_type_id
        reservation.notes = (
            (reservation.notes or "")
            + f"\nRoom type upgrade/change on assign: {old_type} → {target_type_id}"
        ).strip()
    reservation.room_id = data.room_id
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def create_walk_in(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: WalkInCreate,
    default_brand_id: int | None = None,
) -> ReservationDetailRead | ReservationRead:
    create_data = ReservationCreate(
        **{
            **data.model_dump(exclude={"immediate_check_in"}),
            "source": ReservationSource.WALK_IN,
            "auto_confirm": True,
        }
    )
    reservation = create_reservation(
        db, tenant_id, user_id, create_data, default_brand_id=default_brand_id
    )
    if data.immediate_check_in:
        if not data.room_id:
            raise ConflictError("room_id is required for immediate check-in")
        return check_in_reservation(
            db,
            tenant_id,
            user_id,
            reservation.id,
            CheckInRequest(room_id=data.room_id),
        )
    return reservation


def _room_block_to_read(db: Session, block: RoomBlock) -> RoomBlockRead:
    room = db.get(HotelRoom, block.room_id)
    return RoomBlockRead(
        id=block.id,
        tenant_id=block.tenant_id,
        brand_id=block.brand_id,
        outlet_id=block.outlet_id,
        room_id=block.room_id,
        room_number=room.room_number if room else None,
        start_date=block.start_date,
        end_date=block.end_date,
        block_type=block.block_type,
        reason=block.reason,
        created_by=block.created_by,
        created_at=block.created_at,
        updated_at=block.updated_at,
        is_active=block.is_active,
    )


def list_room_blocks(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> list[RoomBlockRead]:
    q = db.query(RoomBlock).filter(
        RoomBlock.tenant_id == tenant_id,
        RoomBlock.is_active.is_(True),
    )
    if outlet_id is not None:
        q = q.filter(RoomBlock.outlet_id == outlet_id)
    if from_date is not None:
        q = q.filter(RoomBlock.end_date > from_date)
    if to_date is not None:
        q = q.filter(RoomBlock.start_date < to_date)
    rows = q.order_by(RoomBlock.start_date, RoomBlock.id).all()
    return [_room_block_to_read(db, row) for row in rows]


def create_room_block(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: RoomBlockCreate,
    default_brand_id: int | None = None,
) -> RoomBlockRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    room = _get_room(db, tenant_id, data.room_id)
    if room.outlet_id != data.outlet_id:
        raise ConflictError("Room does not belong to this outlet")

    occupied = _occupied_room_ids(
        db, tenant_id, data.outlet_id, data.start_date, data.end_date
    )
    if data.room_id in occupied:
        raise ConflictError("Room is not available for the selected block dates")

    block = RoomBlock(
        tenant_id=tenant_id,
        brand_id=default_brand_id or room.brand_id,
        outlet_id=data.outlet_id,
        room_id=data.room_id,
        start_date=data.start_date,
        end_date=data.end_date,
        block_type=data.block_type,
        reason=data.reason,
        created_by=user_id,
    )
    db.add(block)
    db.commit()
    db.refresh(block)
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, data.outlet_id)
    return _room_block_to_read(db, block)


def update_room_block(
    db: Session,
    tenant_id: int,
    block_id: int,
    data: RoomBlockUpdate,
) -> RoomBlockRead:
    block = (
        db.query(RoomBlock)
        .filter(RoomBlock.id == block_id, RoomBlock.tenant_id == tenant_id)
        .first()
    )
    if block is None:
        raise NotFoundError("Room block not found")
    payload = data.model_dump(exclude_unset=True)
    start = payload.get("start_date", block.start_date)
    end = payload.get("end_date", block.end_date)
    if end <= start:
        raise ConflictError("end_date must be after start_date")
    if any(k in payload for k in ("start_date", "end_date")):
        occupied = _occupied_room_ids(
            db, tenant_id, block.outlet_id, start, end
        )
        # Current block's room is in blocked set; allow if only this block occupies it
        blocked = _blocked_room_ids(
            db, tenant_id, block.outlet_id, start, end, exclude_block_id=block.id
        )
        reserved = (
            db.query(GuestReservation.room_id)
            .filter(
                GuestReservation.tenant_id == tenant_id,
                GuestReservation.outlet_id == block.outlet_id,
                GuestReservation.is_active.is_(True),
                GuestReservation.status.in_(list(ACTIVE_STATUSES)),
                GuestReservation.room_id == block.room_id,
                GuestReservation.check_in_date < end,
                GuestReservation.check_out_date > start,
            )
            .first()
        )
        if reserved or block.room_id in blocked:
            raise ConflictError("Room is not available for the selected block dates")
    for key, value in payload.items():
        setattr(block, key, value)
    db.commit()
    db.refresh(block)
    return _room_block_to_read(db, block)


def delete_room_block(db: Session, tenant_id: int, block_id: int) -> None:
    block = (
        db.query(RoomBlock)
        .filter(
            RoomBlock.id == block_id,
            RoomBlock.tenant_id == tenant_id,
            RoomBlock.is_active.is_(True),
        )
        .first()
    )
    if block is None:
        raise NotFoundError("Room block not found")
    block.is_active = False
    outlet_id = block.outlet_id
    db.commit()
    from app.modules.pms.ota_hooks import notify_lodging_availability_changed

    notify_lodging_availability_changed(tenant_id, outlet_id)


def move_room(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: MoveRoomRequest,
) -> ReservationDetailRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Only in-house guests can be moved")
    if not reservation.room_id:
        raise ConflictError("No room currently assigned")
    if data.room_id == reservation.room_id:
        raise ConflictError("Guest is already in this room")

    new_room = _get_room(db, tenant_id, data.room_id)
    if new_room.outlet_id != reservation.outlet_id:
        raise ConflictError("Room belongs to a different outlet")

    target_type_id = new_room.room_type_id
    _validate_availability(
        db,
        tenant_id,
        reservation.outlet_id,
        target_type_id,
        date.today(),
        reservation.check_out_date,
        data.room_id,
        exclude_reservation_id=reservation.id,
    )

    old_room_id = reservation.room_id
    old_type_id = reservation.room_type_id
    hk_service.update_room_status(
        db,
        tenant_id,
        old_room_id,
        RoomStatusUpdate(status=RoomStatus.VACANT_DIRTY, guest_name=None, checkout_date=None),
    )
    if target_type_id != old_type_id:
        reservation.room_type_id = target_type_id
        reservation.notes = (
            (reservation.notes or "")
            + f"\nRoom type upgrade/change on move: {old_type_id} → {target_type_id}"
        ).strip()
    reservation.room_id = data.room_id
    if data.notes:
        reservation.notes = (reservation.notes or "") + f"\nRoom move: {data.notes}"

    hk_service.update_room_status(
        db,
        tenant_id,
        data.room_id,
        RoomStatusUpdate(
            status=RoomStatus.OCCUPIED,
            guest_name=reservation.guest_name,
            checkout_date=reservation.check_out_date,
        ),
    )

    if data.rate_delta:
        folio = _ensure_folio(db, reservation)
        delta = float(data.rate_delta)
        if delta > 0:
            _add_folio_entry(
                db,
                folio,
                FolioEntryType.ADJUSTMENT,
                f"Room move rate adjustment ({old_room_id} → {data.room_id})",
                delta,
                posted_by=user_id,
            )
        elif delta < 0:
            _add_folio_entry(
                db,
                folio,
                FolioEntryType.REFUND,
                f"Room move rate credit ({old_room_id} → {data.room_id})",
                abs(delta),
                posted_by=user_id,
            )

    db.commit()
    return get_reservation(db, tenant_id, reservation_id)


def _next_group_code(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"GRP-{year}-"
    count = (
        db.query(func.count(ReservationGroup.id))
        .filter(
            ReservationGroup.tenant_id == tenant_id,
            ReservationGroup.group_code.like(f"{prefix}%"),
        )
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:04d}"


DEFAULT_GROUP_BILLING = {
    "room_rate": "room",
    "pos": "master",
    "minibar": "room",
    "spa": "master",
    "banquet": "master",
    "other": "master",
}


def _parse_group_billing(raw: str | None) -> GroupBillingInstructions:
    import json

    data = dict(DEFAULT_GROUP_BILLING)
    if raw:
        try:
            parsed = json.loads(raw)
            if isinstance(parsed, dict):
                for key in DEFAULT_GROUP_BILLING:
                    val = str(parsed.get(key, data[key])).strip().lower()
                    data[key] = "master" if val == "master" else "room"
        except (TypeError, ValueError, json.JSONDecodeError):
            pass
    return GroupBillingInstructions(**data)


def _dump_group_billing(instructions: dict[str, str] | GroupBillingInstructions | None) -> str:
    import json

    if instructions is None:
        payload = dict(DEFAULT_GROUP_BILLING)
    elif isinstance(instructions, GroupBillingInstructions):
        payload = instructions.model_dump()
    else:
        payload = dict(DEFAULT_GROUP_BILLING)
        for key in DEFAULT_GROUP_BILLING:
            if key in instructions:
                val = str(instructions[key]).strip().lower()
                payload[key] = "master" if val == "master" else "room"
    return json.dumps(payload)


def _group_billing_target(group: ReservationGroup, charge_class: str) -> str:
    instructions = _parse_group_billing(getattr(group, "billing_instructions_json", None))
    mapping = instructions.model_dump()
    return mapping.get(charge_class, mapping.get("other", "master"))


def _group_to_read(db: Session, group: ReservationGroup) -> ReservationGroupRead:
    reservations = (
        db.query(GuestReservation)
        .options(joinedload(GuestReservation.folio).joinedload(GuestFolio.entries))
        .filter(
            GuestReservation.group_id == group.id,
            GuestReservation.tenant_id == group.tenant_id,
            GuestReservation.is_active.is_(True),
        )
        .order_by(GuestReservation.id)
        .all()
    )
    master = group.master_folio
    if master is None:
        master = (
            db.query(GuestFolio)
            .options(joinedload(GuestFolio.entries))
            .filter(GuestFolio.group_id == group.id, GuestFolio.is_active.is_(True))
            .first()
        )
    room_balance = sum(float(r.folio.balance) for r in reservations if r.folio)
    master_balance = float(master.balance) if master else 0.0
    return ReservationGroupRead(
        id=group.id,
        tenant_id=group.tenant_id,
        brand_id=group.brand_id,
        outlet_id=group.outlet_id,
        group_code=group.group_code,
        name=group.name,
        company_name=getattr(group, "company_name", None),
        shared_deposit=float(group.shared_deposit),
        notes=group.notes,
        customer_id=group.customer_id,
        created_by=group.created_by,
        billing_instructions=_parse_group_billing(getattr(group, "billing_instructions_json", None)),
        reservations=[_reservation_to_read(db, row) for row in reservations],
        master_folio=_folio_to_read(master) if master else None,
        room_folios_balance=round(room_balance, 2),
        combined_balance=round(room_balance + master_balance, 2),
        created_at=group.created_at,
        updated_at=group.updated_at,
        is_active=group.is_active,
    )


def list_reservation_groups(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
) -> list[ReservationGroupRead]:
    q = db.query(ReservationGroup).filter(
        ReservationGroup.tenant_id == tenant_id,
        ReservationGroup.is_active.is_(True),
    )
    if outlet_id is not None:
        q = q.filter(ReservationGroup.outlet_id == outlet_id)
    rows = q.order_by(ReservationGroup.id.desc()).all()
    return [_group_to_read(db, row) for row in rows]


def get_reservation_group(db: Session, tenant_id: int, group_id: int) -> ReservationGroupRead:
    group = _get_group_entity(db, tenant_id, group_id)
    _ensure_group_master_folio(db, group)
    db.commit()
    return _group_to_read(db, group)


def create_reservation_group(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: ReservationGroupCreate,
    default_brand_id: int | None = None,
) -> ReservationGroupRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    code = (data.group_code or _next_group_code(db, tenant_id)).strip().upper()
    existing = (
        db.query(ReservationGroup)
        .filter(ReservationGroup.tenant_id == tenant_id, ReservationGroup.group_code == code)
        .first()
    )
    if existing:
        raise ConflictError("Group code already exists")
    group = ReservationGroup(
        tenant_id=tenant_id,
        brand_id=default_brand_id,
        outlet_id=data.outlet_id,
        group_code=code,
        name=data.name.strip(),
        company_name=(data.company_name.strip() if data.company_name else None),
        billing_instructions_json=_dump_group_billing(data.billing_instructions),
        shared_deposit=data.shared_deposit,
        notes=data.notes,
        customer_id=data.customer_id,
        created_by=user_id,
    )
    db.add(group)
    db.flush()
    master = _create_group_master_folio(db, tenant_id, default_brand_id, group)
    if data.shared_deposit > 0:
        _add_folio_entry(
            db,
            master,
            FolioEntryType.DEPOSIT,
            "Group shared deposit",
            data.shared_deposit,
            posted_by=user_id,
        )
    db.commit()
    db.refresh(group)
    return _group_to_read(db, group)


def add_group_reservations(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: GroupRoomingCreate,
    default_brand_id: int | None = None,
) -> ReservationGroupRead:
    group = (
        db.query(ReservationGroup)
        .filter(
            ReservationGroup.id == group_id,
            ReservationGroup.tenant_id == tenant_id,
            ReservationGroup.is_active.is_(True),
        )
        .first()
    )
    if group is None:
        raise NotFoundError("Reservation group not found")

    for stay in data.stays:
        create_reservation(
            db,
            tenant_id,
            user_id,
            ReservationCreate(
                outlet_id=group.outlet_id,
                guest_name=stay.guest_name,
                guest_mobile=stay.guest_mobile,
                guest_email=stay.guest_email,
                customer_id=group.customer_id,
                room_type_id=stay.room_type_id,
                room_id=stay.room_id,
                check_in_date=stay.check_in_date,
                check_out_date=stay.check_out_date,
                adults=stay.adults,
                children=stay.children,
                rate_plan_id=stay.rate_plan_id,
                rate_per_night=stay.rate_per_night,
                notes=stay.notes,
                auto_confirm=data.auto_confirm,
                group_id=group.id,
            ),
            default_brand_id=default_brand_id or group.brand_id,
        )
    return get_reservation_group(db, tenant_id, group_id)


def get_group_master_folio(db: Session, tenant_id: int, group_id: int) -> FolioRead:
    group = _get_group_entity(db, tenant_id, group_id)
    folio = _ensure_group_master_folio(db, group)
    db.commit()
    db.refresh(folio)
    return _folio_to_read(folio)


def add_group_folio_charge(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: FolioChargeCreate,
) -> FolioRead:
    group = _get_group_entity(db, tenant_id, group_id)
    folio = _ensure_group_master_folio(db, group)
    if folio.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is closed")
    _add_folio_entry(
        db,
        folio,
        data.entry_type,
        data.description,
        data.amount,
        posted_by=user_id,
    )
    db.commit()
    db.refresh(folio)
    return _folio_to_read(folio)


def add_group_folio_payment(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: FolioPaymentCreate,
) -> FolioRead:
    group = _get_group_entity(db, tenant_id, group_id)
    folio = _ensure_group_master_folio(db, group)
    if folio.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is closed")
    _add_folio_entry(
        db,
        folio,
        FolioEntryType.PAYMENT,
        _payment_description(data.tender, data.description),
        data.amount,
        posted_by=user_id,
    )
    db.commit()
    db.refresh(folio)
    return _folio_to_read(folio)


def transfer_room_charge_to_master(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: FolioTransferToMasterRequest,
) -> ReservationGroupRead:
    group = _get_group_entity(db, tenant_id, group_id)
    reservation = _get_reservation(db, tenant_id, data.reservation_id)
    if reservation.group_id != group.id:
        raise ConflictError("Reservation is not part of this group")
    if not reservation.folio:
        raise NotFoundError("Room folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Room folio is closed")

    master = _ensure_group_master_folio(db, group)
    if master.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is closed")

    amount = float(data.amount)
    room_label = reservation.room_number if hasattr(reservation, "room_number") else None
    room = db.get(HotelRoom, reservation.room_id) if reservation.room_id else None
    room_number = room.room_number if room else "unassigned"
    desc = data.description or f"Transferred from {reservation.guest_name} (room {room_number})"

    # Credit room folio (reduces guest room balance)
    _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.PAYMENT,
        f"Transferred to group master · {group.group_code}",
        amount,
        posted_by=user_id,
    )
    # Debit master folio
    _add_folio_entry(
        db,
        master,
        FolioEntryType.ADJUSTMENT,
        desc,
        amount,
        posted_by=user_id,
    )
    db.commit()
    return get_reservation_group(db, tenant_id, group_id)


def update_reservation_group(
    db: Session,
    tenant_id: int,
    group_id: int,
    data: ReservationGroupUpdate,
) -> ReservationGroupRead:
    group = _get_group_entity(db, tenant_id, group_id)
    if data.name is not None:
        group.name = data.name.strip()
    if data.company_name is not None:
        group.company_name = data.company_name.strip() or None
    if data.notes is not None:
        group.notes = data.notes
    if data.billing_instructions is not None:
        group.billing_instructions_json = _dump_group_billing(data.billing_instructions)
    db.commit()
    return get_reservation_group(db, tenant_id, group_id)


def sweep_room_folios_to_master(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: GroupFolioSweepRequest,
) -> ReservationGroupRead:
    group = _get_group_entity(db, tenant_id, group_id)
    master = _ensure_group_master_folio(db, group)
    if master.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is closed")

    q = (
        db.query(GuestReservation)
        .options(joinedload(GuestReservation.folio))
        .filter(
            GuestReservation.group_id == group.id,
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
        )
    )
    if data.reservation_ids:
        q = q.filter(GuestReservation.id.in_(data.reservation_ids))
    reservations = q.all()

    swept = 0
    for reservation in reservations:
        if not reservation.folio or reservation.folio.status != FolioStatus.OPEN:
            continue
        balance = float(reservation.folio.balance)
        if balance <= 0.009 and not data.include_zero:
            continue
        if balance <= 0.009:
            continue
        transfer_room_charge_to_master(
            db,
            tenant_id,
            user_id,
            group_id,
            FolioTransferToMasterRequest(
                reservation_id=reservation.id,
                amount=balance,
                description=f"Sweep room balance · {reservation.guest_name}",
            ),
        )
        swept += 1
    if swept == 0:
        # transfer_room_charge_to_master commits internally; still return fresh group
        return get_reservation_group(db, tenant_id, group_id)
    return get_reservation_group(db, tenant_id, group_id)


def transfer_group_folio_to_city_ledger(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: CityLedgerTransferRequest,
) -> CityLedgerTransferResponse:
    group = _get_group_entity(db, tenant_id, group_id)
    folio = _ensure_group_master_folio(db, group)
    if folio.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is closed")

    amount = round(float(data.amount), 2)
    balance = float(folio.balance)
    if amount > balance + 0.009:
        raise ConflictError(f"Transfer amount exceeds master folio balance (₹{balance:,.2f})")

    company = (data.company_name or group.company_name or group.name).strip()
    if not company:
        raise ConflictError("Company name is required for city ledger transfer")
    reference = _next_city_ledger_reference(db, tenant_id)
    _add_folio_entry(
        db,
        folio,
        FolioEntryType.PAYMENT,
        f"City ledger transfer · {reference} · {company}",
        amount,
        posted_by=user_id,
    )
    entry = CityLedgerEntry(
        tenant_id=tenant_id,
        brand_id=group.brand_id,
        outlet_id=group.outlet_id,
        reservation_id=None,
        group_id=group.id,
        folio_id=folio.id,
        reference=reference,
        company_name=company,
        guest_name=group.name,
        original_amount=amount,
        balance=amount,
        status=CityLedgerStatus.OPEN,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.refresh(folio)
    return CityLedgerTransferResponse(
        folio=_folio_to_read(folio),
        city_ledger=_city_ledger_to_read(entry, group_code=group.group_code),
        message=f"₹{amount:,.2f} transferred to city ledger {reference}",
    )


def close_group_master_folio(
    db: Session,
    tenant_id: int,
    user_id: int,
    group_id: int,
    data: GroupFolioCloseRequest,
) -> FolioRead:
    group = _get_group_entity(db, tenant_id, group_id)
    folio = _ensure_group_master_folio(db, group)
    if folio.status != FolioStatus.OPEN:
        raise ConflictError("Master folio is already closed")

    reservations = (
        db.query(GuestReservation)
        .options(joinedload(GuestReservation.folio))
        .filter(
            GuestReservation.group_id == group.id,
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
        )
        .all()
    )
    open_room_balance = sum(
        float(r.folio.balance)
        for r in reservations
        if r.folio and r.folio.status == FolioStatus.OPEN and float(r.folio.balance) > 0.009
    )
    if open_room_balance > 0.009 and not data.force_settle:
        raise ConflictError(
            f"Room folios still have ₹{open_room_balance:,.2f} open — sweep to master first"
        )

    balance = float(folio.balance)
    if balance > 0.009 and not data.force_settle:
        raise ConflictError(
            f"Master folio balance ₹{balance:,.2f} must be paid or sent to city ledger first"
        )

    folio.status = FolioStatus.CLOSED
    db.commit()
    db.refresh(folio)
    return _folio_to_read(folio)


def apply_stay_modifiers(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: StayModifierUpdate,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status in {
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.CANCELLED,
        ReservationStatus.NO_SHOW,
    }:
        raise ConflictError("Cannot modify a closed reservation")

    payload = data.model_dump(exclude_unset=True)
    was_late = bool(reservation.late_check_out)
    enabling_day_use = payload.get("day_use") is True and not reservation.day_use

    if enabling_day_use and (payload.get("late_check_out") is True or was_late):
        raise ConflictError("Day use cannot be combined with late check-out")
    if payload.get("day_use") is True and payload.get("late_check_out") is True:
        raise ConflictError("Day use cannot be combined with late check-out")

    plan = db.get(RatePlan, reservation.rate_plan_id) if reservation.rate_plan_id else None
    if enabling_day_use and plan is not None and not bool(getattr(plan, "allows_day_use", True)):
        raise ConflictError("Rate plan does not allow day use")

    if "check_out_date" in payload and not enabling_day_use:
        new_out = payload["check_out_date"]
        if new_out <= reservation.check_in_date:
            raise ConflictError("check_out_date must be after check_in_date")
        reservation.check_out_date = new_out

    for key in ("early_check_in", "late_check_out", "day_use"):
        if key in payload:
            setattr(reservation, key, payload[key])

    if reservation.day_use:
        reservation.late_check_out = False
        reservation.check_out_date = reservation.check_in_date + timedelta(days=1)

    day_use_percent = _day_use_percent_for_plan(plan)
    reservation.total_amount = _reservation_stay_total(
        float(reservation.rate_per_night),
        reservation.check_in_date,
        reservation.check_out_date,
        reservation.adults,
        reservation.children,
        plan,
        day_use=bool(reservation.day_use),
    )

    applying_late = (
        payload.get("late_check_out") is True
        and not was_late
        and not reservation.day_use
    )
    if applying_late:
        folio = _ensure_folio(db, reservation)
        half_night = round(float(reservation.rate_per_night) * 0.5, 2)
        if half_night > 0:
            _add_folio_entry(
                db,
                folio,
                FolioEntryType.ROOM_CHARGE,
                "Late check-out (0.5 night)",
                half_night,
                posted_by=user_id,
            )

    if enabling_day_use:
        reservation.notes = (
            (reservation.notes or "")
            + f"\nDay use applied ({day_use_percent:g}% of nightly rate)"
        ).strip()

    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def _night_audit_to_read(log: NightAuditLog) -> NightAuditLogRead:
    return NightAuditLogRead(
        id=log.id,
        tenant_id=log.tenant_id,
        brand_id=log.brand_id,
        outlet_id=log.outlet_id,
        business_date=log.business_date,
        ran_at=log.ran_at,
        rooms_posted=log.rooms_posted,
        no_shows_marked=log.no_shows_marked,
        arrivals_expected=log.arrivals_expected,
        summary_json=log.summary_json or "{}",
        created_by=log.created_by,
        created_at=log.created_at,
        updated_at=log.updated_at,
        is_active=log.is_active,
    )


def run_night_audit(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: NightAuditRunRequest,
    default_brand_id: int | None = None,
) -> NightAuditResult:
    import json

    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    existing = (
        db.query(NightAuditLog)
        .filter(
            NightAuditLog.tenant_id == tenant_id,
            NightAuditLog.outlet_id == data.outlet_id,
            NightAuditLog.business_date == data.business_date,
            NightAuditLog.is_active.is_(True),
        )
        .first()
    )
    if existing and not data.force:
        raise ConflictError("Night audit already run for this outlet and business date")

    in_house = (
        db.query(GuestReservation)
        .options(joinedload(GuestReservation.folio).joinedload(GuestFolio.entries))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == data.outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.CHECKED_IN,
            GuestReservation.check_in_date <= data.business_date,
            GuestReservation.check_out_date > data.business_date,
        )
        .all()
    )

    rooms_posted = 0
    for reservation in in_house:
        folio = _ensure_folio(db, reservation)
        if _post_night_room_charge(db, folio, reservation, data.business_date, user_id):
            rooms_posted += 1

    # Stayover / daily cleans for occupied in-house rooms.
    from app.modules.housekeeping.models import HousekeepingTaskType

    daily_tasks_created = 0
    for reservation in in_house:
        if not reservation.room_id:
            continue
        room = _get_room(db, tenant_id, reservation.room_id)
        created = hk_service.ensure_room_task(
            db,
            tenant_id,
            room,
            HousekeepingTaskType.DAILY,
            notes=(
                f"Night audit stayover · {data.business_date.isoformat()} · "
                f"{reservation.confirmation_number}"
            ),
        )
        if created:
            daily_tasks_created += 1

    no_show_cutoff = data.business_date
    expected_arrivals = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == data.outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.CONFIRMED,
            GuestReservation.check_in_date == no_show_cutoff,
        )
        .count()
    )

    # Mark confirmed arrivals whose check-in was yesterday as no-show
    yesterday = data.business_date - timedelta(days=1)
    no_show_candidates = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == data.outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.CONFIRMED,
            GuestReservation.check_in_date == yesterday,
        )
        .all()
    )
    no_shows_marked = 0
    for reservation in no_show_candidates:
        reservation.status = ReservationStatus.NO_SHOW
        if reservation.rate_plan_id:
            plan = db.get(RatePlan, reservation.rate_plan_id)
            if plan and float(plan.no_show_fee_percent or 0) > 0:
                _post_rate_plan_fee(
                    db,
                    reservation,
                    float(plan.no_show_fee_percent),
                    f"No-show fee ({float(plan.no_show_fee_percent):g}%)",
                    posted_by=user_id,
                )
        no_shows_marked += 1

    summary = {
        "rooms_posted": rooms_posted,
        "no_shows_marked": no_shows_marked,
        "arrivals_expected": expected_arrivals,
        "in_house_count": len(in_house),
        "daily_tasks_created": daily_tasks_created,
    }
    if existing and data.force:
        existing.ran_at = datetime.utcnow()
        existing.rooms_posted = rooms_posted
        existing.no_shows_marked = no_shows_marked
        existing.arrivals_expected = expected_arrivals
        existing.summary_json = json.dumps(summary)
        existing.created_by = user_id
        log = existing
    else:
        log = NightAuditLog(
            tenant_id=tenant_id,
            brand_id=default_brand_id or outlet.brand_id,
            outlet_id=data.outlet_id,
            business_date=data.business_date,
            ran_at=datetime.utcnow(),
            rooms_posted=rooms_posted,
            no_shows_marked=no_shows_marked,
            arrivals_expected=expected_arrivals,
            summary_json=json.dumps(summary),
            created_by=user_id,
        )
        db.add(log)

    db.commit()
    db.refresh(log)
    return NightAuditResult(
        log=_night_audit_to_read(log),
        rooms_posted=rooms_posted,
        no_shows_marked=no_shows_marked,
        arrivals_expected=expected_arrivals,
        daily_tasks_created=daily_tasks_created,
    )


def list_night_audit_logs(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
    limit: int = 50,
) -> list[NightAuditLogRead]:
    q = db.query(NightAuditLog).filter(
        NightAuditLog.tenant_id == tenant_id,
        NightAuditLog.is_active.is_(True),
    )
    if outlet_id is not None:
        q = q.filter(NightAuditLog.outlet_id == outlet_id)
    rows = q.order_by(NightAuditLog.business_date.desc(), NightAuditLog.id.desc()).limit(limit).all()
    return [_night_audit_to_read(row) for row in rows]


_ACCOUNT_HINTS: dict[FolioEntryType, str] = {
    FolioEntryType.ROOM_CHARGE: "Room Revenue",
    FolioEntryType.TAX: "Output GST",
    FolioEntryType.POS_CHARGE: "F&B / POS to Room",
    FolioEntryType.SPA_CHARGE: "Spa Revenue",
    FolioEntryType.BANQUET_CHARGE: "Banquet Revenue",
    FolioEntryType.MINIBAR_CHARGE: "Minibar Revenue",
    FolioEntryType.ADJUSTMENT: "Adjustments",
    FolioEntryType.PAYMENT: "Guest Receipts",
    FolioEntryType.DEPOSIT: "Deposits",
    FolioEntryType.REFUND: "Refunds",
    FolioEntryType.PACKAGE_CREDIT: "Package Credits",
}


def _folio_voucher_type(entry_type: FolioEntryType) -> str:
    if entry_type == FolioEntryType.TAX:
        return "tax"
    if entry_type == FolioEntryType.PAYMENT:
        return "receipt"
    if entry_type == FolioEntryType.DEPOSIT:
        return "receipt"
    if entry_type == FolioEntryType.REFUND:
        return "refund"
    if entry_type in {FolioEntryType.PACKAGE_CREDIT, FolioEntryType.ADJUSTMENT}:
        return "adjustment"
    return "sale"


def _parse_tax_rate_from_description(description: str | None, default: float) -> float:
    import re

    text = description or ""
    match = re.search(r"(\d+(?:\.\d+)?)\s*%", text)
    if match:
        try:
            return float(match.group(1))
        except ValueError:
            pass
    return float(default)


def get_accounts_day_book(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    business_date: date,
) -> AccountsDayBookRead:
    from app.modules.pos.models import (
        Bill,
        BillPaymentStatus,
        Payment,
        PaymentMode,
        PaymentRecordStatus,
    )
    from app.modules.settings.service import get_pms_tax_config

    _get_outlet(db, tenant_id, outlet_id)
    tax_cfg = get_pms_tax_config(db, tenant_id, outlet_id)
    tax_percent = float(tax_cfg.get("tax_percent", 12.0))
    tax_label = str(tax_cfg.get("tax_label", "GST"))

    start = datetime.combine(business_date, time.min)
    end = start + timedelta(days=1)

    audit_row = (
        db.query(NightAuditLog)
        .filter(
            NightAuditLog.tenant_id == tenant_id,
            NightAuditLog.outlet_id == outlet_id,
            NightAuditLog.business_date == business_date,
            NightAuditLog.is_active.is_(True),
        )
        .order_by(NightAuditLog.id.desc())
        .first()
    )
    night_audit = AccountsDayBookNightAuditInfo(
        ran=audit_row is not None,
        ran_at=audit_row.ran_at if audit_row else None,
        rooms_posted=int(audit_row.rooms_posted) if audit_row else 0,
        no_shows_marked=int(audit_row.no_shows_marked) if audit_row else 0,
        arrivals_expected=int(audit_row.arrivals_expected) if audit_row else 0,
    )

    folio_rows = (
        db.query(FolioEntry, GuestReservation, GuestFolio)
        .join(GuestFolio, GuestFolio.id == FolioEntry.folio_id)
        .join(GuestReservation, GuestReservation.id == GuestFolio.reservation_id)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            FolioEntry.is_active.is_(True),
            FolioEntry.created_at >= start,
            FolioEntry.created_at < end,
        )
        .order_by(FolioEntry.id.asc())
        .all()
    )

    lines: list[AccountsDayBookLine] = []
    summary = AccountsDayBookSummary()
    by_type: dict[str, float] = {}
    gst_buckets: dict[float, AccountsGstRateBucket] = {}
    tender = TenderMixRead()

    credit_types = _FOLIO_CREDIT_TYPES

    for entry, reservation, folio in folio_rows:
        desc = entry.description or ""
        if "[voided]" in desc.lower() or desc.upper().startswith("VOID #"):
            continue
        amount = round(float(entry.amount or 0), 2)
        entry_type = entry.entry_type
        et_key = entry_type.value if hasattr(entry_type, "value") else str(entry_type)
        by_type[et_key] = round(by_type.get(et_key, 0.0) + abs(amount), 2)

        is_credit = entry_type in credit_types
        debit = 0.0 if is_credit else abs(amount)
        credit = abs(amount) if is_credit else 0.0

        tax_amount = None
        taxable_amount = None
        tax_rate = None
        tender_val = None

        if entry_type == FolioEntryType.TAX:
            summary.folio_tax = round(summary.folio_tax + abs(amount), 2)
            tax_amount = abs(amount)
            tax_rate = _parse_tax_rate_from_description(desc, tax_percent)
            if tax_rate > 0:
                taxable_amount = round(abs(amount) * 100.0 / tax_rate, 2)
            bucket = gst_buckets.setdefault(
                tax_rate, AccountsGstRateBucket(rate_percent=tax_rate)
            )
            bucket.tax = round(bucket.tax + abs(amount), 2)
            bucket.taxable = round(bucket.taxable + float(taxable_amount or 0), 2)
        elif entry_type == FolioEntryType.PAYMENT:
            summary.folio_payments = round(summary.folio_payments + abs(amount), 2)
            kind = _parse_payment_tender(desc)
            tender_val = kind.value if hasattr(kind, "value") else str(kind)
            if kind == PaymentTender.CASH:
                tender.cash += abs(amount)
            elif kind == PaymentTender.CARD:
                tender.card += abs(amount)
            elif kind == PaymentTender.UPI:
                tender.upi += abs(amount)
            else:
                tender.other += abs(amount)
            tender.total += abs(amount)
        elif entry_type == FolioEntryType.REFUND:
            summary.folio_refunds = round(summary.folio_refunds + abs(amount), 2)
        elif entry_type not in credit_types:
            summary.folio_charges_ex_tax = round(summary.folio_charges_ex_tax + abs(amount), 2)

        lines.append(
            AccountsDayBookLine(
                business_date=business_date,
                outlet_id=outlet_id,
                source="folio",
                voucher_type=_folio_voucher_type(entry_type),
                entry_type=et_key,
                reference=folio.folio_number or reservation.confirmation_number,
                guest_or_party=reservation.guest_name,
                description=desc,
                account_hint=_ACCOUNT_HINTS.get(entry_type, "Other"),
                debit=round(debit, 2),
                credit=round(credit, 2),
                amount_signed=amount,
                taxable_amount=taxable_amount,
                tax_amount=tax_amount,
                tax_rate_percent=tax_rate,
                tax_label=tax_label if tax_amount is not None else None,
                tender=tender_val,
                posted_at=entry.created_at,
                external_id=f"folio_entry:{entry.id}",
            )
        )

    bills = (
        db.query(Bill)
        .options(joinedload(Bill.payments))
        .filter(
            Bill.tenant_id == tenant_id,
            Bill.outlet_id == outlet_id,
            Bill.is_active.is_(True),
            Bill.created_at >= start,
            Bill.created_at < end,
            Bill.payment_status != BillPaymentStatus.CANCELLED,
        )
        .order_by(Bill.id.asc())
        .all()
    )
    for bill in bills:
        taxable = round(float(bill.subtotal or 0) - float(bill.discount_amount or 0), 2)
        gst = round(float(bill.gst_amount or 0), 2)
        summary.pos_taxable = round(summary.pos_taxable + max(taxable, 0), 2)
        summary.pos_gst = round(summary.pos_gst + gst, 2)
        by_type["pos_bill"] = round(by_type.get("pos_bill", 0.0) + float(bill.grand_total or 0), 2)

        if taxable:
            lines.append(
                AccountsDayBookLine(
                    business_date=business_date,
                    outlet_id=outlet_id,
                    source="pos",
                    voucher_type="sale",
                    entry_type="pos_bill",
                    reference=bill.bill_number,
                    guest_or_party="POS walk-in",
                    description=f"POS bill {bill.bill_number}",
                    account_hint="F&B Sales",
                    debit=abs(taxable),
                    credit=0,
                    amount_signed=taxable,
                    taxable_amount=taxable,
                    tax_amount=None,
                    tax_rate_percent=tax_percent if gst else None,
                    tax_label=tax_label if gst else None,
                    tender=None,
                    posted_at=bill.created_at,
                    external_id=f"pos_bill:{bill.id}",
                )
            )
        if gst:
            bucket = gst_buckets.setdefault(
                tax_percent, AccountsGstRateBucket(rate_percent=tax_percent)
            )
            bucket.tax = round(bucket.tax + gst, 2)
            bucket.taxable = round(bucket.taxable + max(taxable, 0), 2)
            lines.append(
                AccountsDayBookLine(
                    business_date=business_date,
                    outlet_id=outlet_id,
                    source="pos",
                    voucher_type="tax",
                    entry_type="pos_gst",
                    reference=bill.bill_number,
                    guest_or_party="POS walk-in",
                    description=f"{tax_label} {tax_percent:g}% — {bill.bill_number}",
                    account_hint="Output GST",
                    debit=gst,
                    credit=0,
                    amount_signed=gst,
                    taxable_amount=max(taxable, 0),
                    tax_amount=gst,
                    tax_rate_percent=tax_percent,
                    tax_label=tax_label,
                    tender=None,
                    posted_at=bill.created_at,
                    external_id=f"pos_bill_gst:{bill.id}",
                )
            )

        for payment in bill.payments or []:
            if payment.status != PaymentRecordStatus.SUCCESS:
                continue
            mode = payment.payment_mode
            mode_val = mode.value if hasattr(mode, "value") else str(mode)
            if mode == PaymentMode.ROOM_CHARGE:
                continue
            pay_amt = round(float(payment.amount or 0), 2)
            if pay_amt <= 0:
                continue
            summary.pos_payments_excl_room_charge = round(
                summary.pos_payments_excl_room_charge + pay_amt, 2
            )
            hint = "Cash"
            tender_key = "other"
            if mode == PaymentMode.CASH:
                tender.cash += pay_amt
                tender_key = "cash"
                hint = "Cash"
            elif mode == PaymentMode.CARD:
                tender.card += pay_amt
                tender_key = "card"
                hint = "Card"
            elif mode == PaymentMode.UPI:
                tender.upi += pay_amt
                tender_key = "upi"
                hint = "UPI"
            elif mode == PaymentMode.ONLINE:
                tender.other += pay_amt
                hint = "Online"
            elif mode == PaymentMode.LOYALTY:
                tender.other += pay_amt
                hint = "Loyalty"
            else:
                tender.other += pay_amt
                hint = mode_val.replace("_", " ").title()
            tender.total += pay_amt
            lines.append(
                AccountsDayBookLine(
                    business_date=business_date,
                    outlet_id=outlet_id,
                    source="pos",
                    voucher_type="receipt",
                    entry_type="pos_payment",
                    reference=bill.bill_number,
                    guest_or_party="POS walk-in",
                    description=f"POS payment · {mode_val}",
                    account_hint=hint,
                    debit=0,
                    credit=pay_amt,
                    amount_signed=-pay_amt,
                    taxable_amount=None,
                    tax_amount=None,
                    tax_rate_percent=None,
                    tax_label=None,
                    tender=tender_key if tender_key != "other" else mode_val,
                    posted_at=bill.created_at,
                    external_id=f"pos_payment:{payment.id}",
                )
            )

    tender.cash = round(tender.cash, 2)
    tender.card = round(tender.card, 2)
    tender.upi = round(tender.upi, 2)
    tender.other = round(tender.other, 2)
    tender.total = round(tender.total, 2)
    summary.by_entry_type = by_type
    summary.by_gst_rate = sorted(gst_buckets.values(), key=lambda b: b.rate_percent)
    summary.tender_mix = tender

    return AccountsDayBookRead(
        outlet_id=outlet_id,
        business_date=business_date,
        tax_label=tax_label,
        tax_percent_default=tax_percent,
        night_audit=night_audit,
        summary=summary,
        lines=lines,
    )


def build_accounts_day_book_csv(book: AccountsDayBookRead) -> str:
    import csv
    import io

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "business_date",
            "outlet_id",
            "source",
            "voucher_type",
            "entry_type",
            "reference",
            "guest_or_party",
            "description",
            "account_hint",
            "debit",
            "credit",
            "amount_signed",
            "taxable_amount",
            "tax_amount",
            "tax_rate_percent",
            "tax_label",
            "tender",
            "posted_at",
            "external_id",
        ]
    )
    for line in book.lines:
        writer.writerow(
            [
                book.business_date.isoformat(),
                book.outlet_id,
                line.source,
                line.voucher_type,
                line.entry_type,
                line.reference or "",
                line.guest_or_party or "",
                line.description or "",
                line.account_hint,
                line.debit,
                line.credit,
                line.amount_signed,
                "" if line.taxable_amount is None else line.taxable_amount,
                "" if line.tax_amount is None else line.tax_amount,
                "" if line.tax_rate_percent is None else line.tax_rate_percent,
                line.tax_label or "",
                line.tender or "",
                line.posted_at.isoformat() if line.posted_at else "",
                line.external_id,
            ]
        )
    # Summary appendix for GSTR mapping
    writer.writerow([])
    writer.writerow(["# summary"])
    writer.writerow(
        [
            "folio_charges_ex_tax",
            book.summary.folio_charges_ex_tax,
            "folio_tax",
            book.summary.folio_tax,
            "folio_payments",
            book.summary.folio_payments,
            "pos_taxable",
            book.summary.pos_taxable,
            "pos_gst",
            book.summary.pos_gst,
            "pos_payments",
            book.summary.pos_payments_excl_room_charge,
        ]
    )
    writer.writerow(["# gst_buckets", "rate_percent", "taxable", "tax"])
    for bucket in book.summary.by_gst_rate:
        writer.writerow(
            ["gst_bucket", bucket.rate_percent, bucket.taxable, bucket.tax]
        )
    writer.writerow(
        [
            "# tender_mix",
            "cash",
            book.summary.tender_mix.cash,
            "card",
            book.summary.tender_mix.card,
            "upi",
            book.summary.tender_mix.upi,
            "other",
            book.summary.tender_mix.other,
            "total",
            book.summary.tender_mix.total,
        ]
    )
    return buffer.getvalue()


def place_card_hold(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: CardHoldRequest,
) -> ReservationRead:
    """Mock gateway authorization hold — no real card data is stored beyond last4."""
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.status in {
        ReservationStatus.CANCELLED,
        ReservationStatus.CHECKED_OUT,
        ReservationStatus.NO_SHOW,
    }:
        raise ConflictError("Cannot place a card hold on a closed reservation")
    if reservation.deposit_status == DepositStatus.HELD and reservation.payment_hold_ref:
        raise ConflictError("A card hold is already active on this reservation")
    if reservation.deposit_status in {
        DepositStatus.CAPTURED,
        DepositStatus.FORFEITED,
        DepositStatus.REFUNDED,
    }:
        raise ConflictError("Deposit is already finalized; cannot place a new hold")

    amount = float(data.amount) if data.amount else float(reservation.deposit_amount or 0)
    if amount <= 0:
        amount = float(reservation.rate_per_night or 0)
    if amount <= 0:
        raise ConflictError("Hold amount must be greater than zero")

    if data.simulate_decline or data.card_last4 == "0000":
        raise ConflictError("Card authorization declined (mock gateway)")

    hold_ref = f"HOLD-{uuid.uuid4().hex[:10].upper()}"
    auth_code = f"{random.randint(100000, 999999)}"
    reservation.guarantee_type = GuaranteeType.CARD_HOLD
    reservation.deposit_status = DepositStatus.HELD
    reservation.deposit_amount = amount
    reservation.payment_provider = "mock"
    reservation.payment_hold_ref = hold_ref
    reservation.payment_auth_code = auth_code
    reservation.card_last4 = data.card_last4
    reservation.hold_expires_at = datetime.utcnow() + timedelta(days=data.hold_days)
    note = data.notes or f"Card hold authorized ······{data.card_last4} ref {hold_ref}"
    reservation.notes = (reservation.notes or "") + f"\n{note}"
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def release_card_hold(
    db: Session,
    tenant_id: int,
    reservation_id: int,
    data: CardHoldReleaseRequest | None = None,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.deposit_status != DepositStatus.HELD:
        raise ConflictError("No active card hold to release")
    hold_ref = reservation.payment_hold_ref or "unknown"
    reservation.deposit_status = DepositStatus.PENDING
    reservation.payment_hold_ref = None
    reservation.payment_auth_code = None
    reservation.hold_expires_at = None
    # Keep card_last4 / provider for audit trail
    note = (data.notes if data and data.notes else f"Card hold released ({hold_ref})")
    reservation.notes = (reservation.notes or "") + f"\n{note}"
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def capture_deposit(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: CaptureDepositRequest | None = None,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.deposit_status not in {DepositStatus.PENDING, DepositStatus.HELD}:
        raise ConflictError("Deposit cannot be captured from current status")

    was_held = reservation.deposit_status == DepositStatus.HELD
    amount = float(reservation.deposit_amount or 0)
    if was_held and amount > 0:
        folio = _ensure_folio(db, reservation)
        last4 = reservation.card_last4 or "****"
        hold_ref = reservation.payment_hold_ref or "n/a"
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.PAYMENT,
            f"Card hold captured ····{last4} ({hold_ref})",
            amount,
            posted_by=user_id,
        )

    reservation.deposit_status = DepositStatus.CAPTURED
    reservation.hold_expires_at = None
    if data and data.notes:
        reservation.notes = (reservation.notes or "") + f"\nDeposit captured: {data.notes}"
    elif was_held:
        reservation.notes = (reservation.notes or "") + "\nCard hold captured to folio"
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def refund_deposit(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: RefundDepositRequest | None = None,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.deposit_status not in {
        DepositStatus.CAPTURED,
        DepositStatus.HELD,
        DepositStatus.PENDING,
    }:
        raise ConflictError("Deposit cannot be refunded from current status")
    amount = float(data.amount) if data and data.amount else float(reservation.deposit_amount or 0)
    if amount > 0:
        folio = _ensure_folio(db, reservation)
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.REFUND,
            (data.notes if data and data.notes else "Deposit refund"),
            amount,
            posted_by=user_id,
        )
    reservation.deposit_status = DepositStatus.REFUNDED
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def forfeit_deposit(
    db: Session,
    tenant_id: int,
    reservation_id: int,
) -> ReservationRead:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if reservation.deposit_status not in {
        DepositStatus.CAPTURED,
        DepositStatus.HELD,
        DepositStatus.PENDING,
    }:
        raise ConflictError("Deposit cannot be forfeited from current status")
    reservation.deposit_status = DepositStatus.FORFEITED
    db.commit()
    db.refresh(reservation)
    return _reservation_to_read(db, reservation)


def get_pms_reports(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    from_date: date,
    to_date: date,
) -> PmsReportsSummary:
    _get_outlet(db, tenant_id, outlet_id)
    if to_date < from_date:
        raise ConflictError("to_date must be on or after from_date")

    total_rooms = (
        db.query(func.count(HotelRoom.id))
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == outlet_id,
            HotelRoom.is_active.is_(True),
            HotelRoom.status.notin_([RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE]),
        )
        .scalar()
        or 0
    )
    days = max((to_date - from_date).days, 1)
    room_nights_available = total_rooms * days

    stayed = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status.in_(
                [ReservationStatus.CHECKED_IN, ReservationStatus.CHECKED_OUT]
            ),
            GuestReservation.check_in_date < to_date,
            GuestReservation.check_out_date > from_date,
        )
        .all()
    )

    room_nights_sold = 0
    room_revenue = 0.0
    for reservation in stayed:
        overlap_start = max(reservation.check_in_date, from_date)
        overlap_end = min(reservation.check_out_date, to_date)
        nights = max((overlap_end - overlap_start).days, 0)
        room_nights_sold += nights
        room_revenue += nights * float(reservation.rate_per_night)

    arrivals = (
        db.query(func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.check_in_date >= from_date,
            GuestReservation.check_in_date <= to_date,
            GuestReservation.status.notin_([ReservationStatus.CANCELLED]),
        )
        .scalar()
        or 0
    )
    departures = (
        db.query(func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.check_out_date >= from_date,
            GuestReservation.check_out_date <= to_date,
            GuestReservation.status.in_(
                [ReservationStatus.CHECKED_OUT, ReservationStatus.CHECKED_IN]
            ),
        )
        .scalar()
        or 0
    )
    cancels = (
        db.query(func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.CANCELLED,
            GuestReservation.check_in_date >= from_date,
            GuestReservation.check_in_date <= to_date,
        )
        .scalar()
        or 0
    )
    no_shows = (
        db.query(func.count(GuestReservation.id))
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.NO_SHOW,
            GuestReservation.check_in_date >= from_date,
            GuestReservation.check_in_date <= to_date,
        )
        .scalar()
        or 0
    )

    occupancy = round((room_nights_sold / room_nights_available * 100) if room_nights_available else 0, 2)
    adr = round((room_revenue / room_nights_sold) if room_nights_sold else 0, 2)
    revpar = round((room_revenue / room_nights_available) if room_nights_available else 0, 2)

    payment_rows = (
        db.query(FolioEntry)
        .join(GuestFolio, GuestFolio.id == FolioEntry.folio_id)
        .join(GuestReservation, GuestReservation.id == GuestFolio.reservation_id)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            FolioEntry.entry_type == FolioEntryType.PAYMENT,
            FolioEntry.is_active.is_(True),
            FolioEntry.created_at >= datetime.combine(from_date, time.min),
            FolioEntry.created_at < datetime.combine(to_date + timedelta(days=1), time.min),
        )
        .all()
    )
    tender = TenderMixRead()
    for entry in payment_rows:
        amount = abs(float(entry.amount))
        kind = _parse_payment_tender(entry.description)
        if "[voided]" in (entry.description or "").lower():
            continue
        if (entry.description or "").upper().startswith("VOID #"):
            continue
        if kind == PaymentTender.CASH:
            tender.cash += amount
        elif kind == PaymentTender.CARD:
            tender.card += amount
        elif kind == PaymentTender.UPI:
            tender.upi += amount
        else:
            tender.other += amount
        tender.total += amount
    tender.cash = round(tender.cash, 2)
    tender.card = round(tender.card, 2)
    tender.upi = round(tender.upi, 2)
    tender.other = round(tender.other, 2)
    tender.total = round(tender.total, 2)

    return PmsReportsSummary(
        outlet_id=outlet_id,
        from_date=from_date,
        to_date=to_date,
        room_nights_sold=room_nights_sold,
        room_nights_available=room_nights_available,
        occupancy=occupancy,
        adr=adr,
        revpar=revpar,
        arrivals=arrivals,
        departures=departures,
        cancels=cancels,
        no_shows=no_shows,
        room_revenue=round(room_revenue, 2),
        payments_collected=tender.total,
        tender_mix=tender,
    )


def list_guest_stay_history(
    db: Session,
    tenant_id: int,
    customer_id: int | None = None,
    guest_mobile: str | None = None,
) -> GuestStayHistoryRead:
    if not customer_id and not guest_mobile:
        raise ConflictError("customer_id or guest_mobile is required")
    q = db.query(GuestReservation).filter(
        GuestReservation.tenant_id == tenant_id,
        GuestReservation.is_active.is_(True),
    )
    if customer_id is not None:
        q = q.filter(GuestReservation.customer_id == customer_id)
    if guest_mobile:
        q = q.filter(GuestReservation.guest_mobile == guest_mobile.strip())
    rows = q.order_by(GuestReservation.check_in_date.desc()).all()
    return GuestStayHistoryRead(
        customer_id=customer_id,
        guest_mobile=guest_mobile,
        stays=[_reservation_to_read(db, row) for row in rows],
    )


def run_night_audit_all_outlets(
    db: Session,
    business_date: date | None = None,
    outlet_id: int | None = None,
) -> dict:
    """Worker helper — run night audit for outlets that have hotel rooms."""
    target_date = business_date or (date.today() - timedelta(days=1))
    room_q = db.query(HotelRoom.outlet_id, HotelRoom.tenant_id).filter(
        HotelRoom.is_active.is_(True),
    )
    if outlet_id is not None:
        room_q = room_q.filter(HotelRoom.outlet_id == outlet_id)
    outlets = {(row.tenant_id, row.outlet_id) for row in room_q.distinct().all()}

    results = []
    for tenant_id, oid in sorted(outlets):
        user = db.query(User).filter(User.tenant_id == tenant_id, User.is_active.is_(True)).first()
        user_id = user.id if user else 0
        try:
            result = run_night_audit(
                db,
                tenant_id,
                user_id,
                NightAuditRunRequest(outlet_id=oid, business_date=target_date, force=False),
            )
            results.append(
                {
                    "tenant_id": tenant_id,
                    "outlet_id": oid,
                    "ok": True,
                    "rooms_posted": result.rooms_posted,
                    "no_shows_marked": result.no_shows_marked,
                }
            )
        except ConflictError as exc:
            results.append(
                {
                    "tenant_id": tenant_id,
                    "outlet_id": oid,
                    "ok": False,
                    "skipped": True,
                    "message": str(exc),
                }
            )
        except Exception as exc:  # noqa: BLE001
            db.rollback()
            results.append(
                {
                    "tenant_id": tenant_id,
                    "outlet_id": oid,
                    "ok": False,
                    "message": str(exc),
                }
            )
    return {
        "business_date": target_date.isoformat(),
        "outlets_processed": len(results),
        "results": results,
    }


def _is_voided_folio_entry(description: str | None) -> bool:
    text = (description or "").lower()
    return "[voided]" in text or (description or "").upper().startswith("VOID #")


def _outlet_folio_entries_in_window(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    start: datetime,
    end: datetime,
    entry_types: list[FolioEntryType],
) -> list[FolioEntry]:
    """Payments/refunds on room folios and group master folios for an outlet."""
    room_entries = (
        db.query(FolioEntry)
        .join(GuestFolio, GuestFolio.id == FolioEntry.folio_id)
        .join(GuestReservation, GuestReservation.id == GuestFolio.reservation_id)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.is_active.is_(True),
            FolioEntry.entry_type.in_(entry_types),
            FolioEntry.is_active.is_(True),
            FolioEntry.created_at >= start,
            FolioEntry.created_at < end,
        )
        .all()
    )
    group_entries = (
        db.query(FolioEntry)
        .join(GuestFolio, GuestFolio.id == FolioEntry.folio_id)
        .join(ReservationGroup, ReservationGroup.id == GuestFolio.group_id)
        .filter(
            ReservationGroup.tenant_id == tenant_id,
            ReservationGroup.outlet_id == outlet_id,
            ReservationGroup.is_active.is_(True),
            FolioEntry.entry_type.in_(entry_types),
            FolioEntry.is_active.is_(True),
            FolioEntry.created_at >= start,
            FolioEntry.created_at < end,
        )
        .all()
    )
    by_id = {e.id: e for e in room_entries}
    for entry in group_entries:
        by_id[entry.id] = entry
    return list(by_id.values())


def _shift_tender_totals(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    opened_at: datetime,
    closed_at: datetime | None,
) -> tuple[TenderMixRead, float]:
    end = closed_at or datetime.utcnow()
    payments = _outlet_folio_entries_in_window(
        db,
        tenant_id,
        outlet_id,
        opened_at,
        end,
        [FolioEntryType.PAYMENT, FolioEntryType.DEPOSIT],
    )
    refunds = _outlet_folio_entries_in_window(
        db,
        tenant_id,
        outlet_id,
        opened_at,
        end,
        [FolioEntryType.REFUND],
    )
    tender = TenderMixRead()
    refunds_total = 0.0
    for entry in payments:
        if _is_voided_folio_entry(entry.description):
            continue
        desc_l = (entry.description or "").lower()
        # Folio transfers are not till cash
        if "transferred to" in desc_l or "city ledger transfer" in desc_l:
            continue
        amount = abs(float(entry.amount))
        kind = _parse_payment_tender(entry.description)
        if kind == PaymentTender.CASH:
            tender.cash += amount
        elif kind == PaymentTender.CARD:
            tender.card += amount
        elif kind == PaymentTender.UPI:
            tender.upi += amount
        else:
            tender.other += amount
        tender.total += amount
    for entry in refunds:
        if _is_voided_folio_entry(entry.description):
            continue
        amount = abs(float(entry.amount))
        refunds_total += amount
        # Cash refunds reduce expected drawer cash
        if _parse_payment_tender(entry.description) == PaymentTender.CASH:
            tender.cash = max(0.0, tender.cash - amount)
            tender.total = max(0.0, tender.total - amount)
    tender.cash = round(tender.cash, 2)
    tender.card = round(tender.card, 2)
    tender.upi = round(tender.upi, 2)
    tender.other = round(tender.other, 2)
    tender.total = round(tender.total, 2)
    return tender, round(refunds_total, 2)


def _cashier_shift_to_read(
    db: Session,
    shift: CashierShift,
    *,
    live: bool = True,
) -> CashierShiftRead:
    end = shift.closed_at if shift.status == CashierShiftStatus.CLOSED else None
    if live or shift.status == CashierShiftStatus.OPEN:
        tender, _refunds = _shift_tender_totals(
            db, shift.tenant_id, shift.outlet_id, shift.opened_at, end
        )
        expected_live = round(float(shift.opening_float) + tender.cash, 2)
    else:
        tender = TenderMixRead(
            cash=float(shift.tender_cash or 0),
            card=float(shift.tender_card or 0),
            upi=float(shift.tender_upi or 0),
            other=float(shift.tender_other or 0),
            total=float(shift.payments_total or 0),
        )
        expected_live = float(shift.expected_cash or 0)

    return CashierShiftRead(
        id=shift.id,
        tenant_id=shift.tenant_id,
        brand_id=shift.brand_id,
        outlet_id=shift.outlet_id,
        status=shift.status.value if hasattr(shift.status, "value") else str(shift.status),
        opened_at=shift.opened_at,
        closed_at=shift.closed_at,
        opened_by=shift.opened_by,
        closed_by=shift.closed_by,
        opening_float=float(shift.opening_float or 0),
        declared_cash=float(shift.declared_cash) if shift.declared_cash is not None else None,
        expected_cash=float(shift.expected_cash) if shift.expected_cash is not None else None,
        cash_variance=float(shift.cash_variance) if shift.cash_variance is not None else None,
        tender_cash=float(shift.tender_cash or 0),
        tender_card=float(shift.tender_card or 0),
        tender_upi=float(shift.tender_upi or 0),
        tender_other=float(shift.tender_other or 0),
        payments_total=float(shift.payments_total or 0),
        refunds_total=float(shift.refunds_total or 0),
        notes=shift.notes,
        tender_mix=tender,
        expected_cash_live=expected_live,
        created_at=shift.created_at,
        updated_at=shift.updated_at,
    )


def _get_cashier_shift(db: Session, tenant_id: int, shift_id: int) -> CashierShift:
    shift = (
        db.query(CashierShift)
        .filter(
            CashierShift.id == shift_id,
            CashierShift.tenant_id == tenant_id,
            CashierShift.is_active.is_(True),
        )
        .first()
    )
    if shift is None:
        raise NotFoundError("Cashier shift not found")
    return shift


def get_open_cashier_shift(
    db: Session,
    tenant_id: int,
    outlet_id: int,
) -> CashierShiftRead | None:
    _get_outlet(db, tenant_id, outlet_id)
    shift = (
        db.query(CashierShift)
        .filter(
            CashierShift.tenant_id == tenant_id,
            CashierShift.outlet_id == outlet_id,
            CashierShift.status == CashierShiftStatus.OPEN,
            CashierShift.is_active.is_(True),
        )
        .order_by(CashierShift.opened_at.desc())
        .first()
    )
    if shift is None:
        return None
    return _cashier_shift_to_read(db, shift)


def list_cashier_shifts(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
    limit: int = 20,
) -> list[CashierShiftRead]:
    q = db.query(CashierShift).filter(
        CashierShift.tenant_id == tenant_id,
        CashierShift.is_active.is_(True),
    )
    if outlet_id is not None:
        q = q.filter(CashierShift.outlet_id == outlet_id)
    rows = q.order_by(CashierShift.opened_at.desc()).limit(min(limit, 100)).all()
    return [_cashier_shift_to_read(db, row, live=row.status == CashierShiftStatus.OPEN) for row in rows]


def open_cashier_shift(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: CashierShiftOpenRequest,
    default_brand_id: int | None = None,
) -> CashierShiftRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    existing = (
        db.query(CashierShift)
        .filter(
            CashierShift.tenant_id == tenant_id,
            CashierShift.outlet_id == data.outlet_id,
            CashierShift.status == CashierShiftStatus.OPEN,
            CashierShift.is_active.is_(True),
        )
        .first()
    )
    if existing:
        raise ConflictError("An open cashier shift already exists for this outlet")

    shift = CashierShift(
        tenant_id=tenant_id,
        brand_id=default_brand_id,
        outlet_id=data.outlet_id,
        status=CashierShiftStatus.OPEN,
        opened_at=datetime.utcnow(),
        opened_by=user_id,
        opening_float=float(data.opening_float or 0),
        notes=data.notes,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return _cashier_shift_to_read(db, shift)


def close_cashier_shift(
    db: Session,
    tenant_id: int,
    user_id: int,
    shift_id: int,
    data: CashierShiftCloseRequest,
) -> CashierShiftRead:
    shift = _get_cashier_shift(db, tenant_id, shift_id)
    if shift.status != CashierShiftStatus.OPEN:
        raise ConflictError("Shift is already closed")

    closed_at = datetime.utcnow()
    tender, refunds_total = _shift_tender_totals(
        db, tenant_id, shift.outlet_id, shift.opened_at, closed_at
    )
    expected_cash = round(float(shift.opening_float) + tender.cash, 2)
    declared = round(float(data.declared_cash), 2)
    variance = round(declared - expected_cash, 2)

    shift.status = CashierShiftStatus.CLOSED
    shift.closed_at = closed_at
    shift.closed_by = user_id
    shift.declared_cash = declared
    shift.expected_cash = expected_cash
    shift.cash_variance = variance
    shift.tender_cash = tender.cash
    shift.tender_card = tender.card
    shift.tender_upi = tender.upi
    shift.tender_other = tender.other
    shift.payments_total = tender.total
    shift.refunds_total = refunds_total
    if data.notes:
        shift.notes = ((shift.notes or "").rstrip() + "\n" + data.notes.strip()).strip()

    db.commit()
    db.refresh(shift)
    return _cashier_shift_to_read(db, shift, live=False)


def get_cashier_shift(
    db: Session,
    tenant_id: int,
    shift_id: int,
) -> CashierShiftRead:
    shift = _get_cashier_shift(db, tenant_id, shift_id)
    return _cashier_shift_to_read(db, shift)


def _next_city_ledger_reference(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"CL-{year}-"
    count = (
        db.query(func.count(CityLedgerEntry.id))
        .filter(CityLedgerEntry.tenant_id == tenant_id, CityLedgerEntry.reference.like(f"{prefix}%"))
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:05d}"


def _city_ledger_to_read(
    entry: CityLedgerEntry,
    confirmation_number: str | None = None,
    group_code: str | None = None,
) -> CityLedgerRead:
    return CityLedgerRead(
        id=entry.id,
        tenant_id=entry.tenant_id,
        brand_id=entry.brand_id,
        outlet_id=entry.outlet_id,
        reservation_id=entry.reservation_id,
        group_id=getattr(entry, "group_id", None),
        folio_id=entry.folio_id,
        reference=entry.reference,
        company_name=entry.company_name,
        guest_name=entry.guest_name,
        original_amount=float(entry.original_amount),
        balance=float(entry.balance),
        status=entry.status.value if hasattr(entry.status, "value") else str(entry.status),
        notes=entry.notes,
        created_by=entry.created_by,
        settled_at=entry.settled_at,
        settled_by=entry.settled_by,
        confirmation_number=confirmation_number,
        group_code=group_code,
        created_at=entry.created_at,
        updated_at=entry.updated_at,
    )


def _get_city_ledger_entry(db: Session, tenant_id: int, entry_id: int) -> CityLedgerEntry:
    entry = (
        db.query(CityLedgerEntry)
        .filter(
            CityLedgerEntry.id == entry_id,
            CityLedgerEntry.tenant_id == tenant_id,
            CityLedgerEntry.is_active.is_(True),
        )
        .first()
    )
    if entry is None:
        raise NotFoundError("City ledger entry not found")
    return entry


def transfer_folio_to_city_ledger(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: CityLedgerTransferRequest,
) -> CityLedgerTransferResponse:
    reservation = _get_reservation(db, tenant_id, reservation_id)
    if not reservation.folio:
        raise NotFoundError("Guest folio not found")
    if reservation.folio.status != FolioStatus.OPEN:
        raise ConflictError("Guest folio is closed")

    amount = round(float(data.amount), 2)
    balance = float(reservation.folio.balance)
    if amount > balance + 0.009:
        raise ConflictError(f"Transfer amount exceeds folio balance (₹{balance:,.2f})")

    company = data.company_name.strip()
    reference = _next_city_ledger_reference(db, tenant_id)
    _add_folio_entry(
        db,
        reservation.folio,
        FolioEntryType.PAYMENT,
        f"City ledger transfer · {reference} · {company}",
        amount,
        posted_by=user_id,
    )

    entry = CityLedgerEntry(
        tenant_id=tenant_id,
        brand_id=reservation.brand_id,
        outlet_id=reservation.outlet_id,
        reservation_id=reservation.id,
        folio_id=reservation.folio.id,
        reference=reference,
        company_name=company,
        guest_name=reservation.guest_name,
        original_amount=amount,
        balance=amount,
        status=CityLedgerStatus.OPEN,
        notes=data.notes,
        created_by=user_id,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    db.refresh(reservation.folio)

    return CityLedgerTransferResponse(
        folio=_folio_to_read(reservation.folio),
        city_ledger=_city_ledger_to_read(entry, reservation.confirmation_number),
        message=f"₹{amount:,.2f} transferred to city ledger {reference}",
    )


def list_city_ledger(
    db: Session,
    tenant_id: int,
    outlet_id: int | None = None,
    status: str | None = None,
    limit: int = 50,
) -> list[CityLedgerRead]:
    q = db.query(CityLedgerEntry).filter(
        CityLedgerEntry.tenant_id == tenant_id,
        CityLedgerEntry.is_active.is_(True),
    )
    if outlet_id is not None:
        q = q.filter(CityLedgerEntry.outlet_id == outlet_id)
    if status:
        q = q.filter(CityLedgerEntry.status == status)
    rows = q.order_by(CityLedgerEntry.created_at.desc()).limit(min(limit, 200)).all()
    conf_map: dict[int, str] = {}
    res_ids = [r.reservation_id for r in rows if r.reservation_id]
    if res_ids:
        for res in (
            db.query(GuestReservation.id, GuestReservation.confirmation_number)
            .filter(GuestReservation.id.in_(res_ids))
            .all()
        ):
            conf_map[res.id] = res.confirmation_number
    return [
        _city_ledger_to_read(row, conf_map.get(row.reservation_id) if row.reservation_id else None)
        for row in rows
    ]


def get_city_ledger_entry(
    db: Session,
    tenant_id: int,
    entry_id: int,
) -> CityLedgerRead:
    entry = _get_city_ledger_entry(db, tenant_id, entry_id)
    conf = None
    if entry.reservation_id:
        res = db.get(GuestReservation, entry.reservation_id)
        conf = res.confirmation_number if res else None
    return _city_ledger_to_read(entry, conf)


def settle_city_ledger(
    db: Session,
    tenant_id: int,
    user_id: int,
    entry_id: int,
    data: CityLedgerSettleRequest,
) -> CityLedgerRead:
    entry = _get_city_ledger_entry(db, tenant_id, entry_id)
    if entry.status in {CityLedgerStatus.SETTLED, CityLedgerStatus.WRITTEN_OFF}:
        raise ConflictError("City ledger entry is already closed")

    remaining = float(entry.balance)
    pay = round(float(data.amount if data.amount is not None else remaining), 2)
    if pay <= 0:
        raise ConflictError("Settlement amount must be positive")
    if pay > remaining + 0.009:
        raise ConflictError(f"Settlement exceeds open balance (₹{remaining:,.2f})")

    entry.balance = round(remaining - pay, 2)
    note_line = f"Settled ₹{pay:,.2f} via {data.tender.value}"
    if data.notes:
        note_line = f"{note_line} — {data.notes.strip()}"
    entry.notes = ((entry.notes or "").rstrip() + "\n" + note_line).strip()

    if entry.balance <= 0.009:
        entry.balance = 0
        entry.status = CityLedgerStatus.SETTLED
        entry.settled_at = datetime.utcnow()
        entry.settled_by = user_id
    else:
        entry.status = CityLedgerStatus.PARTIAL

    db.commit()
    db.refresh(entry)
    conf = None
    if entry.reservation_id:
        res = db.get(GuestReservation, entry.reservation_id)
        conf = res.confirmation_number if res else None
    return _city_ledger_to_read(entry, conf)


def write_off_city_ledger(
    db: Session,
    tenant_id: int,
    user_id: int,
    entry_id: int,
    data: CityLedgerWriteOffRequest,
) -> CityLedgerRead:
    entry = _get_city_ledger_entry(db, tenant_id, entry_id)
    if entry.status in {CityLedgerStatus.SETTLED, CityLedgerStatus.WRITTEN_OFF}:
        raise ConflictError("City ledger entry is already closed")

    note = data.notes.strip() if data.notes else "Written off"
    entry.notes = ((entry.notes or "").rstrip() + f"\nWrite-off: {note}").strip()
    entry.balance = 0
    entry.status = CityLedgerStatus.WRITTEN_OFF
    entry.settled_at = datetime.utcnow()
    entry.settled_by = user_id
    db.commit()
    db.refresh(entry)
    conf = None
    if entry.reservation_id:
        res = db.get(GuestReservation, entry.reservation_id)
        conf = res.confirmation_number if res else None
    return _city_ledger_to_read(entry, conf)


SERVICE_REQUEST_CATALOG: list[tuple[GuestServiceRequestCategory, str, str]] = [
    (GuestServiceRequestCategory.TOWELS, "Extra towels", "Request fresh towels for your room"),
    (GuestServiceRequestCategory.BEDSHEETS, "Change bedsheets", "Request a bedsheet change"),
    (GuestServiceRequestCategory.TOILETRIES, "Toiletries", "Request soap, shampoo, or other toiletries"),
    (GuestServiceRequestCategory.HOUSEKEEPING, "Room cleaning", "Request housekeeping to clean your room"),
    (GuestServiceRequestCategory.WIFI_HELP, "WiFi help", "Need help connecting to WiFi"),
    (GuestServiceRequestCategory.MAINTENANCE_ISSUE, "Report an issue", "Report a maintenance or room issue"),
    (GuestServiceRequestCategory.OTHER, "Other request", "Any other service request"),
]

_CATEGORY_LABELS = {code: label for code, label, _ in SERVICE_REQUEST_CATALOG}


def _public_service_catalog() -> list[PublicServiceCatalogItem]:
    return [
        PublicServiceCatalogItem(code=code, label=label, description=desc)
        for code, label, desc in SERVICE_REQUEST_CATALOG
    ]


def _find_outlet_room(db: Session, outlet_id: int, room_number: str) -> tuple[Outlet, HotelRoom]:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    room_key = room_number.strip().upper()
    room = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == outlet.tenant_id,
            HotelRoom.outlet_id == outlet.id,
            HotelRoom.is_active.is_(True),
            func.upper(HotelRoom.room_number) == room_key,
        )
        .first()
    )
    if room is None:
        raise NotFoundError("Room not found at this property")
    return outlet, room


def _checked_in_reservation_for_room(
    db: Session, tenant_id: int, outlet_id: int, room_id: int
) -> GuestReservation | None:
    return (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.outlet_id == outlet_id,
            GuestReservation.room_id == room_id,
            GuestReservation.status == ReservationStatus.CHECKED_IN,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )


def get_public_room_hub(
    db: Session,
    outlet_id: int,
    room_number: str,
    guest_mobile: str | None = None,
) -> PublicRoomHubResponse:
    from app.modules.settings import service as settings_service

    outlet, room = _find_outlet_room(db, outlet_id, room_number)
    reservation = _checked_in_reservation_for_room(db, outlet.tenant_id, outlet.id, room.id)
    wifi_cfg = settings_service.get_guest_wifi_config(db, outlet.tenant_id, outlet.id)
    menu_path = (
        f"/menu-card?outlet={outlet.id}&room={room.room_number}&type=room_service"
    )
    spa_path = f"/book-spa?outlet={outlet.id}"
    booking_path = f"/book-room?outlet={outlet.id}"

    stay_unlocked = False
    confirmation_number = None
    check_in_date = None
    check_out_date = None
    nights = None
    room_type_name = None
    folio_balance = None
    folio_number = None
    has_folio = False
    status = None
    package_entitlements: list[PackageEntitlementRead] = []
    can_express_checkout = False
    express_checkout_status = ExpressCheckoutStatus.NONE.value
    express_checkout_at = None
    express_checkout_notes = None
    estimated_departure_time = None
    balance_due = False
    upsell_catalog: list = []
    purchased_addons: list = []

    if reservation is not None:
        status = reservation.status.value if hasattr(reservation.status, "value") else str(reservation.status)
        if guest_mobile and _mobiles_match(reservation.guest_mobile or "", guest_mobile):
            stay_unlocked = True
            confirmation_number = reservation.confirmation_number
            check_in_date = reservation.check_in_date
            check_out_date = reservation.check_out_date
            nights = max((reservation.check_out_date - reservation.check_in_date).days, 1)
            room_type = (
                db.query(RoomType)
                .filter(RoomType.id == reservation.room_type_id)
                .first()
            )
            room_type_name = room_type.name if room_type else None
            folio = (
                db.query(GuestFolio)
                .filter(
                    GuestFolio.reservation_id == reservation.id,
                    GuestFolio.is_active.is_(True),
                )
                .first()
            )
            if folio is not None:
                has_folio = True
                folio_number = folio.folio_number
                folio_balance = float(folio.balance or 0)
            balance_due = float(folio_balance or 0) > 0.01
            express_checkout_status = (
                getattr(reservation, "express_checkout_status", None)
                or ExpressCheckoutStatus.NONE.value
            )
            express_checkout_at = getattr(reservation, "express_checkout_at", None)
            express_checkout_notes = getattr(reservation, "express_checkout_notes", None)
            estimated_departure_time = getattr(reservation, "estimated_departure_time", None)
            can_express_checkout = express_checkout_status in {
                ExpressCheckoutStatus.NONE.value,
                ExpressCheckoutStatus.CANCELLED.value,
            }
            package_entitlements = [
                ent
                for ent in _list_reservation_entitlement_reads(db, reservation.id)
                if ent.qty_total > 0 or ent.credit_total > 0
            ]
            upsell_catalog = list_public_addons()
            purchased_addons = _addon_lines_to_read(getattr(reservation, "addons_json", None))

    return PublicRoomHubResponse(
        outlet_id=outlet.id,
        outlet_name=outlet.outlet_name,
        room_id=room.id,
        room_number=room.room_number,
        floor=room.floor,
        guest_name=(reservation.guest_name if reservation else room.guest_name),
        reservation_id=reservation.id if reservation else None,
        is_checked_in=reservation is not None,
        stay_unlocked=stay_unlocked,
        confirmation_number=confirmation_number,
        check_in_date=check_in_date,
        check_out_date=check_out_date,
        nights=nights,
        room_type_name=room_type_name,
        folio_balance=folio_balance,
        folio_number=folio_number,
        has_folio=has_folio,
        status=status,
        wifi=PublicRoomHubWifi(
            ssid=wifi_cfg.get("ssid") or "",
            password=wifi_cfg.get("password") or "",
            notes=wifi_cfg.get("notes") or "",
        ),
        service_catalog=_public_service_catalog(),
        menu_url_path=menu_path,
        spa_url_path=spa_path,
        booking_url_path=booking_path,
        package_entitlements=package_entitlements,
        can_express_checkout=can_express_checkout,
        express_checkout_status=express_checkout_status,
        express_checkout_at=express_checkout_at,
        express_checkout_notes=express_checkout_notes,
        estimated_departure_time=estimated_departure_time,
        balance_due=balance_due,
        upsell_catalog=upsell_catalog if stay_unlocked else [],
        purchased_addons=purchased_addons if stay_unlocked else [],
    )


def submit_public_room_hub_upsell(
    db: Session,
    data: PublicRoomHubUpsellRequest,
) -> PublicRoomHubResponse:
    import json

    outlet, room = _find_outlet_room(db, data.outlet_id, data.room_number)
    reservation = _checked_in_reservation_for_room(
        db, outlet.tenant_id, outlet.id, room.id
    )
    if reservation is None:
        raise ConflictError("No checked-in guest in this room")
    if not _mobiles_match(reservation.guest_mobile or "", data.guest_mobile):
        raise NotFoundError("Stay not found for this mobile")

    folio = _ensure_folio(db, reservation)
    if folio.status != FolioStatus.OPEN:
        raise ConflictError("Folio is closed — cannot add charges")

    remaining_nights = max(
        (reservation.check_out_date - max(date.today(), reservation.check_in_date)).days,
        1,
    )
    lines = resolve_addon_lines(
        [{"code": data.code, "quantity": data.quantity}],
        nights=remaining_nights,
        adults=int(reservation.adults or 1),
        children=int(reservation.children or 0),
    )
    if not lines:
        raise ConflictError("Unknown or invalid add-on")

    total = addon_total(lines)
    existing = parse_addon_lines(getattr(reservation, "addons_json", None))
    new_rows = json.loads(dump_addon_lines(lines))
    reservation.addons_json = json.dumps(existing + new_rows)
    reservation.total_amount = round(float(reservation.total_amount or 0) + total, 2)
    summary = ", ".join(f"{line.name}×{line.quantity}" for line in lines)
    reservation.notes = (
        (reservation.notes or "") + f"\nMid-stay add-on: {summary}"
    ).strip()

    for line in lines:
        _add_folio_entry(
            db,
            folio,
            FolioEntryType.POS_CHARGE,
            f"Mid-stay · {line.description}",
            line.total,
            posted_by=None,
        )
    db.commit()
    return get_public_room_hub(
        db, data.outlet_id, data.room_number, guest_mobile=data.guest_mobile
    )


def submit_public_express_checkout(
    db: Session,
    data: PublicExpressCheckoutRequest,
) -> PublicRoomHubResponse:
    outlet, room = _find_outlet_room(db, data.outlet_id, data.room_number)
    reservation = _checked_in_reservation_for_room(
        db, outlet.tenant_id, outlet.id, room.id
    )
    if reservation is None:
        raise ConflictError("No checked-in guest in this room")
    if not _mobiles_match(reservation.guest_mobile or "", data.guest_mobile):
        raise NotFoundError("Stay not found for this mobile")

    current = (
        getattr(reservation, "express_checkout_status", None)
        or ExpressCheckoutStatus.NONE.value
    )
    if current == ExpressCheckoutStatus.SUBMITTED.value:
        raise ConflictError("Express checkout already requested — front desk will follow up")
    if current == ExpressCheckoutStatus.COMPLETED.value:
        raise ConflictError("Express checkout already completed")

    reservation.express_checkout_status = ExpressCheckoutStatus.SUBMITTED.value
    reservation.express_checkout_at = datetime.utcnow()
    reservation.express_checkout_notes = (data.notes or "").strip() or None
    reservation.estimated_departure_time = (
        data.estimated_departure_time.strip() if data.estimated_departure_time else None
    )
    db.commit()
    return get_public_room_hub(
        db, data.outlet_id, data.room_number, guest_mobile=data.guest_mobile
    )


def complete_express_checkout(
    db: Session,
    tenant_id: int,
    user_id: int,
    reservation_id: int,
    data: ExpressCheckoutCompleteRequest | None = None,
) -> ReservationDetailRead:
    payload = data or ExpressCheckoutCompleteRequest()
    reservation = _get_reservation(db, tenant_id, reservation_id)
    current = (
        getattr(reservation, "express_checkout_status", None)
        or ExpressCheckoutStatus.NONE.value
    )
    if current != ExpressCheckoutStatus.SUBMITTED.value:
        raise ConflictError("No express checkout request to complete")
    if reservation.status != ReservationStatus.CHECKED_IN:
        raise ConflictError("Guest is not checked in")

    folio = reservation.folio
    balance = float(folio.balance) if folio else 0.0
    if balance > 0.01 and not payload.force_settle:
        raise ConflictError(
            f"Folio balance ₹{balance:.2f} must be settled before completing express checkout"
        )

    result = check_out_reservation(
        db,
        tenant_id,
        user_id,
        reservation_id,
        CheckOutRequest(notes=payload.notes, force_settle=payload.force_settle),
    )
    refreshed = _get_reservation(db, tenant_id, reservation_id)
    refreshed.express_checkout_status = ExpressCheckoutStatus.COMPLETED.value
    refreshed.express_checkout_reviewed_at = datetime.utcnow()
    db.commit()
    return get_reservation(db, tenant_id, reservation_id)


def _create_guest_request_task(
    db: Session,
    *,
    tenant_id: int,
    room: HotelRoom,
    category: GuestServiceRequestCategory,
    notes: str | None,
) -> int:
    from app.modules.housekeeping.models import (
        HousekeepingTask,
        HousekeepingTaskStatus,
        HousekeepingTaskType,
        MaintenancePriority,
    )

    label = _CATEGORY_LABELS.get(category, category.value)
    task_notes = f"Guest request: {label}"
    if notes:
        task_notes = f"{task_notes}\n{notes.strip()}"

    task = HousekeepingTask(
        tenant_id=tenant_id,
        brand_id=room.brand_id,
        outlet_id=room.outlet_id,
        room_id=room.id,
        task_type=HousekeepingTaskType.GUEST_REQUEST,
        status=HousekeepingTaskStatus.PENDING,
        assigned_to=room.assigned_housekeeper_id,
        priority=MaintenancePriority.MEDIUM,
        due_at=datetime.utcnow() + timedelta(hours=2),
        notes=task_notes,
    )
    db.add(task)
    db.flush()
    hk_service._create_checklist_from_template(  # noqa: SLF001
        db, task, None, HousekeepingTaskType.GUEST_REQUEST
    )
    return task.id


def _create_guest_maintenance_ticket(
    db: Session,
    *,
    tenant_id: int,
    room: HotelRoom,
    notes: str | None,
) -> int:
    from app.modules.housekeeping.models import (
        MaintenanceCategory,
        MaintenancePriority,
        MaintenanceTicket,
        MaintenanceTicketStatus,
    )

    description = (notes or "").strip() or "Guest reported a room issue via QR hub"
    ticket = MaintenanceTicket(
        tenant_id=tenant_id,
        brand_id=room.brand_id,
        outlet_id=room.outlet_id,
        room_id=room.id,
        ticket_number=hk_service._generate_ticket_number(db, tenant_id),  # noqa: SLF001
        title=f"Guest issue · Room {room.room_number}",
        description=description,
        category=MaintenanceCategory.OTHER,
        priority=MaintenancePriority.MEDIUM,
        status=MaintenanceTicketStatus.OPEN,
        reported_by=None,
    )
    db.add(ticket)
    db.flush()
    return ticket.id


def create_public_service_request(
    db: Session, data: PublicServiceRequestCreate
) -> PublicServiceRequestResponse:
    outlet, room = _find_outlet_room(db, data.outlet_id, data.room_number)
    reservation = _checked_in_reservation_for_room(db, outlet.tenant_id, outlet.id, room.id)

    linked_task_id: int | None = None
    linked_ticket_id: int | None = None
    if data.category == GuestServiceRequestCategory.MAINTENANCE_ISSUE:
        linked_ticket_id = _create_guest_maintenance_ticket(
            db, tenant_id=outlet.tenant_id, room=room, notes=data.notes
        )
    else:
        linked_task_id = _create_guest_request_task(
            db,
            tenant_id=outlet.tenant_id,
            room=room,
            category=data.category,
            notes=data.notes,
        )

    req = GuestServiceRequest(
        tenant_id=outlet.tenant_id,
        brand_id=room.brand_id or outlet.brand_id,
        outlet_id=outlet.id,
        room_id=room.id,
        room_number=room.room_number,
        reservation_id=reservation.id if reservation else None,
        category=GuestServiceRequestCategoryModel(data.category.value),
        notes=(data.notes.strip() if data.notes else None),
        guest_mobile=(data.guest_mobile.strip() if data.guest_mobile else None),
        status=GuestServiceRequestStatusModel.OPEN,
        linked_task_id=linked_task_id,
        linked_ticket_id=linked_ticket_id,
    )
    db.add(req)
    db.commit()
    db.refresh(req)

    label = _CATEGORY_LABELS.get(data.category, data.category.value)
    return PublicServiceRequestResponse(
        id=req.id,
        room_number=req.room_number,
        category=data.category,
        status=GuestServiceRequestStatus.OPEN,
        message=f"Request received for {label}. Our team will assist shortly.",
    )


def _service_request_to_read(req: GuestServiceRequest) -> GuestServiceRequestRead:
    guest_name = getattr(req, "_guest_name", None)
    return GuestServiceRequestRead(
        id=req.id,
        outlet_id=req.outlet_id,
        room_id=req.room_id,
        room_number=req.room_number,
        reservation_id=req.reservation_id,
        guest_name=guest_name,
        category=GuestServiceRequestCategory(req.category.value),
        notes=req.notes,
        guest_mobile=req.guest_mobile,
        status=GuestServiceRequestStatus(req.status.value),
        linked_task_id=req.linked_task_id,
        linked_ticket_id=req.linked_ticket_id,
        fulfilled_at=req.fulfilled_at,
        fulfilled_by=req.fulfilled_by,
        staff_reply=req.staff_reply,
        guest_notified_at=req.guest_notified_at,
        created_at=req.created_at,
        updated_at=req.updated_at,
    )


def list_public_service_requests(
    db: Session,
    outlet_id: int,
    room_number: str,
    *,
    limit: int = 20,
) -> list[PublicGuestServiceRequestRead]:
    outlet, room = _find_outlet_room(db, outlet_id, room_number)
    rows = (
        db.query(GuestServiceRequest)
        .filter(
            GuestServiceRequest.tenant_id == outlet.tenant_id,
            GuestServiceRequest.outlet_id == outlet.id,
            GuestServiceRequest.room_id == room.id,
            GuestServiceRequest.is_active.is_(True),
        )
        .order_by(GuestServiceRequest.created_at.desc())
        .limit(limit)
        .all()
    )
    results: list[PublicGuestServiceRequestRead] = []
    for req in rows:
        category = GuestServiceRequestCategory(req.category.value)
        results.append(
            PublicGuestServiceRequestRead(
                id=req.id,
                room_number=req.room_number,
                category=category,
                category_label=_CATEGORY_LABELS.get(category, category.value),
                notes=req.notes,
                status=GuestServiceRequestStatus(req.status.value),
                staff_reply=req.staff_reply,
                created_at=req.created_at,
                fulfilled_at=req.fulfilled_at,
                guest_notified_at=req.guest_notified_at,
            )
        )
    return results


def list_service_requests(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    status_filter: GuestServiceRequestStatus | None = None,
) -> list[GuestServiceRequestRead]:
    query = (
        db.query(GuestServiceRequest)
        .filter(
            GuestServiceRequest.tenant_id == tenant_id,
            GuestServiceRequest.outlet_id == outlet_id,
            GuestServiceRequest.is_active.is_(True),
        )
        .order_by(GuestServiceRequest.created_at.desc())
    )
    if status_filter is not None:
        query = query.filter(
            GuestServiceRequest.status == GuestServiceRequestStatusModel(status_filter.value)
        )
    rows = query.all()
    reservation_ids = [r.reservation_id for r in rows if r.reservation_id]
    names: dict[int, str] = {}
    if reservation_ids:
        for res in (
            db.query(GuestReservation.id, GuestReservation.guest_name)
            .filter(GuestReservation.id.in_(reservation_ids))
            .all()
        ):
            names[res.id] = res.guest_name
    results: list[GuestServiceRequestRead] = []
    for row in rows:
        setattr(row, "_guest_name", names.get(row.reservation_id) if row.reservation_id else None)
        results.append(_service_request_to_read(row))
    return results


async def fulfill_service_request(
    db: Session,
    tenant_id: int,
    user_id: int,
    request_id: int,
    data: GuestServiceRequestFulfillRequest | None = None,
) -> GuestServiceRequestFulfillResponse:
    from app.modules.communications import service as comms_service
    from app.modules.communications.models import MessageChannel
    from app.modules.communications.schemas import SmsSendRequest, WhatsAppSendRequest
    from app.modules.housekeeping.models import (
        HousekeepingTask,
        HousekeepingTaskStatus,
        MaintenanceTicket,
        MaintenanceTicketStatus,
    )

    payload = data or GuestServiceRequestFulfillRequest()
    req = (
        db.query(GuestServiceRequest)
        .filter(
            GuestServiceRequest.id == request_id,
            GuestServiceRequest.tenant_id == tenant_id,
            GuestServiceRequest.is_active.is_(True),
        )
        .first()
    )
    if req is None:
        raise NotFoundError("Service request not found")
    if req.status != GuestServiceRequestStatusModel.OPEN:
        raise ConflictError("Service request is already closed")

    reply = (payload.staff_reply or "").strip() or None
    req.status = GuestServiceRequestStatusModel.FULFILLED
    req.fulfilled_at = datetime.utcnow()
    req.fulfilled_by = user_id
    req.staff_reply = reply

    if req.linked_task_id:
        task = (
            db.query(HousekeepingTask)
            .filter(HousekeepingTask.id == req.linked_task_id, HousekeepingTask.tenant_id == tenant_id)
            .first()
        )
        if task and task.status in {
            HousekeepingTaskStatus.PENDING,
            HousekeepingTaskStatus.IN_PROGRESS,
        }:
            task.status = HousekeepingTaskStatus.COMPLETED
            task.completed_at = datetime.utcnow()

    if req.linked_ticket_id:
        ticket = (
            db.query(MaintenanceTicket)
            .filter(
                MaintenanceTicket.id == req.linked_ticket_id,
                MaintenanceTicket.tenant_id == tenant_id,
            )
            .first()
        )
        if ticket and ticket.status not in {
            MaintenanceTicketStatus.RESOLVED,
            MaintenanceTicketStatus.CLOSED,
        }:
            ticket.status = MaintenanceTicketStatus.RESOLVED
            ticket.resolved_at = datetime.utcnow()
            ticket.resolution_notes = reply or "Fulfilled via front desk guest service request"

    notified = False
    notify_mobile = (req.guest_mobile or "").strip()
    if not notify_mobile and req.reservation_id:
        reservation = db.get(GuestReservation, req.reservation_id)
        if reservation and reservation.tenant_id == tenant_id:
            notify_mobile = (reservation.guest_mobile or "").strip()

    if payload.notify_guest and notify_mobile:
        label = _CATEGORY_LABELS.get(
            GuestServiceRequestCategory(req.category.value),
            req.category.value,
        )
        body = (
            f"Your request ({label}) for Room {req.room_number} is complete."
            + (f" Note: {reply}" if reply else "")
        )
        try:
            sent = False
            if comms_service.is_channel_enabled(
                db, tenant_id, MessageChannel.SMS, brand_id=req.brand_id, outlet_id=req.outlet_id
            ):
                await comms_service.send_mock_sms(
                    db,
                    tenant_id,
                    user_id,
                    SmsSendRequest(
                        receiver=notify_mobile,
                        message_text=body,
                        outlet_id=req.outlet_id,
                        brand_id=req.brand_id,
                    ),
                    default_brand_id=req.brand_id,
                )
                sent = True
            elif comms_service.is_channel_enabled(
                db,
                tenant_id,
                MessageChannel.WHATSAPP,
                brand_id=req.brand_id,
                outlet_id=req.outlet_id,
            ):
                await comms_service.send_mock_whatsapp(
                    db,
                    tenant_id,
                    user_id,
                    WhatsAppSendRequest(
                        receiver=notify_mobile,
                        message_text=body,
                        outlet_id=req.outlet_id,
                        brand_id=req.brand_id,
                    ),
                    default_brand_id=req.brand_id,
                )
                sent = True
            if sent:
                req.guest_notified_at = datetime.utcnow()
                notified = True
        except Exception:
            # Fulfillment should succeed even if notify fails
            notified = False

    db.commit()
    message = "Service request marked fulfilled"
    if notified:
        message = f"{message} · guest notified"
    elif payload.notify_guest and not notify_mobile:
        message = f"{message} · no guest mobile to notify"
    return GuestServiceRequestFulfillResponse(
        message=message,
        id=req.id,
        status=GuestServiceRequestStatus.FULFILLED,
        notified=notified,
        staff_reply=reply,
    )
