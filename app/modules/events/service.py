from __future__ import annotations

from datetime import date, datetime, time, timedelta

from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.customers.models import Customer
from app.modules.events.models import (
    EventActivity,
    EventActivityType,
    EventPreOrderItem,
    EventStatus,
    EventTableAssignment,
    RestaurantEvent,
)
from app.modules.events.schemas import (
    EventActivityCreate,
    EventActivityRead,
    EventCreate,
    EventDeleteResponse,
    EventDetailRead,
    EventFromLeadCreate,
    EventPosOrderResponse,
    EventPreOrderItemCreate,
    EventPreOrderRead,
    EventRead,
    EventTableAssignmentRead,
    EventUpdate,
    EventWhatsAppKind,
    EventWhatsAppResponse,
    PublicEventInquiryCreate,
    PublicEventInquiryResponse,
)
from app.modules.leads.models import Lead, LeadStage
from app.modules.offers.models import Offer
from app.modules.outlets.models import Outlet
from app.modules.tables.models import RestaurantTable, TableStatus
from app.modules.users.models import User


def create_event(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: EventCreate,
    default_brand_id: int | None = None,
) -> EventRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id
    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
    if data.customer_id is not None:
        _get_customer(db, tenant_id, data.customer_id)
    if data.lead_id is not None:
        _get_lead(db, tenant_id, data.lead_id)
    if data.offer_id is not None:
        _get_offer(db, tenant_id, data.offer_id)
    if data.assigned_to is not None:
        _get_user(db, tenant_id, data.assigned_to)

    for table_id in data.table_ids:
        table = _get_table(db, tenant_id, table_id)
        if table.outlet_id != data.outlet_id:
            raise ConflictError("Table does not belong to this outlet")

    event = RestaurantEvent(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        customer_id=data.customer_id,
        lead_id=data.lead_id,
        offer_id=data.offer_id,
        event_type=data.event_type,
        title=data.title,
        guest_of_honor=data.guest_of_honor,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        event_date=data.event_date,
        start_time=data.start_time,
        end_time=data.end_time,
        duration_minutes=data.duration_minutes,
        expected_guests=data.expected_guests,
        status=EventStatus.INQUIRY,
        source=data.source,
        assigned_to=data.assigned_to,
        special_requests=data.special_requests,
        decoration_notes=data.decoration_notes,
        dietary_notes=data.dietary_notes,
        estimated_amount=data.estimated_amount,
        advance_paid=data.advance_paid,
    )
    db.add(event)
    db.flush()

    if data.table_ids:
        _assign_tables(db, event, data.table_ids, reserve=False)

    _add_activity(
        db,
        tenant_id,
        brand_id,
        event.id,
        user_id,
        EventActivityType.NOTE,
        f"Event created: {data.title}",
    )
    db.commit()
    db.refresh(event)
    return _to_read(event)


def list_events(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    status: EventStatus | None = None,
    event_type=None,
    from_date: date | None = None,
    to_date: date | None = None,
    assigned_to: int | None = None,
    customer_id: int | None = None,
) -> tuple[list[EventRead], int]:
    query = db.query(RestaurantEvent).filter(
        RestaurantEvent.tenant_id == tenant_id,
        RestaurantEvent.is_active.is_(True),
    )

    if outlet_id is not None:
        _get_outlet(db, tenant_id, outlet_id)
        query = query.filter(RestaurantEvent.outlet_id == outlet_id)
    if status is not None:
        query = query.filter(RestaurantEvent.status == status)
    if event_type is not None:
        query = query.filter(RestaurantEvent.event_type == event_type)
    if from_date is not None:
        query = query.filter(RestaurantEvent.event_date >= from_date)
    if to_date is not None:
        query = query.filter(RestaurantEvent.event_date <= to_date)
    if assigned_to is not None:
        query = query.filter(RestaurantEvent.assigned_to == assigned_to)
    if customer_id is not None:
        query = query.filter(RestaurantEvent.customer_id == customer_id)

    rows, total = paginate_query(
        query.order_by(RestaurantEvent.event_date.asc(), RestaurantEvent.start_time.asc()),
        page,
        page_size,
    )
    return [_to_read(row) for row in rows], total


