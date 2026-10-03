from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.banquet.models import BanquetBooking, BanquetBookingStatus, BanquetVenue
from app.modules.banquet.schemas import (
    BanquetAvailabilityRead,
    BanquetAvailabilitySlot,
    BanquetBookingCreate,
    BanquetBookingRead,
    BanquetBookingUpdate,
    BanquetCalendarRead,
    BanquetCalendarBooking,
    BanquetCalendarVenueColumn,
    BanquetDashboard,
    BanquetNotificationKind,
    BanquetNotificationResponse,
    BanquetReminderBatchResult,
    BanquetVenueCreate,
    BanquetVenueRead,
    BanquetVenueUpdate,
    PublicBanquetInquiryCreate,
    PublicBanquetInquiryResponse,
    PublicBanquetVenueRead,
)
from app.modules.outlets.models import Outlet
from app.modules.pms.models import GuestReservation
from app.modules.users.models import User


_ACTIVE_BOOKING_STATUSES = {
    BanquetBookingStatus.INQUIRY,
    BanquetBookingStatus.TENTATIVE,
    BanquetBookingStatus.CONFIRMED,
}

_PUBLIC_SLOT_WINDOWS: tuple[tuple[str, str, str], ...] = (
    ("09:00", "14:00", "Morning half-day"),
    ("14:00", "18:00", "Afternoon half-day"),
    ("18:00", "23:00", "Evening session"),
    ("09:00", "22:00", "Full day"),
)


def list_public_venues(
    db: Session,
    outlet_id: int,
    *,
    venue_type=None,
) -> list[PublicBanquetVenueRead]:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    query = db.query(BanquetVenue).filter(
        BanquetVenue.tenant_id == outlet.tenant_id,
        BanquetVenue.outlet_id == outlet_id,
        BanquetVenue.is_active.is_(True),
    )
    if venue_type is not None:
        query = query.filter(BanquetVenue.venue_type == venue_type)

    return [
        PublicBanquetVenueRead(
            id=row.id,
            outlet_id=row.outlet_id,
            name=row.name,
            venue_type=row.venue_type,
            description=row.description,
            capacity_min=row.capacity_min,
            capacity_max=row.capacity_max,
            half_day_rate=float(row.half_day_rate),
            full_day_rate=float(row.full_day_rate),
            amenities=row.amenities,
        )
        for row in query.order_by(BanquetVenue.name.asc()).all()
    ]


def get_public_venue_availability(
    db: Session,
    outlet_id: int,
    venue_id: int,
    target_date: date,
) -> BanquetAvailabilityRead:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    venue = (
        db.query(BanquetVenue)
        .filter(
            BanquetVenue.id == venue_id,
            BanquetVenue.tenant_id == outlet.tenant_id,
            BanquetVenue.outlet_id == outlet_id,
            BanquetVenue.is_active.is_(True),
        )
        .first()
    )
    if venue is None:
        raise NotFoundError("Banquet venue not found")

    slots: list[BanquetAvailabilitySlot] = []
    for start_time, end_time, label in _PUBLIC_SLOT_WINDOWS:
        try:
            _ensure_venue_available(
                db,
                outlet.tenant_id,
                venue_id,
                target_date,
                start_time,
                end_time,
            )
            is_available = True
        except ConflictError:
            is_available = False
        slots.append(
            BanquetAvailabilitySlot(
                start_time=start_time,
                end_time=end_time,
                label=label,
                is_available=is_available,
            )
        )

    return BanquetAvailabilityRead(venue_id=venue_id, date=target_date, slots=slots)


