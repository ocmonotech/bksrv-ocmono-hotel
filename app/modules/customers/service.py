from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.brands.models import Brand
from app.modules.customers.models import (
    Customer,
    CustomerStatus,
    CustomerTag,
    CustomerTagMap,
    CustomerVisit,
    Feedback,
    FeedbackSentiment,
)
from app.modules.customers.schemas import (
    CustomerCreate,
    CustomerProfileRead,
    CustomerRead,
    CustomerTagAssign,
    CustomerTagRead,
    CustomerUpdate,
    CustomerVisitRead,
    FeedbackCreate,
    FeedbackRead,
    Guest360Banquet,
    Guest360Loyalty,
    Guest360LoyaltyLedger,
    Guest360OutletTouch,
    Guest360PosVisit,
    Guest360Preferences,
    Guest360Read,
    Guest360Spa,
    Guest360Stay,
    Guest360Summary,
    Guest360TimelineItem,
    InactiveCustomerRead,
    VipCustomerRead,
)
from app.modules.outlets.models import Outlet


DEFAULT_VIP_MIN_SPEND = 10000.0
DEFAULT_VIP_MIN_LOYALTY_POINTS = 500
DEFAULT_INACTIVE_DAYS = 90


def create_customer(
    db: Session,
    tenant_id: int,
    data: CustomerCreate,
    default_brand_id: int | None = None,
) -> CustomerRead:
    brand_id = data.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    if data.favourite_outlet_id is not None:
        _get_outlet(db, tenant_id, data.favourite_outlet_id)

    existing = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id, Customer.mobile == data.mobile)
        .first()
    )
    if existing is not None:
        raise ConflictError("Customer with this mobile number already exists")

    customer = Customer(
        tenant_id=tenant_id,
        brand_id=brand_id,
        full_name=data.full_name,
        mobile=data.mobile,
        email=data.email,
        birthday=data.birthday,
        anniversary=data.anniversary,
        source=data.source,
        consent_whatsapp=data.consent_whatsapp,
        consent_sms=data.consent_sms,
        consent_email=data.consent_email,
        favourite_outlet_id=data.favourite_outlet_id,
        status=CustomerStatus.ACTIVE,
    )
    db.add(customer)
    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)


def list_customers(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    search: str | None = None,
    brand_id: int | None = None,
    status: CustomerStatus | None = None,
) -> tuple[list[CustomerRead], int]:
    query = db.query(Customer).filter(Customer.tenant_id == tenant_id)

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Customer.brand_id.is_(None), Customer.brand_id == brand_id))

    if status is not None:
        query = query.filter(Customer.status == status)

    if search:
        term = f"%{search.strip()}%"
        query = query.filter(
            or_(
                Customer.full_name.ilike(term),
                Customer.mobile.ilike(term),
                Customer.email.ilike(term),
            )
        )

    query = query.order_by(Customer.full_name)
    customers, total = paginate_query(query, page, page_size)
    return [CustomerRead.model_validate(customer) for customer in customers], total


def get_customer_profile(db: Session, tenant_id: int, customer_id: int) -> CustomerProfileRead:
    customer = _get_customer_entity(db, tenant_id, customer_id, with_tags=True)

    recent_visit_count = (
        db.query(func.count(CustomerVisit.id))
        .filter(CustomerVisit.customer_id == customer.id)
        .scalar()
        or 0
    )
    feedback_stats = (
        db.query(func.count(Feedback.id), func.avg(Feedback.rating))
        .filter(Feedback.customer_id == customer.id)
        .one()
    )
    feedback_count = int(feedback_stats[0] or 0)
    average_rating = float(feedback_stats[1]) if feedback_stats[1] is not None else None

    tags = [CustomerTagRead.model_validate(tag_map.tag) for tag_map in customer.tag_maps]

    profile = CustomerProfileRead.model_validate(customer)
    profile.tags = tags
    profile.recent_visit_count = recent_visit_count
    profile.feedback_count = feedback_count
    profile.average_rating = average_rating
    return profile


def update_customer(
    db: Session,
    tenant_id: int,
    customer_id: int,
    data: CustomerUpdate,
) -> CustomerRead:
    customer = _get_customer_entity(db, tenant_id, customer_id)
    updates = data.model_dump(exclude_unset=True)

    if "mobile" in updates:
        duplicate = (
            db.query(Customer)
            .filter(
                Customer.tenant_id == tenant_id,
                Customer.mobile == updates["mobile"],
                Customer.id != customer_id,
            )
            .first()
        )
        if duplicate is not None:
            raise ConflictError("Another customer already uses this mobile number")

    if updates.get("favourite_outlet_id") is not None:
        _get_outlet(db, tenant_id, updates["favourite_outlet_id"])

    for field, value in updates.items():
        setattr(customer, field, value)

    db.commit()
    db.refresh(customer)
    return CustomerRead.model_validate(customer)


