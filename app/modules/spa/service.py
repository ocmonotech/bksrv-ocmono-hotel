from __future__ import annotations

import uuid
from datetime import date, datetime, time, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.customers.models import Customer
from app.modules.outlets.models import Outlet
from app.modules.pms.models import GuestReservation
from app.modules.spa.models import SpaBooking, SpaBookingStatus, SpaService, SpaTherapist
from app.modules.spa.schemas import (
    SpaAvailabilityRead,
    SpaAvailabilitySlot,
    SpaBookingCreate,
    SpaBookingRead,
    SpaBookingUpdate,
    SpaCalendarBooking,
    SpaCalendarRead,
    SpaCalendarTherapistColumn,
    SpaDashboard,
    PublicSpaBookingCreate,
    PublicSpaBookingResponse,
    PublicSpaServiceRead,
    SpaBookingConfirmRequest,
    SpaNotificationKind,
    SpaNotificationRequest,
    SpaNotificationResponse,
    SpaReminderBatchResult,
    SpaServiceCreate,
    SpaServiceRead,
    SpaServiceUpdate,
    SpaTherapistCreate,
    SpaTherapistRead,
    SpaTherapistUpdate,
)
from app.modules.users.models import User

_ACTIVE_BOOKING_STATUSES = {
    SpaBookingStatus.PENDING,
    SpaBookingStatus.CONFIRMED,
    SpaBookingStatus.IN_PROGRESS,
}


def get_dashboard(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
) -> SpaDashboard:
    today = date.today()
    day_start = datetime.combine(today, time.min)
    day_end = datetime.combine(today, time.max)

    services_query = db.query(SpaService).filter(
        SpaService.tenant_id == tenant_id,
        SpaService.is_active.is_(True),
    )
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        services_query = services_query.filter(SpaService.outlet_id == outlet_id)

    services = services_query.all()
    total_services = len(services)
    active_services = sum(1 for row in services if row.is_active)

    bookings_query = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(
            SpaBooking.tenant_id == tenant_id,
            SpaBooking.is_active.is_(True),
            SpaBooking.booked_at >= day_start,
            SpaBooking.booked_at <= day_end,
        )
    )
    if outlet_id is not None:
        bookings_query = bookings_query.filter(SpaBooking.outlet_id == outlet_id)

    today_rows = bookings_query.order_by(SpaBooking.booked_at.asc()).all()
    pending_today = sum(1 for row in today_rows if row.status == SpaBookingStatus.PENDING)
    confirmed_today = sum(1 for row in today_rows if row.status == SpaBookingStatus.CONFIRMED)
    in_progress_today = sum(1 for row in today_rows if row.status == SpaBookingStatus.IN_PROGRESS)

    upcoming_query = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(
            SpaBooking.tenant_id == tenant_id,
            SpaBooking.is_active.is_(True),
            SpaBooking.booked_at >= datetime.utcnow(),
            SpaBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
        )
    )
    if outlet_id is not None:
        upcoming_query = upcoming_query.filter(SpaBooking.outlet_id == outlet_id)

    upcoming = upcoming_query.order_by(SpaBooking.booked_at.asc()).limit(8).all()

    return SpaDashboard(
        total_services=total_services,
        active_services=active_services,
        today_bookings=len(today_rows),
        pending_today=pending_today,
        confirmed_today=confirmed_today,
        in_progress_today=in_progress_today,
        upcoming_bookings=[_to_booking_read(db, row) for row in upcoming],
    )