def submit_public_inquiry(
    db: Session,
    data: PublicBanquetInquiryCreate,
) -> PublicBanquetInquiryResponse:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    venue = (
        db.query(BanquetVenue)
        .filter(
            BanquetVenue.id == data.venue_id,
            BanquetVenue.tenant_id == outlet.tenant_id,
            BanquetVenue.outlet_id == data.outlet_id,
            BanquetVenue.is_active.is_(True),
        )
        .first()
    )
    if venue is None:
        raise NotFoundError("Banquet venue not found")

    notes = data.notes or "Online event inquiry"
    if data.notes and "online" not in data.notes.lower():
        notes = f"{data.notes} (online inquiry)"

    duration_hours = (
        datetime.combine(data.event_date, _parse_time(data.end_time))
        - datetime.combine(data.event_date, _parse_time(data.start_time))
    ).total_seconds() / 3600
    estimated = float(venue.full_day_rate) if duration_hours >= 8 else float(venue.half_day_rate)

    payload = BanquetBookingCreate(
        outlet_id=data.outlet_id,
        brand_id=outlet.brand_id,
        venue_id=data.venue_id,
        title=data.title,
        event_type=data.event_type,
        event_date=data.event_date,
        start_time=data.start_time,
        end_time=data.end_time,
        guest_count=data.guest_count,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        notes=notes,
        estimated_amount=estimated,
        advance_paid=0,
    )
    created = create_booking(db, outlet.tenant_id, payload, default_brand_id=outlet.brand_id)

    return PublicBanquetInquiryResponse(
        booking_id=created.id,
        booking_number=created.booking_number,
        message=(
            "Thank you! Your event inquiry has been received. "
            "Our events team will contact you shortly to confirm details and pricing."
        ),
        status=created.status,
    )


def get_dashboard(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
) -> BanquetDashboard:
    venues_query = db.query(BanquetVenue).filter(BanquetVenue.tenant_id == tenant_id)
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        venues_query = venues_query.filter(BanquetVenue.outlet_id == outlet_id)
    venues = venues_query.all()

    bookings_query = (
        db.query(BanquetBooking)
        .options(joinedload(BanquetBooking.venue))
        .filter(
            BanquetBooking.tenant_id == tenant_id,
            BanquetBooking.is_active.is_(True),
            BanquetBooking.event_date >= date.today(),
            BanquetBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
        )
    )
    if outlet_id is not None:
        bookings_query = bookings_query.filter(BanquetBooking.outlet_id == outlet_id)

    upcoming_rows = bookings_query.order_by(BanquetBooking.event_date.asc(), BanquetBooking.start_time.asc()).all()
    inquiry_count = sum(1 for row in upcoming_rows if row.status == BanquetBookingStatus.INQUIRY)
    confirmed_upcoming = sum(1 for row in upcoming_rows if row.status == BanquetBookingStatus.CONFIRMED)

    return BanquetDashboard(
        total_venues=len(venues),
        active_venues=sum(1 for row in venues if row.is_active),
        upcoming_bookings=len(upcoming_rows),
        confirmed_upcoming=confirmed_upcoming,
        inquiry_count=inquiry_count,
        upcoming_events=[_to_booking_read(db, row) for row in upcoming_rows[:8]],
    )


def get_venue_calendar(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    target_date: date,
) -> BanquetCalendarRead:
    _get_outlet(db, tenant_id, outlet_id)

    venues = (
        db.query(BanquetVenue)
        .filter(
            BanquetVenue.tenant_id == tenant_id,
            BanquetVenue.outlet_id == outlet_id,
            BanquetVenue.is_active.is_(True),
        )
        .order_by(BanquetVenue.name.asc())
        .all()
    )

    bookings = (
        db.query(BanquetBooking)
        .filter(
            BanquetBooking.tenant_id == tenant_id,
            BanquetBooking.outlet_id == outlet_id,
            BanquetBooking.is_active.is_(True),
            BanquetBooking.event_date == target_date,
            BanquetBooking.status.in_(
                _ACTIVE_BOOKING_STATUSES | {BanquetBookingStatus.COMPLETED}
            ),
        )
        .order_by(BanquetBooking.start_time.asc())
        .all()
    )

    bookings_by_venue: dict[int, list[BanquetCalendarBooking]] = {venue.id: [] for venue in venues}
    for booking in bookings:
        if booking.venue_id not in bookings_by_venue:
            continue
        bookings_by_venue[booking.venue_id].append(_to_calendar_booking(booking))

    columns = [
        BanquetCalendarVenueColumn(
            venue_id=venue.id,
            name=venue.name,
            venue_type=venue.venue_type,
            capacity_min=venue.capacity_min,
            capacity_max=venue.capacity_max,
            bookings=bookings_by_venue.get(venue.id, []),
        )
        for venue in venues
    ]

    return BanquetCalendarRead(date=target_date, outlet_id=outlet_id, venues=columns)


