"""Table booking reservations."""

from __future__ import annotations

import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.bookings.models import BookingPlatform, BookingStatus, TableBooking
from app.seeds.base import SeedContext


def seed_bookings(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    table_t3 = ctx.tables.get(("Andheri West", "T3"))

    zomato_integration = next(
        (i for k, i in ctx.booking_integrations.items() if "zomato" in k.lower()),
        None,
    )
    direct_integration = next(
        (i for k, i in ctx.booking_integrations.items() if "direct" in k.lower()),
        None,
    )

    booking_specs = [
        {
            "key": "ZMT-BOOK-001",
            "integration": zomato_integration,
            "platform": BookingPlatform.ZOMATO,
            "external_id": "ZMT-BOOK-001",
            "status": BookingStatus.CONFIRMED,
            "name": "Mohit Agarwal",
            "phone": "+919810000004",
            "guests": 4,
            "offset_hours": 24,
            "table": table_t3,
            "requests": "Window seat preferred",
        },
        {
            "key": "DIRECT-BOOK-001",
            "integration": direct_integration,
            "platform": BookingPlatform.DIRECT,
            "external_id": None,
            "status": BookingStatus.PENDING,
            "name": "Sneha Iyer",
            "phone": "+919810000003",
            "guests": 2,
            "offset_hours": 48,
            "table": None,
            "requests": "Anniversary dinner",
        },
        {
            "key": "ZMT-BOOK-002",
            "integration": zomato_integration,
            "platform": BookingPlatform.ZOMATO,
            "external_id": "ZMT-BOOK-002",
            "status": BookingStatus.COMPLETED,
            "name": "Aarav Mehta",
            "phone": "+919800000001",
            "guests": 3,
            "offset_hours": -48,
            "table": ctx.tables.get(("Andheri West", "T1")),
            "requests": None,
        },
        {
            "key": "EAZY-BOOK-001",
            "integration": next(
                (i for k, i in ctx.booking_integrations.items() if "eazy" in k.lower()),
                direct_integration,
            ),
            "platform": BookingPlatform.DIRECT,
            "external_id": "EAZY-BOOK-001",
            "status": BookingStatus.CONFIRMED,
            "name": "Sunita Joshi",
            "phone": "+919800000006",
            "guests": 6,
            "offset_hours": 72,
            "table": ctx.tables.get(("Andheri West", "T4")),
            "requests": "High chair needed for toddler",
        },
        {
            "key": "DIRECT-BOOK-002",
            "integration": direct_integration,
            "platform": BookingPlatform.DIRECT,
            "external_id": None,
            "status": BookingStatus.CANCELLED,
            "name": "Rohan Verma",
            "phone": "+919810000006",
            "guests": 4,
            "offset_hours": -24,
            "table": None,
            "requests": "Outdoor seating",
        },
    ]

    for spec in booking_specs:
        lookup_external = spec["external_id"] or spec["key"]
        booking = (
            db.query(TableBooking)
            .filter(
                TableBooking.tenant_id == tenant.id,
                TableBooking.outlet_id == andheri.id,
                TableBooking.external_booking_id == lookup_external,
            )
            .first()
        )
        if booking is None and spec["external_id"] is None:
            booking = (
                db.query(TableBooking)
                .filter(
                    TableBooking.tenant_id == tenant.id,
                    TableBooking.outlet_id == andheri.id,
                    TableBooking.customer_phone == spec["phone"],
                    TableBooking.platform == spec["platform"],
                )
                .first()
            )
        if booking is not None:
            ctx.bookings[spec["key"]] = booking
            continue

        booked_for = datetime.utcnow() + timedelta(hours=spec["offset_hours"])
        booking = TableBooking(
            tenant_id=tenant.id,
            brand_id=brand.id,
            integration_id=spec["integration"].id if spec["integration"] else None,
            outlet_id=andheri.id,
            platform=spec["platform"],
            external_booking_id=lookup_external,
            status=spec["status"],
            customer_name=spec["name"],
            customer_phone=spec["phone"],
            guest_count=spec["guests"],
            booked_for=booked_for,
            duration_minutes=90,
            table_id=spec["table"].id if spec["table"] else None,
            special_requests=spec["requests"],
            raw_payload_json=json.dumps({"demo": True, "key": spec["key"]}),
        )
        db.add(booking)
        db.flush()
        ctx.bookings[spec["key"]] = booking