def list_services(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    *,
    outlet_id: int | None = None,
    category=None,
    include_inactive: bool = False,
) -> tuple[list[SpaServiceRead], int]:
    query = db.query(SpaService).filter(SpaService.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(SpaService.is_active.is_(True))
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(SpaService.outlet_id == outlet_id)
    if category is not None:
        query = query.filter(SpaService.category == category)

    rows, total = paginate_query(query.order_by(SpaService.name.asc()), page, page_size)
    return [_to_service_read(row) for row in rows], total


def create_service(
    db: Session,
    tenant_id: int,
    data: SpaServiceCreate,
    default_brand_id: int | None = None,
) -> SpaServiceRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    _validate_operating_hours(data.operating_start, data.operating_end)

    service = SpaService(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        name=data.name,
        category=data.category,
        description=data.description,
        duration_minutes=data.duration_minutes,
        price=data.price,
        max_capacity=data.max_capacity,
        slot_interval_minutes=data.slot_interval_minutes,
        operating_start=data.operating_start,
        operating_end=data.operating_end,
    )
    db.add(service)
    db.commit()
    db.refresh(service)
    return _to_service_read(service)


def update_service(
    db: Session,
    tenant_id: int,
    service_id: int,
    data: SpaServiceUpdate,
) -> SpaServiceRead:
    service = _get_service(db, tenant_id, service_id)
    payload = data.model_dump(exclude_unset=True)
    start = payload.get("operating_start", service.operating_start)
    end = payload.get("operating_end", service.operating_end)
    if "operating_start" in payload or "operating_end" in payload:
        _validate_operating_hours(start, end)

    for key, value in payload.items():
        setattr(service, key, value)
    db.commit()
    db.refresh(service)
    return _to_service_read(service)


def get_service_availability(
    db: Session,
    tenant_id: int,
    service_id: int,
    target_date: date,
) -> SpaAvailabilityRead:
    service = _get_service(db, tenant_id, service_id)
    day_start = datetime.combine(target_date, _parse_time(service.operating_start))
    day_end = datetime.combine(target_date, _parse_time(service.operating_end))

    bookings = (
        db.query(SpaBooking)
        .filter(
            SpaBooking.tenant_id == tenant_id,
            SpaBooking.service_id == service_id,
            SpaBooking.is_active.is_(True),
            SpaBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
            SpaBooking.booked_at >= day_start,
            SpaBooking.booked_at < day_end + timedelta(days=1),
        )
        .all()
    )

    slots: list[SpaAvailabilitySlot] = []
    cursor = day_start
    step = timedelta(minutes=service.slot_interval_minutes)
    duration = timedelta(minutes=service.duration_minutes)

    while cursor + duration <= day_end:
        slot_end = cursor + duration
        overlap_count = sum(
            1
            for booking in bookings
            if _intervals_overlap(cursor, slot_end, booking.booked_at, booking.booked_at + timedelta(minutes=booking.duration_minutes))
        )
        available = max(service.max_capacity - overlap_count, 0)
        slots.append(
            SpaAvailabilitySlot(
                start_time=cursor.strftime("%H:%M"),
                end_time=slot_end.strftime("%H:%M"),
                available_capacity=available,
                is_available=available > 0,
            )
        )
        cursor += step

    return SpaAvailabilityRead(service_id=service_id, date=target_date, slots=slots)


def list_bookings(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    *,
    outlet_id: int | None = None,
    service_id: int | None = None,
    status: SpaBookingStatus | None = None,
    from_date: date | None = None,
    to_date: date | None = None,
    guest_reservation_id: int | None = None,
    assigned_staff_id: int | None = None,
) -> tuple[list[SpaBookingRead], int]:
    query = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(SpaBooking.tenant_id == tenant_id, SpaBooking.is_active.is_(True))
    )
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(SpaBooking.outlet_id == outlet_id)
    if service_id is not None:
        _get_service(db, tenant_id, service_id)
        query = query.filter(SpaBooking.service_id == service_id)
    if status is not None:
        query = query.filter(SpaBooking.status == status)
    if from_date is not None:
        query = query.filter(SpaBooking.booked_at >= datetime.combine(from_date, time.min))
    if to_date is not None:
        query = query.filter(SpaBooking.booked_at <= datetime.combine(to_date, time.max))
    if guest_reservation_id is not None:
        query = query.filter(SpaBooking.guest_reservation_id == guest_reservation_id)
    if assigned_staff_id is not None:
        query = query.filter(SpaBooking.assigned_staff_id == assigned_staff_id)

    rows, total = paginate_query(query.order_by(SpaBooking.booked_at.desc()), page, page_size)
    return [_to_booking_read(db, row) for row in rows], total


def get_booking(db: Session, tenant_id: int, booking_id: int) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    return _to_booking_read(db, booking)


