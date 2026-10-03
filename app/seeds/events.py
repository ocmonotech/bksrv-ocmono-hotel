"""Restaurant events with preorders, table assignments, and activities."""

from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.events.models import (
    EventActivity,
    EventActivityType,
    EventPreOrderItem,
    EventSource,
    EventStatus,
    EventTableAssignment,
    EventType,
    RestaurantEvent,
)
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


def seed_events(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    andheri = ctx.outlets["Andheri West"]
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    marketing = ctx.users.get("marketing@restrochain.test")
    assigned_to = marketing.id if marketing else (admin.id if admin else None)

    customer = ctx.customers.get("+919800000004")
    lead = ctx.leads.get("+919810000001")
    booking = ctx.bookings.get("ZMT-BOOK-001")
    offer = ctx.offers.get("Birthday Special")
    table_t5 = ctx.tables.get(("Andheri West", "T5"))
    table_t6 = ctx.tables.get(("Andheri West", "T6"))

    event_specs = [
        {
            "title": "Neha's 30th Birthday Party",
            "type": EventType.BIRTHDAY,
            "status": EventStatus.CONFIRMED,
            "customer_name": "Neha Kapoor",
            "phone": "+919800000004",
            "guests": 15,
            "days_ahead": 7,
            "customer": customer,
            "lead": None,
            "booking": None,
            "offer": offer,
            "preorders": [("Paneer Tikka", 2), ("Butter Chicken", 3), ("Gulab Jamun", 5)],
            "tables": [table_t5, table_t6],
        },
        {
            "title": "Corporate Team Lunch - TechCorp",
            "type": EventType.CORPORATE,
            "status": EventStatus.QUOTED,
            "customer_name": "Ananya Rao",
            "phone": "+919810000001",
            "guests": 25,
            "days_ahead": 14,
            "customer": None,
            "lead": lead,
            "booking": None,
            "offer": None,
            "preorders": [("Veg Biryani", 10), ("Chicken Biryani", 15)],
            "tables": [],
        },
        {
            "title": "Anniversary Dinner",
            "type": EventType.ANNIVERSARY,
            "status": EventStatus.INQUIRY,
            "customer_name": "Mohit Agarwal",
            "phone": "+919810000004",
            "guests": 2,
            "days_ahead": 3,
            "customer": None,
            "lead": ctx.leads.get("+919810000004"),
            "booking": booking,
            "offer": None,
            "preorders": [],
            "tables": [table_t5] if table_t5 else [],
        },
        {
            "title": "Sunita's Baby Shower",
            "type": EventType.CELEBRATION,
            "status": EventStatus.CONFIRMED,
            "customer_name": "Sunita Joshi",
            "phone": "+919800000006",
            "guests": 30,
            "days_ahead": 10,
            "customer": ctx.customers.get("+919800000006"),
            "lead": None,
            "booking": None,
            "offer": ctx.offers.get("Birthday Special"),
            "preorders": [("Paneer Tikka", 4), ("Veg Biryani", 6), ("Gulab Jamun", 10)],
            "tables": [table_t6] if table_t6 else [],
        },
        {
            "title": "School Reunion Dinner",
            "type": EventType.PRIVATE_DINING,
            "status": EventStatus.QUOTED,
            "customer_name": "Arjun Malhotra",
            "phone": "+919800000007",
            "guests": 20,
            "days_ahead": 21,
            "customer": ctx.customers.get("+919800000007"),
            "lead": None,
            "booking": None,
            "offer": None,
            "preorders": [("Butter Chicken", 5), ("Chicken Biryani", 4), ("Garlic Naan", 10)],
            "tables": [],
        },
    ]

    for spec in event_specs:
        existing = (
            db.query(RestaurantEvent)
            .filter(RestaurantEvent.tenant_id == tenant.id, RestaurantEvent.title == spec["title"])
            .first()
        )
        if existing is not None:
            continue

        event_date = date.today() + timedelta(days=spec["days_ahead"])
        event = RestaurantEvent(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            customer_id=spec["customer"].id if spec["customer"] else None,
            lead_id=spec["lead"].id if spec["lead"] else None,
            booking_id=spec["booking"].id if spec["booking"] else None,
            offer_id=spec["offer"].id if spec["offer"] else None,
            event_type=spec["type"],
            title=spec["title"],
            guest_of_honor=spec["customer_name"] if spec["type"] == EventType.BIRTHDAY else None,
            customer_name=spec["customer_name"],
            customer_phone=spec["phone"],
            event_date=event_date,
            start_time="19:00",
            end_time="22:00",
            duration_minutes=180,
            expected_guests=spec["guests"],
            confirmed_guests=spec["guests"] if spec["status"] == EventStatus.CONFIRMED else None,
            status=spec["status"],
            source=EventSource.LEAD if spec["lead"] else EventSource.WALK_IN,
            assigned_to=assigned_to,
            special_requests="Demo event seed data",
            decoration_notes="Balloons and fairy lights" if spec["type"] == EventType.BIRTHDAY else None,
            estimated_amount=spec["guests"] * 650,
            advance_paid=5000 if spec["status"] == EventStatus.CONFIRMED else 0,
        )
        db.add(event)
        db.flush()

        for item_name, qty in spec["preorders"]:
            menu_item = ctx.menu_items.get(item_name)
            if menu_item is None:
                continue
            db.add(
                EventPreOrderItem(
                    event_id=event.id,
                    menu_item_id=menu_item.id,
                    item_name=item_name,
                    quantity=qty,
                    unit_price=float(menu_item.base_price),
                )
            )

        reserved_from = datetime.combine(event_date, datetime.strptime("18:30", "%H:%M").time())
        reserved_until = datetime.combine(event_date, datetime.strptime("22:30", "%H:%M").time())
        for table in spec["tables"]:
            if table is None:
                continue
            db.add(
                EventTableAssignment(
                    event_id=event.id,
                    table_id=table.id,
                    reserved_from=reserved_from,
                    reserved_until=reserved_until,
                )
            )

        if assigned_to:
            db.add(
                EventActivity(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    event_id=event.id,
                    activity_type=EventActivityType.NOTE,
                    note=f"Demo event created: {spec['title']}",
                    created_by=assigned_to,
                )
            )
