"""Demo spa services and bookings."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.pms.models import GuestReservation, ReservationStatus
from app.modules.spa.models import SpaBooking, SpaBookingStatus, SpaService, SpaServiceCategory, SpaTherapist
from app.seeds.base import SeedContext


def seed_spa(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    outlet = ctx.outlets.get("Andheri West")
    if outlet is None:
        return
    outlet_id = outlet.id

    service_specs = [
        ("Swedish Massage", SpaServiceCategory.SPA, "60-minute full-body relaxation massage", 60, 2500, 2, 30, "10:00", "20:00"),
        ("Aromatherapy Facial", SpaServiceCategory.SPA, "Deep cleanse and rejuvenating facial", 45, 1800, 1, 30, "10:00", "19:00"),
        ("Sunset Yoga Session", SpaServiceCategory.ACTIVITY, "Group yoga on the pool deck", 60, 800, 12, 60, "17:00", "19:00"),
        ("Guided Nature Walk", SpaServiceCategory.ACTIVITY, "Resort trail walk with naturalist guide", 90, 600, 8, 90, "07:00", "10:00"),
        ("Hot Stone Therapy", SpaServiceCategory.SPA, "90-minute deep relaxation with heated basalt stones", 90, 3500, 1, 60, "10:00", "18:00"),
    ]

    services: dict[str, SpaService] = {}
    for name, category, description, duration, price, max_cap, slot_interval, op_start, op_end in service_specs:
        svc = (
            db.query(SpaService)
            .filter(SpaService.tenant_id == tenant.id, SpaService.name == name)
            .first()
        )
        if svc is None:
            svc = SpaService(
                tenant_id=tenant.id,
                brand_id=outlet.brand_id,
                outlet_id=outlet_id,
                name=name,
                category=category,
                description=description,
                duration_minutes=duration,
                price=price,
                max_capacity=max_cap,
                slot_interval_minutes=slot_interval,
                operating_start=op_start,
                operating_end=op_end,
            )
            db.add(svc)
            db.flush()
        services[name] = svc

    therapist_users = []
    for key in ("admin@example.com", "admin@restrochain.test", "ops@restrochain.test",
                "marketing@restrochain.test", "housekeeper@restrochain.test",
                "cashier.andheri@restrochain.test", "waiter.bandra@restrochain.test"):
        user = ctx.users.get(key)
        if user and user not in therapist_users:
            therapist_users.append(user)
    if not therapist_users:
        therapist_users = list(ctx.users.values())

    colors = ["#8b5cf6", "#0d9488", "#f59e0b", "#ef4444", "#3b82f6"]
    therapist_specs = [
        ("Senior Massage Therapist", "Swedish, Deep Tissue"),
        ("Wellness Guide", "Yoga, Meditation"),
        ("Beauty Therapist", "Facials, Body Wraps"),
        ("Ayurvedic Practitioner", "Abhyanga, Shirodhara"),
        ("Fitness & Yoga Instructor", "Yoga, Pilates, Breathwork"),
    ]

    therapists: list[SpaTherapist] = []
    for idx, (title, specialties) in enumerate(therapist_specs):
        user = therapist_users[idx % len(therapist_users)]
        existing_therapist = (
            db.query(SpaTherapist)
            .filter(
                SpaTherapist.tenant_id == tenant.id,
                SpaTherapist.outlet_id == outlet_id,
                SpaTherapist.user_id == user.id,
                SpaTherapist.title == title,
            )
            .first()
        )
        if existing_therapist is None:
            t = SpaTherapist(
                tenant_id=tenant.id,
                brand_id=outlet.brand_id,
                outlet_id=outlet_id,
                user_id=user.id,
                title=title,
                specialties=specialties,
                shift_start="09:00",
                shift_end="20:00",
                calendar_color=colors[idx % len(colors)],
            )
            db.add(t)
            db.flush()
            therapists.append(t)
        else:
            therapists.append(existing_therapist)

    reservation = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant.id,
            GuestReservation.is_active.is_(True),
            GuestReservation.status == ReservationStatus.CHECKED_IN,
        )
        .order_by(GuestReservation.id.asc())
        .first()
    )
    if reservation is None:
        reservation = (
            db.query(GuestReservation)
            .filter(GuestReservation.tenant_id == tenant.id, GuestReservation.is_active.is_(True))
            .order_by(GuestReservation.id.asc())
            .first()
        )

    tomorrow_10 = datetime.now().replace(hour=10, minute=0, second=0, microsecond=0) + timedelta(days=1)
    tomorrow_14 = datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1)
    tomorrow_17 = datetime.now().replace(hour=17, minute=0, second=0, microsecond=0) + timedelta(days=1)
    day2_11 = datetime.now().replace(hour=11, minute=0, second=0, microsecond=0) + timedelta(days=2)
    day2_07 = datetime.now().replace(hour=7, minute=0, second=0, microsecond=0) + timedelta(days=2)

    booking_specs = [
        ("SPA-2026-0001", "Swedish Massage", SpaBookingStatus.CONFIRMED, tomorrow_10, 60, 1, 2500,
         "Priya Sharma", "+91 98765 43210", True, "Prefer lavender oil", reservation),
        ("SPA-2026-0002", "Sunset Yoga Session", SpaBookingStatus.PENDING, tomorrow_17, 60, 2, 1600,
         "Walk-in Guest", "+91 90000 11111", False, None, None),
        ("SPA-2026-0003", "Aromatherapy Facial", SpaBookingStatus.CONFIRMED, tomorrow_14, 45, 1, 1800,
         "Neha Kapoor", "+919800000004", True, "Sensitive skin, no fragrance", reservation),
        ("SPA-2026-0004", "Hot Stone Therapy", SpaBookingStatus.CONFIRMED, day2_11, 90, 1, 3500,
         "Sarah Mitchell", "+919810000102", True, "First time guest", reservation),
        ("SPA-2026-0005", "Guided Nature Walk", SpaBookingStatus.PENDING, day2_07, 90, 4, 2400,
         "Group Booking", "+91 90001 22222", False, "Morning walk for 4 guests", None),
    ]

    for (booking_number, service_name, status, booked_at, duration, party_size, price,
         guest_name, guest_phone, charge_folio, notes, res) in booking_specs:
        existing_booking = (
            db.query(SpaBooking)
            .filter(SpaBooking.tenant_id == tenant.id, SpaBooking.booking_number == booking_number)
            .first()
        )
        if existing_booking is not None:
            continue
        svc = services.get(service_name)
        if svc is None:
            continue
        therapist = therapists[0] if therapists else None
        db.add(
            SpaBooking(
                tenant_id=tenant.id,
                brand_id=outlet.brand_id,
                outlet_id=outlet_id,
                service_id=svc.id,
                booking_number=booking_number,
                status=status,
                booked_at=booked_at,
                duration_minutes=duration,
                party_size=party_size,
                price=price,
                guest_name=guest_name,
                guest_phone=guest_phone,
                guest_reservation_id=res.id if res else None,
                notes=notes,
                charge_to_folio=charge_folio,
                confirmed_at=datetime.utcnow() if status == SpaBookingStatus.CONFIRMED else None,
                assigned_staff_id=therapist.user_id if therapist else None,
            )
        )