def _to_calendar_booking(booking: BanquetBooking) -> BanquetCalendarBooking:
    return BanquetCalendarBooking(
        id=booking.id,
        booking_number=booking.booking_number,
        title=booking.title,
        event_type=booking.event_type,
        start_time=booking.start_time,
        end_time=booking.end_time,
        guest_count=booking.guest_count,
        status=booking.status,
        contact_name=booking.contact_name,
    )


def list_venues(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    *,
    outlet_id: int | None = None,
    include_inactive: bool = False,
) -> tuple[list[BanquetVenueRead], int]:
    query = db.query(BanquetVenue).filter(BanquetVenue.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(BanquetVenue.is_active.is_(True))
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(BanquetVenue.outlet_id == outlet_id)
    query = query.order_by(BanquetVenue.name.asc())
    rows, total = paginate_query(query, page, page_size)
    return [BanquetVenueRead.model_validate(row) for row in rows], total


def create_venue(
    db: Session,
    tenant_id: int,
    data: BanquetVenueCreate,
    default_brand_id: int | None = None,
) -> BanquetVenueRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    if data.capacity_max < data.capacity_min:
        raise ConflictError("Maximum capacity must be greater than or equal to minimum capacity")

    venue = BanquetVenue(
        tenant_id=tenant_id,
        brand_id=data.brand_id or outlet.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        name=data.name,
        venue_type=data.venue_type,
        description=data.description,
        capacity_min=data.capacity_min,
        capacity_max=data.capacity_max,
        half_day_rate=data.half_day_rate,
        full_day_rate=data.full_day_rate,
        amenities=data.amenities,
    )
    db.add(venue)
    db.commit()
    db.refresh(venue)
    return BanquetVenueRead.model_validate(venue)


def update_venue(
    db: Session,
    tenant_id: int,
    venue_id: int,
    data: BanquetVenueUpdate,
) -> BanquetVenueRead:
    venue = _get_venue(db, tenant_id, venue_id)
    payload = data.model_dump(exclude_unset=True)
    cap_min = payload.get("capacity_min", venue.capacity_min)
    cap_max = payload.get("capacity_max", venue.capacity_max)
    if cap_max < cap_min:
        raise ConflictError("Maximum capacity must be greater than or equal to minimum capacity")
    for key, value in payload.items():
        setattr(venue, key, value)
    db.commit()
    db.refresh(venue)
    return BanquetVenueRead.model_validate(venue)


def list_bookings(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    *,
    outlet_id: int | None = None,
    venue_id: int | None = None,
    status: BanquetBookingStatus | None = None,
    guest_reservation_id: int | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
) -> tuple[list[BanquetBookingRead], int]:
    query = (
        db.query(BanquetBooking)
        .options(joinedload(BanquetBooking.venue))
        .filter(BanquetBooking.tenant_id == tenant_id, BanquetBooking.is_active.is_(True))
    )
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(BanquetBooking.outlet_id == outlet_id)
    if venue_id is not None:
        query = query.filter(BanquetBooking.venue_id == venue_id)
    if status is not None:
        query = query.filter(BanquetBooking.status == status)
    if guest_reservation_id is not None:
        query = query.filter(BanquetBooking.guest_reservation_id == guest_reservation_id)
    if from_date is not None:
        query = query.filter(BanquetBooking.event_date >= from_date)
    if to_date is not None:
        query = query.filter(BanquetBooking.event_date <= to_date)
    query = query.order_by(BanquetBooking.event_date.desc(), BanquetBooking.start_time.desc())
    rows, total = paginate_query(query, page, page_size)
    return [_to_booking_read(db, row) for row in rows], total


def get_booking(db: Session, tenant_id: int, booking_id: int) -> BanquetBookingRead:
    return _to_booking_read(db, _get_booking(db, tenant_id, booking_id))


def create_booking(
    db: Session,
    tenant_id: int,
    data: BanquetBookingCreate,
    default_brand_id: int | None = None,
) -> BanquetBookingRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    venue = _get_venue(db, tenant_id, data.venue_id)
    if venue.outlet_id != data.outlet_id:
        raise ConflictError("Venue does not belong to this outlet")
    if data.guest_count < venue.capacity_min or data.guest_count > venue.capacity_max:
        raise ConflictError(f"Guest count must be between {venue.capacity_min} and {venue.capacity_max}")
    if data.guest_reservation_id is not None:
        _get_guest_reservation(db, tenant_id, data.guest_reservation_id)
    _validate_time_window(data.start_time, data.end_time)
    _ensure_venue_available(
        db,
        tenant_id,
        data.venue_id,
        data.event_date,
        data.start_time,
        data.end_time,
    )

    booking = BanquetBooking(
        tenant_id=tenant_id,
        brand_id=data.brand_id or outlet.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        venue_id=venue.id,
        booking_number=_next_booking_number(db, tenant_id),
        title=data.title,
        event_type=data.event_type,
        status=BanquetBookingStatus.INQUIRY,
        event_date=data.event_date,
        start_time=data.start_time,
        end_time=data.end_time,
        guest_count=data.guest_count,
        contact_name=data.contact_name,
        contact_phone=data.contact_phone,
        contact_email=data.contact_email,
        guest_reservation_id=data.guest_reservation_id,
        notes=data.notes,
        estimated_amount=data.estimated_amount,
        advance_paid=data.advance_paid,
        charge_to_folio=data.charge_to_folio,
    )
    db.add(booking)
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def update_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    data: BanquetBookingUpdate,
) -> BanquetBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    payload = data.model_dump(exclude_unset=True)

    venue_id = payload.get("venue_id", booking.venue_id)
    event_date = payload.get("event_date", booking.event_date)
    start_time = payload.get("start_time", booking.start_time)
    end_time = payload.get("end_time", booking.end_time)
    guest_count = payload.get("guest_count", booking.guest_count)

    if "venue_id" in payload:
        venue = _get_venue(db, tenant_id, venue_id)
        if venue.outlet_id != booking.outlet_id:
            raise ConflictError("Venue does not belong to this outlet")
    else:
        venue = _get_venue(db, tenant_id, venue_id)

    if guest_count < venue.capacity_min or guest_count > venue.capacity_max:
        raise ConflictError(f"Guest count must be between {venue.capacity_min} and {venue.capacity_max}")

    if any(key in payload for key in ("start_time", "end_time")):
        _validate_time_window(start_time, end_time)

    if any(key in payload for key in ("venue_id", "event_date", "start_time", "end_time")):
        _ensure_venue_available(
            db,
            tenant_id,
            venue_id,
            event_date,
            start_time,
            end_time,
            exclude_booking_id=booking.id,
        )

    if "guest_reservation_id" in payload and payload["guest_reservation_id"] is not None:
        _get_guest_reservation(db, tenant_id, payload["guest_reservation_id"])

    for key, value in payload.items():
        setattr(booking, key, value)

    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def confirm_booking(db: Session, tenant_id: int, booking_id: int) -> BanquetBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status in {BanquetBookingStatus.COMPLETED, BanquetBookingStatus.CANCELLED}:
        raise ConflictError("Booking cannot be confirmed")
    booking.status = BanquetBookingStatus.CONFIRMED
    booking.confirmed_at = datetime.utcnow()
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def _format_event_schedule(booking: BanquetBooking) -> str:
    return f"{booking.event_date.strftime('%d %b %Y')} · {booking.start_time}–{booking.end_time}"