def create_booking(
    db: Session,
    tenant_id: int,
    data: SpaBookingCreate,
    default_brand_id: int | None = None,
) -> SpaBookingRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    service = _get_service(db, tenant_id, data.service_id)
    if service.outlet_id != data.outlet_id:
        raise ConflictError("Service does not belong to this outlet")

    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    if data.customer_id is not None:
        _get_customer(db, tenant_id, data.customer_id)
    if data.guest_reservation_id is not None:
        _get_guest_reservation(db, tenant_id, data.guest_reservation_id)
    if data.assigned_staff_id is not None:
        _get_therapist_for_user(db, tenant_id, data.outlet_id, data.assigned_staff_id)

    _ensure_capacity(db, service, data.booked_at, data.party_size)
    if data.assigned_staff_id is not None:
        _ensure_staff_available(
            db,
            tenant_id,
            data.assigned_staff_id,
            data.booked_at,
            service.duration_minutes,
        )

    booking = SpaBooking(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        service_id=service.id,
        booking_number=_next_booking_number(db, tenant_id),
        status=SpaBookingStatus.PENDING,
        booked_at=data.booked_at,
        duration_minutes=service.duration_minutes,
        party_size=data.party_size,
        price=float(service.price) * data.party_size,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        guest_email=data.guest_email,
        customer_id=data.customer_id,
        guest_reservation_id=data.guest_reservation_id,
        assigned_staff_id=data.assigned_staff_id,
        notes=data.notes,
        charge_to_folio=data.charge_to_folio,
    )
    db.add(booking)
    db.commit()
    db.refresh(booking)
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def update_booking(
    db: Session,
    tenant_id: int,
    booking_id: int,
    data: SpaBookingUpdate,
) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    payload = data.model_dump(exclude_unset=True)

    if "customer_id" in payload and payload["customer_id"] is not None:
        _get_customer(db, tenant_id, payload["customer_id"])
    if "guest_reservation_id" in payload and payload["guest_reservation_id"] is not None:
        _get_guest_reservation(db, tenant_id, payload["guest_reservation_id"])
    if "assigned_staff_id" in payload and payload["assigned_staff_id"] is not None:
        _get_therapist_for_user(db, tenant_id, booking.outlet_id, payload["assigned_staff_id"])

    new_time = payload.get("booked_at", booking.booked_at)
    new_party = payload.get("party_size", booking.party_size)
    new_staff = payload.get("assigned_staff_id", booking.assigned_staff_id)
    if "booked_at" in payload or "party_size" in payload:
        _ensure_capacity(
            db,
            booking.service,
            new_time,
            new_party,
            exclude_booking_id=booking.id,
        )
    if new_staff is not None and ("booked_at" in payload or "assigned_staff_id" in payload):
        duration = payload.get("duration_minutes", booking.duration_minutes)
        _ensure_staff_available(
            db,
            tenant_id,
            new_staff,
            new_time,
            duration,
            exclude_booking_id=booking.id,
        )

    for key, value in payload.items():
        setattr(booking, key, value)

    if "party_size" in payload:
        booking.price = float(booking.service.price) * booking.party_size

    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def confirm_booking(db: Session, tenant_id: int, booking_id: int) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status not in {SpaBookingStatus.PENDING, SpaBookingStatus.CONFIRMED}:
        raise ConflictError("Only pending bookings can be confirmed")
    booking.status = SpaBookingStatus.CONFIRMED
    booking.confirmed_at = datetime.utcnow()
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def _format_booking_datetime(booked_at: datetime) -> str:
    return booked_at.strftime("%d %b %Y at %H:%M")


def _build_spa_notification_message(
    booking: SpaBooking,
    outlet_name: str,
    kind: SpaNotificationKind,
    *,
    assigned_staff_name: str | None = None,
) -> tuple[str, str]:
    service_name = booking.service.name if booking.service else "Spa service"
    when = _format_booking_datetime(booking.booked_at)
    therapist_line = f"\nTherapist: {assigned_staff_name}" if assigned_staff_name else ""

    if kind == SpaNotificationKind.REQUEST_RECEIVED:
        body = (
            f"Hi {booking.guest_name}!\n\n"
            f"We received your spa request for {service_name} at {outlet_name} "
            f"on {when} (Ref: {booking.booking_number}).\n"
            f"Our team will confirm your appointment shortly."
        )
        subject = f"Spa request received — {booking.booking_number}"
    elif kind == SpaNotificationKind.REMINDER:
        body = (
            f"Hi {booking.guest_name}! 👋\n\n"
            f"Reminder: your {service_name} appointment at {outlet_name} "
            f"is on {when} (Ref: {booking.booking_number}).{therapist_line}\n"
            f"We look forward to seeing you!"
        )
        subject = f"Reminder: {service_name} — {booking.booking_number}"
    else:
        body = (
            f"Hi {booking.guest_name}! ✨\n\n"
            f"Your {service_name} appointment at {outlet_name} is confirmed "
            f"for {when} (Ref: {booking.booking_number}).{therapist_line}\n"
            f"Duration: {booking.duration_minutes} min · Party size: {booking.party_size}.\n"
            f"See you soon!"
        )
        subject = f"Confirmed: {service_name} — {booking.booking_number}"
    return body, subject