def add_customer_tag(
    db: Session,
    tenant_id: int,
    customer_id: int,
    data: CustomerTagAssign,
    default_brand_id: int | None = None,
) -> CustomerProfileRead:
    if data.tag_id is None and not data.name:
        raise ConflictError("Provide tag_id or name")

    customer = _get_customer_entity(db, tenant_id, customer_id)

    if data.tag_id is not None:
        tag = _get_tag(db, tenant_id, data.tag_id)
    else:
        tag = _get_or_create_tag(db, tenant_id, data.name, customer.brand_id or default_brand_id)

    existing = (
        db.query(CustomerTagMap)
        .filter(CustomerTagMap.customer_id == customer.id, CustomerTagMap.tag_id == tag.id)
        .first()
    )
    if existing is not None:
        raise ConflictError("Tag is already assigned to this customer")

    db.add(CustomerTagMap(customer_id=customer.id, tag_id=tag.id))
    db.commit()
    return get_customer_profile(db, tenant_id, customer_id)


def remove_customer_tag(
    db: Session,
    tenant_id: int,
    customer_id: int,
    tag_id: int,
) -> CustomerProfileRead:
    _get_customer_entity(db, tenant_id, customer_id)
    _get_tag(db, tenant_id, tag_id)

    tag_map = (
        db.query(CustomerTagMap)
        .filter(CustomerTagMap.customer_id == customer_id, CustomerTagMap.tag_id == tag_id)
        .first()
    )
    if tag_map is None:
        raise NotFoundError("Tag is not assigned to this customer")

    db.delete(tag_map)
    db.commit()
    return get_customer_profile(db, tenant_id, customer_id)


def get_customer_visits(
    db: Session,
    tenant_id: int,
    customer_id: int,
    page: int,
    page_size: int,
) -> tuple[list[CustomerVisitRead], int]:
    _get_customer_entity(db, tenant_id, customer_id)

    query = (
        db.query(CustomerVisit)
        .filter(CustomerVisit.tenant_id == tenant_id, CustomerVisit.customer_id == customer_id)
        .order_by(CustomerVisit.visit_date.desc(), CustomerVisit.id.desc())
    )
    visits, total = paginate_query(query, page, page_size)
    return [CustomerVisitRead.model_validate(visit) for visit in visits], total