def _build_banquet_notification_message(
    booking: BanquetBooking,
    outlet_name: str,
    kind: BanquetNotificationKind,
) -> tuple[str, str]:
    venue_name = booking.venue.name if booking.venue else "Event venue"
    when = _format_event_schedule(booking)
    event_label = booking.event_type.value.replace("_", " ").title()

    if kind == BanquetNotificationKind.INQUIRY_RECEIVED:
        body = (
            f"Hi {booking.contact_name}!\n\n"
            f"We received your inquiry for {booking.title} at {outlet_name} "
            f"({venue_name}) on {when} (Ref: {booking.booking_number}).\n"
            f"Our events team will contact you shortly with availability and a proposal."
        )
        subject = f"Event inquiry received — {booking.booking_number}"
    elif kind == BanquetNotificationKind.REMINDER:
        body = (
            f"Hi {booking.contact_name}! 👋\n\n"
            f"Reminder: your {event_label} event \"{booking.title}\" at {venue_name}, {outlet_name} "
            f"is scheduled for {when} (Ref: {booking.booking_number}).\n"
            f"Guest count: {booking.guest_count}. We look forward to hosting you!"
        )
        subject = f"Reminder: {booking.title} — {booking.booking_number}"
    else:
        body = (
            f"Hi {booking.contact_name}! ✨\n\n"
            f"Your {event_label} event \"{booking.title}\" at {venue_name}, {outlet_name} "
            f"is confirmed for {when} (Ref: {booking.booking_number}).\n"
            f"Guest count: {booking.guest_count}."
        )
        if float(booking.estimated_amount) > 0:
            body += f"\nEstimated amount: ₹{float(booking.estimated_amount):,.0f}."
        if float(booking.advance_paid) > 0:
            body += f"\nAdvance received: ₹{float(booking.advance_paid):,.0f}."
        body += "\nSee you soon!"
        subject = f"Confirmed: {booking.title} — {booking.booking_number}"
    return body, subject


