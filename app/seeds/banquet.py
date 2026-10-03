"""Demo banquet venues and bookings."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.banquet.models import (
    BanquetBooking,
    BanquetBookingStatus,
    BanquetEventType,
    BanquetVenue,
    BanquetVenueType,
)
from app.seeds.base import SeedContext


def seed_banquet(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    outlet = ctx.outlets.get("Andheri West")
    if outlet is None:
        return
    outlet_id = outlet.id

    venue_specs = [
        ("Grand Ballroom", BanquetVenueType.INDOOR,
         "Elegant ballroom with chandelier lighting and stage",
         80, 350, 85000, 150000, "Stage, AV system, bridal suite access, valet parking"),
        ("Pool Deck Lawn", BanquetVenueType.LAWN,
         "Open-air lawn beside the pool, ideal for sundowners",
         40, 180, 45000, 80000, "Pool views, cocktail bar setup, fairy lights"),
        ("Summit Conference Hall", BanquetVenueType.CONFERENCE,
         "Corporate MICE space with breakout rooms",
         20, 120, 35000, 60000, "Projector, Wi-Fi, whiteboard, coffee service"),
        ("Rooftop Terrace", BanquetVenueType.OUTDOOR,
         "Open rooftop with panoramic city views, perfect for cocktail parties",
         30, 100, 30000, 55000, "City views, bar counter, ambient lighting"),
        ("Heritage Dining Hall", BanquetVenueType.INDOOR,
         "Intimate private dining hall with colonial décor for small banquets",
         15, 60, 20000, 38000, "Private butler, curated menu, sound system"),
    ]

    venues: dict[str, BanquetVenue] = {}
    for name, vtype, description, cap_min, cap_max, half_rate, full_rate, amenities in venue_specs:
        venue = (
            db.query(BanquetVenue)
            .filter(BanquetVenue.tenant_id == tenant.id, BanquetVenue.name == name)
            .first()
        )
        if venue is None:
            venue = BanquetVenue(
                tenant_id=tenant.id,
                brand_id=outlet.brand_id,
                outlet_id=outlet_id,
                name=name,
                venue_type=vtype,
                description=description,
                capacity_min=cap_min,
                capacity_max=cap_max,
                half_day_rate=half_rate,
                full_day_rate=full_rate,
                amenities=amenities,
            )
            db.add(venue)
            db.flush()
        venues[name] = venue

    booking_specs = [
        ("BQT-2026-0001", "Grand Ballroom", "Sharma-Mehta Wedding Reception",
         BanquetEventType.WEDDING, BanquetBookingStatus.CONFIRMED,
         14, "18:00", "23:00", 220, "Priya Sharma", "+91 98765 43210", None, 150000, 50000,
         None, True),
        ("BQT-2026-0002", "Summit Conference Hall", "TechCorp Annual Offsite",
         BanquetEventType.CONFERENCE, BanquetBookingStatus.INQUIRY,
         21, "09:00", "17:00", 85, "Rahul Desai", "+91 90000 11111",
         "rahul@techcorp.example.com", 60000, 0, "Needs hybrid AV setup for remote speakers", False),
        ("BQT-2026-0003", "Pool Deck Lawn", "Sunita's Baby Shower Celebration",
         BanquetEventType.SOCIAL, BanquetBookingStatus.CONFIRMED,
         10, "15:00", "20:00", 60, "Sunita Joshi", "+919800000006", None, 80000, 25000,
         None, True),
        ("BQT-2026-0004", "Rooftop Terrace", "Kavya & Arjun Engagement Party",
         BanquetEventType.SOCIAL, BanquetBookingStatus.TENTATIVE,
         30, "19:00", "23:00", 80, "Kavya Reddy", "+919800000008", "kavya@example.com",
         55000, 10000, "Outdoor cocktail setup with DJ", False),
        ("BQT-2026-0005", "Heritage Dining Hall", "Board Dinner — MNR Industries",
         BanquetEventType.CORPORATE, BanquetBookingStatus.CONFIRMED,
         7, "20:00", "23:00", 30, "Arjun Malhotra", "+919800000007",
         "arjun@mnr.example.com", 38000, 15000, "Curated 5-course menu required", True),
    ]

    for (booking_number, venue_name, title, event_type, status, days_ahead,
         start_time, end_time, guest_count, contact_name, contact_phone,
         contact_email, estimated_amount, advance_paid, notes, confirmed) in booking_specs:
        existing_booking = (
            db.query(BanquetBooking)
            .filter(BanquetBooking.tenant_id == tenant.id, BanquetBooking.booking_number == booking_number)
            .first()
        )
        if existing_booking is not None:
            continue
        venue = venues.get(venue_name)
        if venue is None:
            continue
        db.add(
            BanquetBooking(
                tenant_id=tenant.id,
                brand_id=outlet.brand_id,
                outlet_id=outlet_id,
                venue_id=venue.id,
                booking_number=booking_number,
                title=title,
                event_type=event_type,
                status=status,
                event_date=date.today() + timedelta(days=days_ahead),
                start_time=start_time,
                end_time=end_time,
                guest_count=guest_count,
                contact_name=contact_name,
                contact_phone=contact_phone,
                contact_email=contact_email,
                estimated_amount=estimated_amount,
                advance_paid=advance_paid,
                notes=notes,
                confirmed_at=datetime.utcnow() if confirmed else None,
            )
        )