def get_guest_360(db: Session, tenant_id: int, customer_id: int) -> Guest360Read:
    """Aggregate hotel / café / spa / banquet / loyalty touchpoints for one guest."""
    from datetime import datetime

    from app.modules.banquet.models import BanquetBooking
    from app.modules.loyalty.service import list_ledger, resolve_tier
    from app.modules.pms.models import GuestReservation, HotelRoom
    from app.modules.spa.models import SpaBooking

    profile = get_customer_profile(db, tenant_id, customer_id)
    outlet_names = {
        row.id: row.name
        for row in db.query(Outlet).filter(Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True)).all()
    }

    stays_rows = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant_id,
            GuestReservation.is_active.is_(True),
            GuestReservation.customer_id == customer_id,
        )
        .order_by(GuestReservation.check_in_date.desc())
        .limit(50)
        .all()
    )
    room_ids = [row.room_id for row in stays_rows if row.room_id]
    room_numbers = {
        room.id: room.room_number
        for room in db.query(HotelRoom).filter(HotelRoom.id.in_(room_ids)).all()
    } if room_ids else {}
    stays = [
        Guest360Stay(
            reservation_id=row.id,
            confirmation_number=row.confirmation_number,
            outlet_id=row.outlet_id,
            outlet_name=outlet_names.get(row.outlet_id),
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            check_in_date=row.check_in_date,
            check_out_date=row.check_out_date,
            room_number=room_numbers.get(row.room_id) if row.room_id else None,
            guest_mobile=row.guest_mobile,
            notes=row.notes,
        )
        for row in stays_rows
    ]

    visit_rows = (
        db.query(CustomerVisit)
        .filter(CustomerVisit.tenant_id == tenant_id, CustomerVisit.customer_id == customer_id)
        .order_by(CustomerVisit.visit_date.desc())
        .limit(50)
        .all()
    )
    pos_visits = [
        Guest360PosVisit(
            id=v.id,
            outlet_id=v.outlet_id,
            outlet_name=outlet_names.get(v.outlet_id),
            visit_date=v.visit_date,
            total_amount=float(v.total_amount or 0),
            bill_id=v.bill_id,
        )
        for v in visit_rows
    ]

    mobile = (profile.mobile or "").strip()
    spa_q = db.query(SpaBooking).filter(
        SpaBooking.tenant_id == tenant_id,
        SpaBooking.is_active.is_(True),
    )
    if mobile:
        spa_q = spa_q.filter(
            or_(SpaBooking.customer_id == customer_id, SpaBooking.guest_phone == mobile)
        )
    else:
        spa_q = spa_q.filter(SpaBooking.customer_id == customer_id)
    spa_rows = (
        spa_q.options(joinedload(SpaBooking.service))
        .order_by(SpaBooking.booked_at.desc())
        .limit(50)
        .all()
    )
    spa = [
        Guest360Spa(
            booking_id=row.id,
            booking_number=row.booking_number,
            outlet_id=row.outlet_id,
            outlet_name=outlet_names.get(row.outlet_id),
            service_name=row.service.name if row.service else None,
            status=row.status.value if hasattr(row.status, "value") else str(row.status),
            booked_at=row.booked_at,
            price=float(row.price or 0),
            guest_reservation_id=row.guest_reservation_id,
        )
        for row in spa_rows
    ]

    banquet: list[Guest360Banquet] = []
    if mobile:
        banquet_rows = (
            db.query(BanquetBooking)
            .filter(
                BanquetBooking.tenant_id == tenant_id,
                BanquetBooking.is_active.is_(True),
                BanquetBooking.contact_phone == mobile,
            )
            .order_by(BanquetBooking.event_date.desc())
            .limit(50)
            .all()
        )
        banquet = [
            Guest360Banquet(
                booking_id=row.id,
                booking_number=row.booking_number,
                title=row.title,
                outlet_id=row.outlet_id,
                outlet_name=outlet_names.get(row.outlet_id),
                event_date=row.event_date,
                status=row.status.value if hasattr(row.status, "value") else str(row.status),
                estimated_amount=float(row.estimated_amount or 0),
            )
            for row in banquet_rows
        ]

    tier = resolve_tier(db, tenant_id, int(profile.loyalty_points or 0))
    ledger_rows, _ = list_ledger(db, tenant_id, customer_id=customer_id, page=1, page_size=20)
    loyalty = Guest360Loyalty(
        points=int(profile.loyalty_points or 0),
        tier_code=tier.code if tier else None,
        tier_name=tier.name if tier else None,
        recent_ledger=[
            Guest360LoyaltyLedger(
                id=entry.id,
                points=entry.points,
                txn_type=entry.txn_type.value if hasattr(entry.txn_type, "value") else str(entry.txn_type),
                source=entry.source.value if hasattr(entry.source, "value") else str(entry.source),
                description=entry.description,
                created_at=entry.created_at,
            )
            for entry in ledger_rows
        ],
    )

    feedback_rows = (
        db.query(Feedback)
        .filter(Feedback.tenant_id == tenant_id, Feedback.customer_id == customer_id)
        .order_by(Feedback.id.desc())
        .limit(30)
        .all()
    )
    feedback = [FeedbackRead.model_validate(row) for row in feedback_rows]

    notes_snippets: list[str] = []
    for stay in stays_rows[:5]:
        note = (getattr(stay, "notes", None) or "").strip()
        if note:
            notes_snippets.append(note[:160])

    preferences = Guest360Preferences(
        tags=[t.name for t in profile.tags],
        favourite_outlet_id=profile.favourite_outlet_id,
        notes_snippets=notes_snippets,
    )

    outlet_touch: dict[int, Guest360OutletTouch] = {}
    timeline: list[Guest360TimelineItem] = []

    def _touch(outlet_id: int, channel: str, at: datetime | None) -> None:
        row = outlet_touch.get(outlet_id)
        if row is None:
            row = Guest360OutletTouch(
                outlet_id=outlet_id,
                outlet_name=outlet_names.get(outlet_id),
                last_at=at,
                channels=[channel],
            )
            outlet_touch[outlet_id] = row
        else:
            if channel not in row.channels:
                row.channels.append(channel)
            if at and (row.last_at is None or at > row.last_at):
                row.last_at = at

    for stay in stays:
        at = datetime.combine(stay.check_in_date, datetime.min.time())
        _touch(stay.outlet_id, "hotel", at)
        timeline.append(
            Guest360TimelineItem(
                channel="hotel",
                at=at,
                title=f"Stay {stay.confirmation_number}",
                subtitle=f"{stay.status} · {stay.check_in_date} → {stay.check_out_date}"
                + (f" · Room {stay.room_number}" if stay.room_number else ""),
                outlet_name=stay.outlet_name,
                reference_id=str(stay.reservation_id),
            )
        )
    for visit in pos_visits:
        _touch(visit.outlet_id, "cafe", visit.visit_date)
        timeline.append(
            Guest360TimelineItem(
                channel="cafe",
                at=visit.visit_date,
                title="Café visit",
                subtitle=f"Bill #{visit.bill_id}" if visit.bill_id else None,
                amount=visit.total_amount,
                outlet_name=visit.outlet_name,
                reference_id=str(visit.id),
            )
        )
    for row in spa:
        _touch(row.outlet_id, "spa", row.booked_at)
        timeline.append(
            Guest360TimelineItem(
                channel="spa",
                at=row.booked_at,
                title=row.service_name or "Spa booking",
                subtitle=row.status,
                amount=row.price,
                outlet_name=row.outlet_name,
                reference_id=str(row.booking_id),
            )
        )
    for row in banquet:
        at = datetime.combine(row.event_date, datetime.min.time()) if row.event_date else None
        _touch(row.outlet_id, "banquet", at)
        timeline.append(
            Guest360TimelineItem(
                channel="banquet",
                at=at,
                title=row.title or "Banquet",
                subtitle=row.status,
                amount=row.estimated_amount,
                outlet_name=row.outlet_name,
                reference_id=str(row.booking_id),
            )
        )

    timeline.sort(key=lambda item: item.at or datetime.min, reverse=True)
    last = timeline[0] if timeline else None
    lifetime = float(profile.total_spend or 0) + sum(s.estimated_amount for s in banquet)
    for stay_row in stays_rows:
        lifetime += float(getattr(stay_row, "total_amount", 0) or 0)

    summary = Guest360Summary(
        hotel_stays=len(stays),
        cafe_visits=len(pos_visits) if pos_visits else int(profile.total_visits or 0),
        spa_bookings=len(spa),
        banquet_events=len(banquet),
        lifetime_spend=round(lifetime, 2),
        last_touch_at=last.at if last else profile.last_visit_at,
        last_touch_channel=last.channel if last else None,
    )

    return Guest360Read(
        profile=profile,
        outlets_touched=sorted(
            outlet_touch.values(),
            key=lambda o: o.last_at or datetime.min,
            reverse=True,
        ),
        stays=stays,
        pos_visits=pos_visits,
        spa=spa,
        banquet=banquet,
        loyalty=loyalty,
        feedback=feedback,
        preferences=preferences,
        summary=summary,
        timeline=timeline[:80],
    )