async def send_booking_notifications(
    db: Session,
    tenant_id: int,
    user_id: int,
    booking_id: int,
    *,
    kind: BanquetNotificationKind,
    send_sms: bool = False,
    send_email: bool = False,
    send_whatsapp: bool = False,
) -> BanquetNotificationResponse:
    from app.modules.communications import service as comms_service
    from app.modules.communications.models import MessageChannel
    from app.modules.communications.schemas import EmailSendRequest, SmsSendRequest, WhatsAppSendRequest

    if not send_sms and not send_email and not send_whatsapp:
        raise ConflictError("Select at least one notification channel")

    booking = _get_booking(db, tenant_id, booking_id)
    outlet = _get_outlet(db, tenant_id, booking.outlet_id)
    body, subject = _build_banquet_notification_message(booking, outlet.outlet_name, kind)
    sent_channels: list[str] = []

    if send_sms and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.SMS, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.contact_phone:
            raise ConflictError("Contact phone is required to send SMS")
        await comms_service.send_mock_sms(
            db,
            tenant_id,
            user_id,
            SmsSendRequest(
                receiver=booking.contact_phone,
                message_text=body,
                outlet_id=booking.outlet_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("sms")

    if send_whatsapp and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.WHATSAPP, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.contact_phone:
            raise ConflictError("Contact phone is required to send WhatsApp")
        await comms_service.send_mock_whatsapp(
            db,
            tenant_id,
            user_id,
            WhatsAppSendRequest(
                receiver=booking.contact_phone,
                message_text=body,
                outlet_id=booking.outlet_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("whatsapp")

    if send_email and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.EMAIL, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.contact_email:
            raise ConflictError("Contact email is required to send email")
        await comms_service.send_mock_email(
            db,
            tenant_id,
            user_id,
            EmailSendRequest(
                receiver=booking.contact_email,
                subject=subject,
                message_text=body,
                outlet_id=booking.outlet_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("email")

    if not sent_channels:
        raise ConflictError("No notification channels are enabled for this outlet")

    db.commit()
    return BanquetNotificationResponse(
        message=f"Notification sent via {', '.join(sent_channels)}",
        booking_id=booking.id,
        sent_channels=sent_channels,
        message_preview=body,
    )


async def send_public_inquiry_acknowledgment(
    db: Session,
    tenant_id: int,
    booking_id: int,
) -> BanquetNotificationResponse | None:
    booking = _get_booking(db, tenant_id, booking_id)
    send_sms = bool(booking.contact_phone)
    send_email = bool(booking.contact_email)
    send_whatsapp = bool(booking.contact_phone)
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

    return await send_booking_notifications(
        db,
        tenant_id,
        admin.id,
        booking_id,
        kind=BanquetNotificationKind.INQUIRY_RECEIVED,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )


def build_booking_automation_payload(booking: BanquetBookingRead) -> dict:
    return {
        "booking_id": booking.id,
        "booking_number": booking.booking_number,
        "contact_name": booking.contact_name,
        "contact_phone": booking.contact_phone,
        "contact_email": booking.contact_email,
        "title": booking.title,
        "event_type": booking.event_type.value if hasattr(booking.event_type, "value") else booking.event_type,
        "venue_name": booking.venue_name,
        "event_date": booking.event_date.isoformat() if hasattr(booking.event_date, "isoformat") else booking.event_date,
        "start_time": booking.start_time,
        "end_time": booking.end_time,
        "guest_count": booking.guest_count,
        "outlet_id": booking.outlet_id,
        "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
    }


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


def _booking_event_datetime(booking: BanquetBooking) -> datetime:
    return datetime.combine(booking.event_date, _parse_time(booking.start_time))


async def _send_booking_reminder(
    db: Session,
    tenant_id: int,
    booking_id: int,
    *,
    config: dict | None = None,
) -> bool:
    from app.modules.settings.service import get_banquet_reminder_config

    booking = _get_booking(db, tenant_id, booking_id)
    if booking.reminder_sent_at is not None:
        return False
    if booking.status != BanquetBookingStatus.CONFIRMED:
        return False

    reminder_config = config or get_banquet_reminder_config(db, tenant_id, booking.outlet_id)
    if not reminder_config.get("enabled", True):
        return False

    user_id = _get_system_user_id(db, tenant_id)
    if user_id is None:
        return False

    send_sms = reminder_config.get("send_sms", True) and bool(booking.contact_phone)
    send_email = reminder_config.get("send_email", True) and bool(booking.contact_email)
    send_whatsapp = reminder_config.get("send_whatsapp", True) and bool(booking.contact_phone)
    if not send_sms and not send_email and not send_whatsapp:
        return False

    await send_booking_notifications(
        db,
        tenant_id,
        user_id,
        booking_id,
        kind=BanquetNotificationKind.REMINDER,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )
    booking.reminder_sent_at = datetime.utcnow()
    db.commit()
    return True


def _is_banquet_booking_due(
    booking: BanquetBooking,
    *,
    now: datetime,
    hours_before: int,
    window_minutes: int,
) -> bool:
    target = _booking_event_datetime(booking)
    window_start = now + timedelta(hours=hours_before) - timedelta(minutes=window_minutes)
    window_end = now + timedelta(hours=hours_before) + timedelta(minutes=window_minutes)
    return window_start <= target <= window_end


def run_due_banquet_reminders_all_tenants(
    db: Session,
    *,
    hours_before: int | None = None,
    window_minutes: int | None = None,
) -> BanquetReminderBatchResult:
    import asyncio

    from app.core.config import settings
    from app.modules.settings.service import get_banquet_reminder_config
    from app.modules.tenants.models import Tenant

    default_hours = hours_before if hours_before is not None else settings.banquet_reminder_hours_before
    default_window = window_minutes if window_minutes is not None else settings.banquet_reminder_window_minutes
    now = datetime.utcnow()
    max_scan_hours = 168 if hours_before is None else default_hours + 1
    scan_start = now - timedelta(minutes=default_window + 30)
    scan_end = now + timedelta(hours=max_scan_hours) + timedelta(minutes=default_window + 30)

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    reminders_sent = 0
    bookings_checked = 0
    config_cache: dict[tuple[int, int], dict] = {}

    for tenant in tenants:
        candidates = (
            db.query(BanquetBooking)
            .options(joinedload(BanquetBooking.venue))
            .filter(
                BanquetBooking.tenant_id == tenant.id,
                BanquetBooking.is_active.is_(True),
                BanquetBooking.status == BanquetBookingStatus.CONFIRMED,
                BanquetBooking.reminder_sent_at.is_(None),
                BanquetBooking.event_date >= scan_start.date(),
                BanquetBooking.event_date <= scan_end.date(),
            )
            .all()
        )
        for booking in candidates:
            cache_key = (tenant.id, booking.outlet_id)
            if cache_key not in config_cache:
                config_cache[cache_key] = get_banquet_reminder_config(db, tenant.id, booking.outlet_id)
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
            if not _is_banquet_booking_due(
                booking,
                now=now,
                hours_before=outlet_hours,
                window_minutes=outlet_window,
            ):
                continue

            bookings_checked += 1
            try:
                sent = asyncio.run(
                    _send_booking_reminder(
                        db,
                        tenant.id,
                        booking.id,
                        config=reminder_config,
                    )
                )
                if sent:
                    reminders_sent += 1
            except Exception:
                db.rollback()
                continue

    return BanquetReminderBatchResult(
        message=f"Banquet reminders sent: {reminders_sent}",
        reminders_sent=reminders_sent,
        tenants_processed=len(tenants),
        bookings_checked=bookings_checked,
    )


def cancel_booking(db: Session, tenant_id: int, booking_id: int) -> BanquetBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status == BanquetBookingStatus.COMPLETED:
        raise ConflictError("Completed bookings cannot be cancelled")
    booking.status = BanquetBookingStatus.CANCELLED
    booking.cancelled_at = datetime.utcnow()
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def complete_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    *,
    post_to_folio: bool = True,
    posted_by: int | None = None,
) -> BanquetBookingRead:
    from app.modules.pms import service as pms_service

    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status not in {BanquetBookingStatus.CONFIRMED, BanquetBookingStatus.TENTATIVE}:
        raise ConflictError("Only confirmed or tentative bookings can be completed")
    booking.status = BanquetBookingStatus.COMPLETED
    db.flush()

    if post_to_folio and booking.charge_to_folio and booking.guest_reservation_id:
        try:
            pms_service.post_banquet_booking_to_folio(db, tenant_id, posted_by, booking.id)
        except (ConflictError, NotFoundError):
            pass

    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def post_deposit_to_folio(
    db: Session,
    tenant_id: int,
    booking_id: int,
    posted_by: int | None = None,
) -> BanquetBookingRead:
    from app.modules.pms import service as pms_service

    pms_service.post_banquet_deposit_to_folio(db, tenant_id, posted_by, booking_id)
    db.commit()
    booking = _get_booking(db, tenant_id, booking_id)
    return _to_booking_read(db, booking)


def post_booking_to_folio(
    db: Session,
    tenant_id: int,
    booking_id: int,
    posted_by: int | None = None,
) -> BanquetBookingRead:
    from app.modules.pms import service as pms_service

    pms_service.post_banquet_booking_to_folio(db, tenant_id, posted_by, booking_id)
    db.commit()
    booking = _get_booking(db, tenant_id, booking_id)
    return _to_booking_read(db, booking)


def _next_booking_number(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"BQT-{year}-"
    last = (
        db.query(BanquetBooking)
        .filter(
            BanquetBooking.tenant_id == tenant_id,
            BanquetBooking.booking_number.like(f"{prefix}%"),
        )
        .order_by(BanquetBooking.id.desc())
        .first()
    )
    if last is None:
        seq = 1
    else:
        seq = int(last.booking_number.rsplit("-", 1)[-1]) + 1
    return f"{prefix}{seq:04d}"


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_venue(db: Session, tenant_id: int, venue_id: int) -> BanquetVenue:
    venue = (
        db.query(BanquetVenue)
        .filter(BanquetVenue.id == venue_id, BanquetVenue.tenant_id == tenant_id, BanquetVenue.is_active.is_(True))
        .first()
    )
    if venue is None:
        raise NotFoundError("Banquet venue not found")
    return venue


def _get_booking(db: Session, tenant_id: int, booking_id: int) -> BanquetBooking:
    booking = (
        db.query(BanquetBooking)
        .options(joinedload(BanquetBooking.venue))
        .filter(
            BanquetBooking.id == booking_id,
            BanquetBooking.tenant_id == tenant_id,
            BanquetBooking.is_active.is_(True),
        )
        .first()
    )
    if booking is None:
        raise NotFoundError("Banquet booking not found")
    return booking


def _get_guest_reservation(db: Session, tenant_id: int, reservation_id: int) -> GuestReservation:
    reservation = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.id == reservation_id,
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
        )
        .first()
    )
    if reservation is None:
        raise NotFoundError("Guest reservation not found")
    return reservation


def _parse_time(value: str) -> time:
    return datetime.strptime(value, "%H:%M").time()


def _validate_time_window(start_time: str, end_time: str) -> None:
    start = _parse_time(start_time)
    end = _parse_time(end_time)
    if end <= start:
        raise ConflictError("End time must be after start time")


def _ensure_venue_available(
    db: Session,
    tenant_id: int,
    venue_id: int,
    event_date: date,
    start_time: str,
    end_time: str,
    *,
    exclude_booking_id: int | None = None,
) -> None:
    start = datetime.combine(event_date, _parse_time(start_time))
    end = datetime.combine(event_date, _parse_time(end_time))
    query = db.query(BanquetBooking).filter(
        BanquetBooking.tenant_id == tenant_id,
        BanquetBooking.venue_id == venue_id,
        BanquetBooking.event_date == event_date,
        BanquetBooking.is_active.is_(True),
        BanquetBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
    )
    if exclude_booking_id is not None:
        query = query.filter(BanquetBooking.id != exclude_booking_id)

    for row in query.all():
        row_start = datetime.combine(event_date, _parse_time(row.start_time))
        row_end = datetime.combine(event_date, _parse_time(row.end_time))
        if _intervals_overlap(start, end, row_start, row_end):
            raise ConflictError("Venue is already booked for this time slot")


def _intervals_overlap(a_start: datetime, a_end: datetime, b_start: datetime, b_end: datetime) -> bool:
    return a_start < b_end and b_start < a_end


def _to_booking_read(db: Session, booking: BanquetBooking) -> BanquetBookingRead:
    from app.modules.pms.models import FolioEntry, FolioEntryType

    data = BanquetBookingRead.model_validate(booking)
    if booking.venue is not None:
        data.venue_name = booking.venue.name
        data.venue_type = booking.venue.venue_type
    data.balance_due = max(float(booking.estimated_amount) - float(booking.advance_paid), 0)
    if booking.folio_posted_at is not None:
        entry = (
            db.query(FolioEntry)
            .filter(
                FolioEntry.banquet_booking_id == booking.id,
                FolioEntry.entry_type == FolioEntryType.BANQUET_CHARGE,
            )
            .order_by(FolioEntry.id.desc())
            .first()
        )
        if entry:
            data.folio_entry_id = entry.id
    if booking.deposit_folio_posted_at is not None:
        entry = (
            db.query(FolioEntry)
            .filter(
                FolioEntry.banquet_booking_id == booking.id,
                FolioEntry.entry_type == FolioEntryType.DEPOSIT,
            )
            .order_by(FolioEntry.id.desc())
            .first()
        )
        if entry:
            data.deposit_folio_entry_id = entry.id
    return data