def get_event(db: Session, tenant_id: int, event_id: int) -> EventDetailRead:
    event = _get_event_entity(db, tenant_id, event_id, with_details=True)
    return _to_detail_read(db, event)


def update_event(
    db: Session,
    tenant_id: int,
    event_id: int,
    data: EventUpdate,
) -> EventRead:
    event = _get_event_entity(db, tenant_id, event_id)
    payload = data.model_dump(exclude_unset=True)
    table_ids = payload.pop("table_ids", None)

    if "assigned_to" in payload and payload["assigned_to"] is not None:
        _get_user(db, tenant_id, payload["assigned_to"])
    if "offer_id" in payload and payload["offer_id"] is not None:
        _get_offer(db, tenant_id, payload["offer_id"])

    for key, value in payload.items():
        setattr(event, key, value)

    if table_ids is not None:
        db.query(EventTableAssignment).filter(EventTableAssignment.event_id == event.id).delete()
        if table_ids:
            _assign_tables(
                db,
                event,
                table_ids,
                reserve=event.status in {EventStatus.CONFIRMED, EventStatus.IN_PROGRESS},
            )

    db.commit()
    db.refresh(event)
    return _to_read(event)


def confirm_event(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    table_ids: list[int] | None = None,
    notes: str | None = None,
) -> EventRead:
    event = _get_event_entity(db, tenant_id, event_id, with_details=table_ids is None)
    if event.status in {EventStatus.COMPLETED, EventStatus.CANCELLED}:
        raise ConflictError("Event cannot be confirmed in its current status")

    if table_ids:
        db.query(EventTableAssignment).filter(EventTableAssignment.event_id == event.id).delete()
        _assign_tables(db, event, table_ids, reserve=True)
    elif event.table_assignments:
        for assignment in event.table_assignments:
            table = db.get(RestaurantTable, assignment.table_id)
            if table:
                _reserve_table(table)

    event.status = EventStatus.CONFIRMED
    _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        EventActivityType.STATUS_CHANGE,
        notes or "Event confirmed",
    )
    db.commit()
    db.refresh(event)
    return _to_read(event)


def create_event_from_lead(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: EventFromLeadCreate,
    default_brand_id: int | None = None,
) -> EventRead:
    lead = _get_lead(db, tenant_id, data.lead_id)
    if lead.outlet_id is None:
        raise ConflictError("Lead must be assigned to an outlet before creating an event")

    combined_text = (lead.last_message or "").lower()
    tags_json = (lead.tags_json or "[]").lower()
    is_party = "birthday" in combined_text or "party" in combined_text or "party" in tags_json

    from app.modules.events.models import EventSource, EventType

    event_type = data.event_type or (EventType.BIRTHDAY if is_party else EventType.CUSTOM)
    title = data.title or (
        f"{lead.lead_name.split()[0]}'s Birthday Party"
        if event_type == EventType.BIRTHDAY
        else f"Event for {lead.lead_name}"
    )
    event_date = data.event_date or (date.today() + timedelta(days=14))

    payload = EventCreate(
        outlet_id=lead.outlet_id,
        brand_id=lead.brand_id or default_brand_id,
        customer_id=lead.customer_id,
        lead_id=lead.id,
        event_type=event_type,
        title=title,
        guest_of_honor=lead.lead_name if event_type == EventType.BIRTHDAY else None,
        customer_name=lead.lead_name,
        customer_phone=lead.mobile,
        customer_email=lead.email,
        event_date=event_date,
        start_time=data.start_time or "19:00",
        expected_guests=data.expected_guests or (25 if is_party else 10),
        source=EventSource.LEAD,
        assigned_to=lead.assigned_to,
        special_requests=data.special_requests or lead.last_message,
        estimated_amount=data.estimated_amount or 0,
    )
    event_read = create_event(db, tenant_id, user_id, payload, default_brand_id=default_brand_id)

    lead.stage = LeadStage.TABLE_BOOKED
    db.commit()
    return event_read