def add_feedback(
    db: Session,
    tenant_id: int,
    data: FeedbackCreate,
    default_brand_id: int | None = None,
) -> FeedbackRead:
    customer = _get_customer_entity(db, tenant_id, data.customer_id)
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or customer.brand_id or outlet.brand_id or default_brand_id
    _validate_brand(db, tenant_id, brand_id)

    sentiment = data.sentiment or _sentiment_from_rating(data.rating)

    feedback = Feedback(
        tenant_id=tenant_id,
        brand_id=brand_id,
        outlet_id=data.outlet_id,
        customer_id=data.customer_id,
        rating=data.rating,
        message=data.message,
        sentiment=sentiment,
        source=data.source,
    )
    db.add(feedback)
    db.commit()
    db.refresh(feedback)
    return FeedbackRead.model_validate(feedback)


def get_vip_customers(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    min_spend: float = DEFAULT_VIP_MIN_SPEND,
    min_loyalty_points: int = DEFAULT_VIP_MIN_LOYALTY_POINTS,
    brand_id: int | None = None,
) -> tuple[list[VipCustomerRead], int]:
    query = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.status == CustomerStatus.ACTIVE,
        or_(
            Customer.total_spend >= min_spend,
            Customer.loyalty_points >= min_loyalty_points,
        ),
    )

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Customer.brand_id.is_(None), Customer.brand_id == brand_id))

    query = query.order_by(Customer.total_spend.desc(), Customer.loyalty_points.desc())
    customers, total = paginate_query(query, page, page_size)

    items: list[VipCustomerRead] = []
    for customer in customers:
        reasons: list[str] = []
        if float(customer.total_spend) >= min_spend:
            reasons.append(f"spend >= {min_spend}")
        if customer.loyalty_points >= min_loyalty_points:
            reasons.append(f"loyalty >= {min_loyalty_points}")

        item = VipCustomerRead.model_validate(customer)
        item.vip_reason = ", ".join(reasons)
        items.append(item)

    return items, total