async def send_booking_notifications(
    db: Session,
    tenant_id: int,
    user_id: int,
    booking_id: int,
    *,
    kind: SpaNotificationKind,
    send_sms: bool = False,
    send_email: bool = False,
    send_whatsapp: bool = False,
) -> SpaNotificationResponse:
    from app.modules.communications import service as comms_service
    from app.modules.communications.models import MessageChannel
    from app.modules.communications.schemas import EmailSendRequest, SmsSendRequest, WhatsAppSendRequest

    if not send_sms and not send_email and not send_whatsapp:
        raise ConflictError("Select at least one notification channel")

    booking = _get_booking(db, tenant_id, booking_id)
    outlet = _get_outlet(db, tenant_id, booking.outlet_id)
    assigned_staff_name = None
    if booking.assigned_staff_id is not None:
        staff = db.get(User, booking.assigned_staff_id)
        assigned_staff_name = staff.full_name if staff else None

    body, subject = _build_spa_notification_message(
        booking,
        outlet.outlet_name,
        kind,
        assigned_staff_name=assigned_staff_name,
    )
    sent_channels: list[str] = []

    if send_sms and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.SMS, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.guest_phone:
            raise ConflictError("Guest phone is required to send SMS")
        await comms_service.send_mock_sms(
            db,
            tenant_id,
            user_id,
            SmsSendRequest(
                receiver=booking.guest_phone,
                message_text=body,
                outlet_id=booking.outlet_id,
                customer_id=booking.customer_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("sms")

    if send_whatsapp and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.WHATSAPP, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.guest_phone:
            raise ConflictError("Guest phone is required to send WhatsApp")
        await comms_service.send_mock_whatsapp(
            db,
            tenant_id,
            user_id,
            WhatsAppSendRequest(
                receiver=booking.guest_phone,
                message_text=body,
                outlet_id=booking.outlet_id,
                customer_id=booking.customer_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("whatsapp")

    if send_email and comms_service.is_channel_enabled(
        db, tenant_id, MessageChannel.EMAIL, brand_id=booking.brand_id, outlet_id=booking.outlet_id
    ):
        if not booking.guest_email:
            raise ConflictError("Guest email is required to send email")
        await comms_service.send_mock_email(
            db,
            tenant_id,
            user_id,
            EmailSendRequest(
                receiver=booking.guest_email,
                subject=subject,
                message_text=body,
                outlet_id=booking.outlet_id,
                customer_id=booking.customer_id,
                brand_id=booking.brand_id,
            ),
            default_brand_id=booking.brand_id,
        )
        sent_channels.append("email")

    if not sent_channels:
        raise ConflictError("No notification channels are enabled for this outlet")

    db.commit()
    return SpaNotificationResponse(
        message=f"Notification sent via {', '.join(sent_channels)}",
        booking_id=booking.id,
        sent_channels=sent_channels,
        message_preview=body,
    )


async def send_public_booking_acknowledgment(
    db: Session,
    tenant_id: int,
    booking_id: int,
) -> SpaNotificationResponse | None:
    booking = _get_booking(db, tenant_id, booking_id)
    send_sms = bool(booking.guest_phone)
    send_email = bool(booking.guest_email)
    send_whatsapp = bool(booking.guest_phone)
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
        kind=SpaNotificationKind.REQUEST_RECEIVED,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )


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


async def _send_booking_reminder(
    db: Session,
    tenant_id: int,
    booking_id: int,
    *,
    config: dict | None = None,
) -> bool:
    from app.modules.settings.service import get_spa_reminder_config

    booking = _get_booking(db, tenant_id, booking_id)
    if booking.reminder_sent_at is not None:
        return False
    if booking.status != SpaBookingStatus.CONFIRMED:
        return False

    reminder_config = config or get_spa_reminder_config(db, tenant_id, booking.outlet_id)
    if not reminder_config.get("enabled", True):
        return False

    user_id = _get_system_user_id(db, tenant_id)
    if user_id is None:
        return False

    send_sms = reminder_config.get("send_sms", True) and bool(booking.guest_phone)
    send_email = reminder_config.get("send_email", True) and bool(booking.guest_email)
    send_whatsapp = reminder_config.get("send_whatsapp", True) and bool(booking.guest_phone)
    if not send_sms and not send_email and not send_whatsapp:
        return False

    await send_booking_notifications(
        db,
        tenant_id,
        user_id,
        booking_id,
        kind=SpaNotificationKind.REMINDER,
        send_sms=send_sms,
        send_email=send_email,
        send_whatsapp=send_whatsapp,
    )
    booking.reminder_sent_at = datetime.utcnow()
    db.commit()
    return True


def _is_spa_booking_due(
    booking: SpaBooking,
    *,
    now: datetime,
    hours_before: int,
    window_minutes: int,
) -> bool:
    target = booking.booked_at
    window_start = now + timedelta(hours=hours_before) - timedelta(minutes=window_minutes)
    window_end = now + timedelta(hours=hours_before) + timedelta(minutes=window_minutes)
    return window_start <= target <= window_end


def run_due_spa_reminders_all_tenants(
    db: Session,
    *,
    hours_before: int | None = None,
    window_minutes: int | None = None,
) -> SpaReminderBatchResult:
    import asyncio

    from app.core.config import settings
    from app.modules.settings.service import get_spa_reminder_config
    from app.modules.tenants.models import Tenant

    default_hours = hours_before if hours_before is not None else settings.spa_reminder_hours_before
    default_window = window_minutes if window_minutes is not None else settings.spa_reminder_window_minutes
    now = datetime.utcnow()
    max_scan_hours = 168 if hours_before is None else default_hours + 1
    scan_start = now - timedelta(minutes=default_window + 30)
    scan_end = now + timedelta(hours=max_scan_hours) + timedelta(minutes=default_window + 30)

    tenants = db.query(Tenant).filter(Tenant.is_active.is_(True)).all()
    reminders_sent = 0
    bookings_checked = 0
    config_cache: dict[tuple[int, int], dict] = {}

    for tenant in tenants:
        bookings = (
            db.query(SpaBooking)
            .options(joinedload(SpaBooking.service))
            .filter(
                SpaBooking.tenant_id == tenant.id,
                SpaBooking.is_active.is_(True),
                SpaBooking.status == SpaBookingStatus.CONFIRMED,
                SpaBooking.reminder_sent_at.is_(None),
                SpaBooking.booked_at >= scan_start,
                SpaBooking.booked_at <= scan_end,
            )
            .all()
        )
        for booking in bookings:
            cache_key = (tenant.id, booking.outlet_id)
            if cache_key not in config_cache:
                config_cache[cache_key] = get_spa_reminder_config(db, tenant.id, booking.outlet_id)
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
            if not _is_spa_booking_due(
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

    return SpaReminderBatchResult(
        message=f"Spa reminders sent: {reminders_sent}",
        reminders_sent=reminders_sent,
        tenants_processed=len(tenants),
        bookings_checked=bookings_checked,
    )


def build_booking_automation_payload(booking: SpaBookingRead) -> dict:
    return {
        "booking_id": booking.id,
        "booking_number": booking.booking_number,
        "guest_name": booking.guest_name,
        "guest_phone": booking.guest_phone,
        "guest_email": booking.guest_email,
        "service_name": booking.service_name,
        "service_id": booking.service_id,
        "booked_at": booking.booked_at.isoformat() if booking.booked_at else None,
        "outlet_id": booking.outlet_id,
        "status": booking.status.value if hasattr(booking.status, "value") else booking.status,
    }


def start_booking(db: Session, tenant_id: int, booking_id: int) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status not in {SpaBookingStatus.PENDING, SpaBookingStatus.CONFIRMED}:
        raise ConflictError("Only confirmed bookings can be started")
    booking.status = SpaBookingStatus.IN_PROGRESS
    booking.started_at = datetime.utcnow()
    if booking.confirmed_at is None:
        booking.confirmed_at = booking.started_at
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
) -> SpaBookingRead:
    from app.modules.pms import service as pms_service

    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status not in {SpaBookingStatus.CONFIRMED, SpaBookingStatus.IN_PROGRESS}:
        raise ConflictError("Only in-progress or confirmed bookings can be completed")
    booking.status = SpaBookingStatus.COMPLETED
    booking.completed_at = datetime.utcnow()
    db.flush()

    if post_to_folio and booking.charge_to_folio and booking.guest_reservation_id:
        try:
            pms_service.post_spa_booking_to_folio(db, tenant_id, posted_by, booking.id)
        except (ConflictError, NotFoundError):
            pass

    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def post_booking_to_folio(
    db: Session,
    tenant_id: int,
    booking_id: int,
    posted_by: int | None = None,
) -> SpaBookingRead:
    from app.modules.pms import service as pms_service

    pms_service.post_spa_booking_to_folio(db, tenant_id, posted_by, booking_id)
    db.commit()
    booking = _get_booking(db, tenant_id, booking_id)
    return _to_booking_read(db, booking)


def assign_booking_staff(
    db: Session,
    tenant_id: int,
    booking_id: int,
    assigned_staff_id: int | None,
) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if assigned_staff_id is not None:
        _get_therapist_for_user(db, tenant_id, booking.outlet_id, assigned_staff_id)
        _ensure_staff_available(
            db,
            tenant_id,
            assigned_staff_id,
            booking.booked_at,
            booking.duration_minutes,
            exclude_booking_id=booking.id,
        )
    booking.assigned_staff_id = assigned_staff_id
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def list_therapists(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
    include_inactive: bool = False,
) -> list[SpaTherapistRead]:
    query = db.query(SpaTherapist).filter(SpaTherapist.tenant_id == tenant_id)
    if not include_inactive:
        query = query.filter(SpaTherapist.is_active.is_(True))
    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(SpaTherapist.outlet_id == outlet_id)
    rows = query.order_by(SpaTherapist.id.asc()).all()
    return [_to_therapist_read(db, row) for row in rows]


def create_therapist(
    db: Session,
    tenant_id: int,
    data: SpaTherapistCreate,
    default_brand_id: int | None = None,
) -> SpaTherapistRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    _get_user(db, tenant_id, data.user_id)
    _validate_operating_hours(data.shift_start, data.shift_end)

    existing = (
        db.query(SpaTherapist)
        .filter(
            SpaTherapist.tenant_id == tenant_id,
            SpaTherapist.outlet_id == data.outlet_id,
            SpaTherapist.user_id == data.user_id,
        )
        .first()
    )
    if existing:
        raise ConflictError("User is already on the spa therapist roster for this outlet")

    therapist = SpaTherapist(
        tenant_id=tenant_id,
        brand_id=data.brand_id or outlet.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        user_id=data.user_id,
        title=data.title,
        specialties=data.specialties,
        shift_start=data.shift_start,
        shift_end=data.shift_end,
        calendar_color=data.calendar_color,
    )
    db.add(therapist)
    db.commit()
    db.refresh(therapist)
    return _to_therapist_read(db, therapist)


def update_therapist(
    db: Session,
    tenant_id: int,
    therapist_id: int,
    data: SpaTherapistUpdate,
) -> SpaTherapistRead:
    therapist = _get_therapist(db, tenant_id, therapist_id)
    payload = data.model_dump(exclude_unset=True)
    start = payload.get("shift_start", therapist.shift_start)
    end = payload.get("shift_end", therapist.shift_end)
    if "shift_start" in payload or "shift_end" in payload:
        _validate_operating_hours(start, end)
    for key, value in payload.items():
        setattr(therapist, key, value)
    db.commit()
    db.refresh(therapist)
    return _to_therapist_read(db, therapist)


def get_therapist_calendar(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    target_date: date,
) -> SpaCalendarRead:
    _get_outlet(db, tenant_id, outlet_id)
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    therapists = (
        db.query(SpaTherapist)
        .filter(
            SpaTherapist.tenant_id == tenant_id,
            SpaTherapist.outlet_id == outlet_id,
            SpaTherapist.is_active.is_(True),
        )
        .order_by(SpaTherapist.id.asc())
        .all()
    )

    bookings = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(
            SpaBooking.tenant_id == tenant_id,
            SpaBooking.outlet_id == outlet_id,
            SpaBooking.is_active.is_(True),
            SpaBooking.booked_at >= day_start,
            SpaBooking.booked_at <= day_end,
            SpaBooking.status.in_(_ACTIVE_BOOKING_STATUSES | {SpaBookingStatus.COMPLETED}),
        )
        .order_by(SpaBooking.booked_at.asc())
        .all()
    )

    columns: list[SpaCalendarTherapistColumn] = []
    for therapist in therapists:
        user = db.get(User, therapist.user_id)
        staff_bookings = [
            _to_calendar_booking(row)
            for row in bookings
            if row.assigned_staff_id == therapist.user_id
        ]
        columns.append(
            SpaCalendarTherapistColumn(
                therapist_id=therapist.id,
                user_id=therapist.user_id,
                name=user.full_name if user else f"Staff #{therapist.user_id}",
                title=therapist.title,
                specialties=therapist.specialties,
                shift_start=therapist.shift_start,
                shift_end=therapist.shift_end,
                calendar_color=therapist.calendar_color,
                bookings=staff_bookings,
            )
        )

    unassigned = [
        _to_calendar_booking(row)
        for row in bookings
        if row.assigned_staff_id is None
    ]

    return SpaCalendarRead(
        date=target_date,
        outlet_id=outlet_id,
        therapists=columns,
        unassigned=unassigned,
    )


def list_public_services(
    db: Session,
    outlet_id: int,
    *,
    category=None,
) -> list[PublicSpaServiceRead]:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    query = db.query(SpaService).filter(
        SpaService.tenant_id == outlet.tenant_id,
        SpaService.outlet_id == outlet_id,
        SpaService.is_active.is_(True),
    )
    if category is not None:
        query = query.filter(SpaService.category == category)

    return [
        PublicSpaServiceRead(
            id=row.id,
            outlet_id=row.outlet_id,
            name=row.name,
            category=row.category,
            description=row.description,
            duration_minutes=row.duration_minutes,
            price=float(row.price),
            operating_start=row.operating_start,
            operating_end=row.operating_end,
        )
        for row in query.order_by(SpaService.name.asc()).all()
    ]


def get_public_service_availability(
    db: Session,
    outlet_id: int,
    service_id: int,
    target_date: date,
) -> SpaAvailabilityRead:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    service_row = (
        db.query(SpaService)
        .filter(
            SpaService.id == service_id,
            SpaService.tenant_id == outlet.tenant_id,
            SpaService.outlet_id == outlet_id,
            SpaService.is_active.is_(True),
        )
        .first()
    )
    if service_row is None:
        raise NotFoundError("Spa service not found")
    return get_service_availability(db, outlet.tenant_id, service_id, target_date)


async def submit_public_booking(
    db: Session,
    data: PublicSpaBookingCreate,
) -> PublicSpaBookingResponse:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    service_row = (
        db.query(SpaService)
        .filter(
            SpaService.id == data.service_id,
            SpaService.tenant_id == outlet.tenant_id,
            SpaService.outlet_id == data.outlet_id,
            SpaService.is_active.is_(True),
        )
        .first()
    )
    if service_row is None:
        raise NotFoundError("Spa service not found")

    _ensure_capacity(db, service_row, data.booked_at, data.party_size)

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
        raise ConflictError("Outlet is not configured for online spa bookings")

    notes = data.notes or "Online self-booking"
    if data.notes and "self-booking" not in data.notes.lower():
        notes = f"{data.notes} (online self-booking)"

    payment_ref: str | None = None
    payment_amount: float | None = None
    paid = False
    card_last4: str | None = None
    if data.pay_now:
        if not data.card_last4:
            raise ConflictError("Card last 4 digits are required to pay now")
        from app.modules.payments import service as payments_service
        from app.modules.payments.models import PaymentProvider
        from app.modules.payments.schemas import OnlineCheckoutCreate

        try:
            provider = PaymentProvider((data.payment_provider or "razorpay").lower())
        except ValueError as exc:
            raise ConflictError("Unsupported payment gateway") from exc

        amount = float(data.payment_amount) if data.payment_amount is not None else float(service_row.price or 0)
        if amount <= 0:
            amount = float(service_row.price or 0)
        order_id = f"SPA-{uuid.uuid4().hex[:12].upper()}"
        charge = await payments_service.create_online_checkout_charge(
            db,
            OnlineCheckoutCreate(
                outlet_id=data.outlet_id,
                provider=provider,
                amount=round(amount, 2),
                order_id=order_id,
                purpose="spa_booking",
                customer_name=data.guest_name,
                customer_email=data.guest_email,
                customer_phone=data.guest_phone,
                card_last4=data.card_last4,
            ),
        )
        payment_ref = charge.provider_payment_id or charge.provider_order_id or order_id
        payment_amount = charge.amount
        paid = True
        card_last4 = charge.card_last4
        pay_note = (
            f"Guest prepaid via {provider.value} · {payment_ref} · "
            f"card ····{card_last4} · ₹{payment_amount:,.2f}"
        )
        notes = f"{notes}\n{pay_note}".strip()

    payload = SpaBookingCreate(
        outlet_id=data.outlet_id,
        brand_id=outlet.brand_id,
        service_id=data.service_id,
        booked_at=data.booked_at,
        party_size=data.party_size,
        guest_name=data.guest_name,
        guest_phone=data.guest_phone,
        guest_email=data.guest_email,
        notes=notes,
        charge_to_folio=False,
    )
    created = create_booking(db, outlet.tenant_id, payload, default_brand_id=outlet.brand_id)

    if paid:
        created = confirm_booking(db, outlet.tenant_id, created.id)
        message = (
            f"Payment authorized ({payment_ref}). Your spa appointment is confirmed. "
            f"Reference {created.booking_number}."
        )
    else:
        message = (
            "Thank you! Your request has been received. "
            "Our spa team will confirm your appointment shortly. "
            "You can also pay at the spa desk."
        )

    return PublicSpaBookingResponse(
        booking_id=created.id,
        booking_number=created.booking_number,
        message=message,
        status=created.status,
        payment_ref=payment_ref,
        payment_amount=payment_amount,
        card_last4=card_last4 if paid else None,
        paid=paid,
    )


def cancel_booking(db: Session, tenant_id: int, booking_id: int) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status in {SpaBookingStatus.COMPLETED, SpaBookingStatus.CANCELLED, SpaBookingStatus.NO_SHOW}:
        raise ConflictError("Booking cannot be cancelled")
    booking.status = SpaBookingStatus.CANCELLED
    booking.cancelled_at = datetime.utcnow()
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def mark_no_show(db: Session, tenant_id: int, booking_id: int) -> SpaBookingRead:
    booking = _get_booking(db, tenant_id, booking_id)
    if booking.status not in {SpaBookingStatus.PENDING, SpaBookingStatus.CONFIRMED}:
        raise ConflictError("Only pending or confirmed bookings can be marked no-show")
    booking.status = SpaBookingStatus.NO_SHOW
    booking.cancelled_at = datetime.utcnow()
    db.commit()
    booking = _get_booking(db, tenant_id, booking.id)
    return _to_booking_read(db, booking)


def _next_booking_number(db: Session, tenant_id: int) -> str:
    year = datetime.utcnow().year
    prefix = f"SPA-{year}-"
    latest = (
        db.query(func.max(SpaBooking.booking_number))
        .filter(
            SpaBooking.tenant_id == tenant_id,
            SpaBooking.booking_number.like(f"{prefix}%"),
        )
        .scalar()
    )
    if latest:
        seq = int(latest.split("-")[-1]) + 1
    else:
        seq = 1
    return f"{prefix}{seq:04d}"


def _ensure_capacity(
    db: Session,
    service: SpaService,
    booked_at: datetime,
    party_size: int,
    *,
    exclude_booking_id: int | None = None,
) -> None:
    start = booked_at
    end = booked_at + timedelta(minutes=service.duration_minutes)
    query = db.query(SpaBooking).filter(
        SpaBooking.tenant_id == service.tenant_id,
        SpaBooking.service_id == service.id,
        SpaBooking.is_active.is_(True),
        SpaBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
    )
    if exclude_booking_id is not None:
        query = query.filter(SpaBooking.id != exclude_booking_id)

    overlap_count = 0
    for row in query.all():
        row_end = row.booked_at + timedelta(minutes=row.duration_minutes)
        if _intervals_overlap(start, end, row.booked_at, row_end):
            overlap_count += row.party_size

    if overlap_count + party_size > service.max_capacity:
        raise ConflictError("No capacity available for the selected time slot")


def _intervals_overlap(start_a: datetime, end_a: datetime, start_b: datetime, end_b: datetime) -> bool:
    return start_a < end_b and end_a > start_b


def _parse_time(value: str) -> time:
    hour, minute = value.split(":")
    return time(int(hour), int(minute))


def _validate_operating_hours(start: str, end: str) -> None:
    if _parse_time(start) >= _parse_time(end):
        raise ConflictError("Operating end must be after start")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_service(db: Session, tenant_id: int, service_id: int) -> SpaService:
    service = (
        db.query(SpaService)
        .filter(SpaService.id == service_id, SpaService.tenant_id == tenant_id, SpaService.is_active.is_(True))
        .first()
    )
    if service is None:
        raise NotFoundError("Spa service not found")
    return service


def _get_booking(db: Session, tenant_id: int, booking_id: int) -> SpaBooking:
    booking = (
        db.query(SpaBooking)
        .options(joinedload(SpaBooking.service))
        .filter(SpaBooking.id == booking_id, SpaBooking.tenant_id == tenant_id, SpaBooking.is_active.is_(True))
        .first()
    )
    if booking is None:
        raise NotFoundError("Spa booking not found")
    return booking


def _get_customer(db: Session, tenant_id: int, customer_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id, Customer.is_active.is_(True))
        .first()
    )
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


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


def _get_user(db: Session, tenant_id: int, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id, User.is_active.is_(True)).first()
    if user is None:
        raise NotFoundError("User not found")
    return user


def _get_therapist(db: Session, tenant_id: int, therapist_id: int) -> SpaTherapist:
    therapist = (
        db.query(SpaTherapist)
        .filter(
            SpaTherapist.id == therapist_id,
            SpaTherapist.tenant_id == tenant_id,
            SpaTherapist.is_active.is_(True),
        )
        .first()
    )
    if therapist is None:
        raise NotFoundError("Spa therapist not found")
    return therapist


def _get_therapist_for_user(db: Session, tenant_id: int, outlet_id: int, user_id: int) -> SpaTherapist:
    therapist = (
        db.query(SpaTherapist)
        .filter(
            SpaTherapist.tenant_id == tenant_id,
            SpaTherapist.outlet_id == outlet_id,
            SpaTherapist.user_id == user_id,
            SpaTherapist.is_active.is_(True),
        )
        .first()
    )
    if therapist is None:
        raise NotFoundError("Staff member is not on the spa therapist roster for this outlet")
    return therapist


def _ensure_staff_available(
    db: Session,
    tenant_id: int,
    staff_user_id: int,
    booked_at: datetime,
    duration_minutes: int,
    *,
    exclude_booking_id: int | None = None,
) -> None:
    start = booked_at
    end = booked_at + timedelta(minutes=duration_minutes)
    query = db.query(SpaBooking).filter(
        SpaBooking.tenant_id == tenant_id,
        SpaBooking.assigned_staff_id == staff_user_id,
        SpaBooking.is_active.is_(True),
        SpaBooking.status.in_(_ACTIVE_BOOKING_STATUSES),
    )
    if exclude_booking_id is not None:
        query = query.filter(SpaBooking.id != exclude_booking_id)

    for row in query.all():
        row_end = row.booked_at + timedelta(minutes=row.duration_minutes)
        if _intervals_overlap(start, end, row.booked_at, row_end):
            raise ConflictError("Therapist is already booked for this time slot")


def _to_therapist_read(db: Session, therapist: SpaTherapist) -> SpaTherapistRead:
    user = db.get(User, therapist.user_id)
    data = SpaTherapistRead.model_validate(therapist)
    data.user_name = user.full_name if user else None
    data.user_email = user.email if user else None
    return data


def _to_calendar_booking(booking: SpaBooking) -> SpaCalendarBooking:
    return SpaCalendarBooking(
        id=booking.id,
        booking_number=booking.booking_number,
        guest_name=booking.guest_name,
        service_name=booking.service.name if booking.service else None,
        booked_at=booking.booked_at,
        duration_minutes=booking.duration_minutes,
        status=booking.status,
        assigned_staff_id=booking.assigned_staff_id,
    )


def _to_service_read(service: SpaService) -> SpaServiceRead:
    return SpaServiceRead.model_validate(service)


def _to_booking_read(db: Session, booking: SpaBooking) -> SpaBookingRead:
    data = SpaBookingRead.model_validate(booking)
    if booking.service is not None:
        data.service_name = booking.service.name
        data.service_category = booking.service.category
    if booking.folio_posted_at is not None:
        from app.modules.pms.models import FolioEntry

        entry = (
            db.query(FolioEntry)
            .filter(FolioEntry.spa_booking_id == booking.id)
            .order_by(FolioEntry.id.desc())
            .first()
        )
        if entry:
            data.folio_entry_id = entry.id
    if booking.assigned_staff_id is not None:
        staff = db.get(User, booking.assigned_staff_id)
        data.assigned_staff_name = staff.full_name if staff else None
    return data