async def send_event_whatsapp(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    kind: EventWhatsAppKind = EventWhatsAppKind.CONFIRMATION,
) -> EventWhatsAppResponse:
    from app.modules.communications.schemas import WhatsAppSendRequest
    from app.modules.communications import service as comms_service

    event = _get_event_entity(db, tenant_id, event_id)
    if not event.customer_phone:
        raise ConflictError("Customer phone is required to send WhatsApp")

    outlet = _get_outlet(db, tenant_id, event.outlet_id)
    message_text = _build_event_whatsapp_message(event, outlet.name, kind)

    await comms_service.send_mock_whatsapp(
        db,
        tenant_id,
        user_id,
        WhatsAppSendRequest(
            receiver=event.customer_phone,
            message_text=message_text,
            outlet_id=event.outlet_id,
            customer_id=event.customer_id,
            lead_id=event.lead_id,
            brand_id=event.brand_id,
        ),
        default_brand_id=event.brand_id,
    )

    _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        EventActivityType.WHATSAPP,
        f"WhatsApp {kind.value} sent to {event.customer_phone}",
    )
    db.commit()

    return EventWhatsAppResponse(
        message=f"WhatsApp {kind.value} sent",
        event_id=event.id,
        message_preview=message_text,
    )


def _build_event_whatsapp_message(
    event: RestaurantEvent,
    outlet_name: str,
    kind: EventWhatsAppKind,
) -> str:
    date_label = event.event_date.strftime("%d %b %Y")
    if kind == EventWhatsAppKind.REMINDER:
        return (
            f"Hi {event.customer_name}! 👋\n\n"
            f"Reminder: your event \"{event.title}\" at {outlet_name} "
            f"is on {date_label} at {event.start_time}.\n"
            f"Guests: {event.expected_guests}. We look forward to hosting you!"
        )
    return (
        f"Hi {event.customer_name}! 🎉\n\n"
        f"Your event \"{event.title}\" is confirmed at {outlet_name} "
        f"on {date_label} at {event.start_time} for {event.expected_guests} guests.\n"
        f"Reply here if you need any changes. See you soon!"
    )


def cancel_event(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    notes: str | None = None,
) -> EventRead:
    event = _get_event_entity(db, tenant_id, event_id)
    if event.status == EventStatus.COMPLETED:
        raise ConflictError("Completed events cannot be cancelled")

    event.status = EventStatus.CANCELLED
    _release_event_tables(db, event)
    _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        EventActivityType.STATUS_CHANGE,
        notes or "Event cancelled",
    )
    db.commit()
    db.refresh(event)
    return _to_read(event)


def complete_event(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    notes: str | None = None,
) -> EventRead:
    event = _get_event_entity(db, tenant_id, event_id)
    if event.status not in {EventStatus.CONFIRMED, EventStatus.IN_PROGRESS}:
        raise ConflictError("Only confirmed or in-progress events can be completed")

    event.status = EventStatus.COMPLETED
    _release_event_tables(db, event)
    _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        EventActivityType.STATUS_CHANGE,
        notes or "Event completed",
    )
    db.commit()
    db.refresh(event)
    return _to_read(event)


def add_activity(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    data: EventActivityCreate,
) -> EventActivityRead:
    event = _get_event_entity(db, tenant_id, event_id)
    activity = _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        data.activity_type,
        data.note,
    )
    db.commit()
    db.refresh(activity)
    return EventActivityRead.model_validate(activity)


def delete_event(db: Session, tenant_id: int, event_id: int) -> EventDeleteResponse:
    event = _get_event_entity(db, tenant_id, event_id)
    if event.status in {EventStatus.CONFIRMED, EventStatus.IN_PROGRESS}:
        _release_event_tables(db, event)
    event.is_active = False
    db.commit()
    return EventDeleteResponse(message="Event deleted", event_id=event.id)


def _assign_tables(
    db: Session,
    event: RestaurantEvent,
    table_ids: list[int],
    *,
    reserve: bool,
) -> None:
    reserved_from, reserved_until = _event_window(event)
    for table_id in table_ids:
        table = _get_table(db, event.tenant_id, table_id)
        if table.outlet_id != event.outlet_id:
            raise ConflictError("Table does not belong to this outlet")
        db.add(
            EventTableAssignment(
                event_id=event.id,
                table_id=table_id,
                reserved_from=reserved_from,
                reserved_until=reserved_until,
            )
        )
        if reserve:
            _reserve_table(table)