def get_inactive_customers(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    inactive_days: int = DEFAULT_INACTIVE_DAYS,
    brand_id: int | None = None,
) -> tuple[list[InactiveCustomerRead], int]:
    cutoff = datetime.utcnow() - timedelta(days=inactive_days)

    query = db.query(Customer).filter(
        Customer.tenant_id == tenant_id,
        Customer.status == CustomerStatus.ACTIVE,
        or_(Customer.last_visit_at.is_(None), Customer.last_visit_at < cutoff),
    )

    if brand_id is not None:
        _validate_brand(db, tenant_id, brand_id)
        query = query.filter(or_(Customer.brand_id.is_(None), Customer.brand_id == brand_id))

    query = query.order_by(Customer.last_visit_at.asc().nullsfirst(), Customer.full_name)
    customers, total = paginate_query(query, page, page_size)

    items: list[InactiveCustomerRead] = []
    now = datetime.utcnow()
    for customer in customers:
        days_since = None
        if customer.last_visit_at is not None:
            days_since = (now - customer.last_visit_at).days

        item = InactiveCustomerRead.model_validate(customer)
        item.days_since_last_visit = days_since
        items.append(item)

    return items, total


def record_customer_visit(
    db: Session,
    tenant_id: int,
    customer_id: int,
    outlet_id: int,
    bill_id: int | None,
    visit_date: datetime,
    total_amount: float,
    brand_id: int | None = None,
) -> CustomerVisit:
    """Helper for POS/billing integration to append visits and roll up customer stats."""
    customer = _get_customer_entity(db, tenant_id, customer_id)
    outlet = _get_outlet(db, tenant_id, outlet_id)

    visit = CustomerVisit(
        tenant_id=tenant_id,
        brand_id=brand_id or customer.brand_id or outlet.brand_id,
        outlet_id=outlet_id,
        customer_id=customer_id,
        bill_id=bill_id,
        visit_date=visit_date,
        total_amount=total_amount,
    )
    db.add(visit)

    customer.total_visits += 1
    customer.total_spend = float(customer.total_spend) + total_amount
    customer.last_visit_at = visit_date
    if customer.favourite_outlet_id is None:
        customer.favourite_outlet_id = outlet_id

    db.flush()
    return visit


def _sentiment_from_rating(rating: int) -> FeedbackSentiment:
    if rating >= 4:
        return FeedbackSentiment.POSITIVE
    if rating == 3:
        return FeedbackSentiment.NEUTRAL
    return FeedbackSentiment.NEGATIVE


def _get_or_create_tag(
    db: Session,
    tenant_id: int,
    name: str,
    brand_id: int | None,
) -> CustomerTag:
    normalized = name.strip()
    tag = (
        db.query(CustomerTag)
        .filter(
            CustomerTag.tenant_id == tenant_id,
            func.lower(CustomerTag.name) == normalized.lower(),
            or_(CustomerTag.brand_id.is_(None), CustomerTag.brand_id == brand_id),
        )
        .first()
    )
    if tag is not None:
        return tag

    tag = CustomerTag(tenant_id=tenant_id, brand_id=brand_id, name=normalized)
    db.add(tag)
    db.flush()
    return tag


def _get_tag(db: Session, tenant_id: int, tag_id: int) -> CustomerTag:
    tag = (
        db.query(CustomerTag)
        .filter(CustomerTag.id == tag_id, CustomerTag.tenant_id == tenant_id)
        .first()
    )
    if tag is None:
        raise NotFoundError("Customer tag not found")
    return tag


def _get_customer_entity(
    db: Session,
    tenant_id: int,
    customer_id: int,
    with_tags: bool = False,
) -> Customer:
    query = db.query(Customer).filter(Customer.id == customer_id, Customer.tenant_id == tenant_id)
    if with_tags:
        query = query.options(joinedload(Customer.tag_maps).joinedload(CustomerTagMap.tag))
    customer = query.first()
    if customer is None:
        raise NotFoundError("Customer not found")
    return customer


def _validate_brand(db: Session, tenant_id: int, brand_id: int | None) -> None:
    if brand_id is None:
        return
    brand = db.query(Brand).filter(Brand.id == brand_id, Brand.tenant_id == tenant_id).first()
    if brand is None:
        raise NotFoundError("Brand not found")


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if outlet is None:
        raise NotFoundError("Outlet not found")
    return outlet