def _event_window(event: RestaurantEvent) -> tuple[datetime, datetime]:
    start = _parse_event_datetime(event.event_date, event.start_time)
    if event.end_time:
        end = _parse_event_datetime(event.event_date, event.end_time)
    else:
        end = start + timedelta(minutes=event.duration_minutes)
    return start, end


def _parse_event_datetime(event_date: date, time_str: str) -> datetime:
    parts = time_str.split(":")
    hour = int(parts[0])
    minute = int(parts[1]) if len(parts) > 1 else 0
    return datetime.combine(event_date, time(hour, minute))


def _reserve_table(table: RestaurantTable) -> None:
    if table.status in {TableStatus.AVAILABLE, TableStatus.CLEANING}:
        table.status = TableStatus.RESERVED


def _release_event_tables(db: Session, event: RestaurantEvent) -> None:
    for assignment in event.table_assignments:
        table = db.get(RestaurantTable, assignment.table_id)
        if table and table.status == TableStatus.RESERVED:
            table.status = TableStatus.AVAILABLE


def _add_activity(
    db: Session,
    tenant_id: int,
    brand_id: int | None,
    event_id: int,
    user_id: int,
    activity_type: EventActivityType,
    note: str | None,
) -> EventActivity:
    activity = EventActivity(
        tenant_id=tenant_id,
        brand_id=brand_id,
        event_id=event_id,
        activity_type=activity_type,
        note=note,
        created_by=user_id,
    )
    db.add(activity)
    return activity


def _get_event_entity(
    db: Session,
    tenant_id: int,
    event_id: int,
    *,
    with_details: bool = False,
) -> RestaurantEvent:
    query = db.query(RestaurantEvent).filter(
        RestaurantEvent.id == event_id,
        RestaurantEvent.tenant_id == tenant_id,
        RestaurantEvent.is_active.is_(True),
    )
    if with_details:
        query = query.options(
            joinedload(RestaurantEvent.table_assignments),
            joinedload(RestaurantEvent.activities),
            joinedload(RestaurantEvent.preorders),
        )
    event = query.first()
    if event is None:
        raise NotFoundError("Event not found")
    return event


def _to_read(event: RestaurantEvent) -> EventRead:
    estimated = float(event.estimated_amount or 0)
    advance = float(event.advance_paid or 0)
    payload = EventRead.model_validate(event)
    payload.balance_due = max(estimated - advance, 0)
    return payload


def _to_detail_read(db: Session, event: RestaurantEvent) -> EventDetailRead:
    base = _to_read(event)
    tables: list[EventTableAssignmentRead] = []
    for assignment in event.table_assignments:
        table_number = None
        table = db.get(RestaurantTable, assignment.table_id)
        if table:
            table_number = table.table_number
        row = EventTableAssignmentRead.model_validate(assignment)
        row.table_number = table_number
        tables.append(row)

    return EventDetailRead(
        **base.model_dump(),
        tables=tables,
        activities=[EventActivityRead.model_validate(a) for a in event.activities],
        preorders=[EventPreOrderRead.model_validate(p) for p in event.preorders],
    )


def _validate_brand(db: Session, tenant_id: int, brand_id: int) -> None:
    exists = db.query(Brand.id).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if exists is None:
        raise NotFoundError("Brand not found")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_customer(db: Session, tenant_id: int, customer_id: int) -> Customer:
    customer = (
        db.query(Customer)
        .filter(Customer.id == customer_id, Customer.tenant_id == tenant_id, Customer.is_active.is_(True))
        .first()
    )
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


def _get_lead(db: Session, tenant_id: int, lead_id: int) -> Lead:
    lead = db.query(Lead).filter(Lead.id == lead_id, Lead.tenant_id == tenant_id).first()
    if lead is None:
        raise NotFoundError("Lead not found")
    return lead


def _get_offer(db: Session, tenant_id: int, offer_id: int) -> Offer:
    offer = (
        db.query(Offer)
        .filter(Offer.id == offer_id, Offer.tenant_id == tenant_id, Offer.is_active.is_(True))
        .first()
    )
    if offer is None:
        raise NotFoundError("Offer not found")
    return offer


def _get_user(db: Session, tenant_id: int, user_id: int) -> User:
    user = db.query(User).filter(User.id == user_id, User.tenant_id == tenant_id).first()
    if user is None:
        raise NotFoundError("User not found")
    return user


def _get_table(db: Session, tenant_id: int, table_id: int) -> RestaurantTable:
    table = (
        db.query(RestaurantTable)
        .filter(
            RestaurantTable.id == table_id,
            RestaurantTable.tenant_id == tenant_id,
            RestaurantTable.is_active.is_(True),
        )
        .first()
    )
    if table is None:
        raise NotFoundError("Table not found")
    return table


EVENT_PACKAGES: list[dict] = [
    {
        "id": "birthday-standard",
        "name": "Birthday Standard",
        "event_type": "birthday",
        "price_per_person": 599,
        "min_guests": 10,
        "includes": ["Welcome drink", "Birthday cake", "Balloon decor", "Dedicated host"],
        "description": "Perfect for intimate birthday celebrations",
    },
    {
        "id": "birthday-premium",
        "name": "Birthday Premium",
        "event_type": "birthday",
        "price_per_person": 899,
        "min_guests": 15,
        "includes": ["3-course set menu", "Custom cake", "Theme decor", "Photographer (1 hr)"],
        "description": "Premium birthday experience with full decor",
    },
    {
        "id": "corporate-lunch",
        "name": "Corporate Lunch",
        "event_type": "corporate",
        "price_per_person": 750,
        "min_guests": 20,
        "includes": ["Buffet lunch", "Projector setup", "Dedicated service staff"],
        "description": "Team lunches and corporate meetings",
    },
    {
        "id": "anniversary-dinner",
        "name": "Anniversary Dinner",
        "event_type": "anniversary",
        "price_per_person": 1200,
        "min_guests": 8,
        "includes": ["Candle setup", "Anniversary cake", "Rose petals", "Wine pairing"],
        "description": "Romantic anniversary celebration",
    },
]


def list_event_packages() -> list:
    from app.modules.events.models import EventType
    from app.modules.events.schemas import EventPackageRead

    return [
        EventPackageRead(
            id=pkg["id"],
            name=pkg["name"],
            event_type=EventType(pkg["event_type"]),
            price_per_person=pkg["price_per_person"],
            min_guests=pkg["min_guests"],
            includes=pkg["includes"],
            description=pkg.get("description"),
        )
        for pkg in EVENT_PACKAGES
    ]


def list_birthday_opportunities(
    db: Session,
    tenant_id: int,
    days_ahead: int = 30,
) -> list:
    from app.modules.events.schemas import BirthdayOpportunityRead

    today = date.today()
    customers = (
        db.query(Customer)
        .filter(
            Customer.tenant_id == tenant_id,
            Customer.is_active.is_(True),
            Customer.birthday.isnot(None),
        )
        .all()
    )
    rows = []
    for customer in customers:
        if customer.birthday is None:
            continue
        next_bday = _next_occurrence(customer.birthday, today)
        days_until = (next_bday - today).days
        if days_until > days_ahead:
            continue
        rows.append(
            BirthdayOpportunityRead(
                customer_id=customer.id,
                customer_name=customer.full_name,
                mobile=customer.mobile,
                birthday=next_bday,
                days_until=days_until,
                favourite_outlet_id=customer.favourite_outlet_id,
            )
        )
    rows.sort(key=lambda row: row.days_until)
    return rows


def _next_occurrence(birthday: date, today: date) -> date:
    candidate = birthday.replace(year=today.year)
    if candidate < today:
        candidate = candidate.replace(year=today.year + 1)
    return candidate


def list_preorders(db: Session, tenant_id: int, event_id: int) -> list[EventPreOrderRead]:
    event = _get_event_entity(db, tenant_id, event_id, with_details=True)
    return [EventPreOrderRead.model_validate(row) for row in event.preorders]


def replace_preorders(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
    items: list[EventPreOrderItemCreate],
) -> list[EventPreOrderRead]:
    from app.modules.pos.service import _resolve_menu_item_price

    event = _get_event_entity(db, tenant_id, event_id)
    db.query(EventPreOrderItem).filter(EventPreOrderItem.event_id == event.id).delete()

    rows: list[EventPreOrderItem] = []
    total = 0.0
    for item in items:
        menu_item, price = _resolve_menu_item_price(db, event.outlet_id, item.menu_item_id)
        row = EventPreOrderItem(
            event_id=event.id,
            menu_item_id=menu_item.id,
            item_name=menu_item.item_name,
            quantity=item.quantity,
            unit_price=price,
            notes=item.notes,
        )
        db.add(row)
        rows.append(row)
        total += price * item.quantity

    if total > 0 and float(event.estimated_amount or 0) == 0:
        event.estimated_amount = total

    if items:
        _add_activity(
            db,
            event.tenant_id,
            event.brand_id,
            event.id,
            user_id,
            EventActivityType.NOTE,
            f"Pre-order menu updated ({len(items)} items, ₹{total:.0f} estimated)",
        )

    db.commit()
    db.refresh(event)
    return list_preorders(db, tenant_id, event_id)


def create_pos_order_from_event(
    db: Session,
    tenant_id: int,
    user_id: int,
    event_id: int,
) -> EventPosOrderResponse:
    from app.modules.pos import service as pos_service
    from app.modules.pos.models import OrderType
    from app.modules.pos.schemas import OrderCreate, OrderItemCreate

    event = _get_event_entity(db, tenant_id, event_id, with_details=True)
    if event.pos_order_id is not None:
        raise ConflictError("Event is already linked to a POS order")
    if event.status in {EventStatus.CANCELLED, EventStatus.COMPLETED}:
        raise ConflictError("Cannot create POS order for a closed event")

    preorders = list(event.preorders)
    if not preorders:
        raise ConflictError("Add pre-order menu items before creating a POS order")

    table_id = event.table_assignments[0].table_id if event.table_assignments else None
    order_read = pos_service.create_order(
        db,
        tenant_id,
        user_id,
        OrderCreate(
            outlet_id=event.outlet_id,
            brand_id=event.brand_id,
            table_id=table_id,
            customer_id=event.customer_id,
            order_type=OrderType.DINE_IN,
        ),
    )

    for pre in preorders:
        pos_service.add_item(
            db,
            tenant_id,
            order_read.id,
            OrderItemCreate(
                menu_item_id=pre.menu_item_id,
                quantity=pre.quantity,
                note=pre.notes,
            ),
        )

    event = _get_event_entity(db, tenant_id, event_id)
    event.pos_order_id = order_read.id
    if event.status == EventStatus.CONFIRMED:
        event.status = EventStatus.IN_PROGRESS

    _add_activity(
        db,
        event.tenant_id,
        event.brand_id,
        event.id,
        user_id,
        EventActivityType.NOTE,
        f"POS order {order_read.order_number} created from event pre-order",
    )
    db.commit()

    return EventPosOrderResponse(
        event_id=event.id,
        pos_order_id=order_read.id,
        order_number=order_read.order_number,
    )


def submit_public_inquiry(
    db: Session,
    data: PublicEventInquiryCreate,
) -> PublicEventInquiryResponse:
    from app.modules.events.models import EventSource

    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == data.outlet_id, Outlet.is_active.is_(True))
        .first()
    )
    if outlet is None:
        raise NotFoundError("Outlet not found")

    estimated = 0.0
    if data.package_id:
        for pkg in EVENT_PACKAGES:
            if pkg["id"] == data.package_id:
                estimated = float(pkg["price_per_person"]) * data.expected_guests
                break

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
        raise ConflictError("Outlet is not configured for online event bookings")

    payload = EventCreate(
        outlet_id=outlet.id,
        brand_id=outlet.brand_id,
        event_type=data.event_type,
        title=data.title,
        guest_of_honor=data.guest_of_honor,
        customer_name=data.customer_name,
        customer_phone=data.customer_phone,
        customer_email=data.customer_email,
        event_date=data.event_date,
        start_time=data.start_time,
        expected_guests=data.expected_guests,
        source=EventSource.WEBSITE,
        special_requests=data.special_requests,
        estimated_amount=estimated,
    )
    created = create_event(db, outlet.tenant_id, admin.id, payload, default_brand_id=outlet.brand_id)

    return PublicEventInquiryResponse(
        event_id=created.id,
        message="Thank you! Our team will contact you shortly to confirm your event.",
        status=created.status,
    )
