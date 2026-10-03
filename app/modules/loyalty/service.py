"""Loyalty earn/burn engine — hotel stays + café/POS."""

from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.exceptions import ConflictError, NotFoundError
from app.modules.customers.models import Customer
from app.modules.customers.service import record_customer_visit
from app.modules.loyalty.models import LoyaltyLedger, LoyaltySource, LoyaltyTier, LoyaltyTxnType
from app.modules.loyalty.schemas import (
    LoyaltyAdjustRequest,
    LoyaltyConfigRead,
    LoyaltyConfigUpdate,
    LoyaltyLedgerRead,
    LoyaltyMemberRead,
    LoyaltyRedeemPreview,
    LoyaltySummaryRead,
    LoyaltyTierCreate,
    LoyaltyTierRead,
    LoyaltyTierUpdate,
)
from app.modules.settings.schemas import SettingValueUpdate
from app.modules.settings.service import get_brand_settings, update_brand_setting


DEFAULT_LOYALTY_CONFIG: dict = {
    "enabled": True,
    "points_per_100": 5,
    "stay_points_per_night": 50,
    "stay_points_per_100": 2,
    "min_redeem_points": 100,
    "point_value": 1,
    "earn_on_room_charge": False,
}

DEFAULT_TIERS = [
    {
        "name": "Bronze",
        "code": "BRONZE",
        "min_points": 0,
        "earn_multiplier": 1,
        "color": "amber",
        "perks": "Earn on café & stays",
        "sort_order": 1,
    },
    {
        "name": "Silver",
        "code": "SILVER",
        "min_points": 500,
        "earn_multiplier": 1.25,
        "color": "slate",
        "perks": "1.25× earn rate",
        "sort_order": 2,
    },
    {
        "name": "Gold",
        "code": "GOLD",
        "min_points": 2000,
        "earn_multiplier": 1.5,
        "color": "yellow",
        "perks": "1.5× earn · priority spa slots",
        "sort_order": 3,
    },
    {
        "name": "Platinum",
        "code": "PLATINUM",
        "min_points": 5000,
        "earn_multiplier": 2,
        "color": "violet",
        "perks": "2× earn · room upgrade preference",
        "sort_order": 4,
    },
]


def get_loyalty_config(db: Session, tenant_id: int, brand_id: int | None = None) -> LoyaltyConfigRead:
    raw: dict = {}
    if brand_id:
        settings = get_brand_settings(db, tenant_id, brand_id).settings
        raw = dict(settings.get("loyalty") or {})
        # Migrate legacy seed key name if still present in storage via deep merge miss.
        if not raw.get("points_per_100") and settings.get("loyalty_config"):
            raw = {**raw, **(settings.get("loyalty_config") or {})}
    merged = {**DEFAULT_LOYALTY_CONFIG, **(raw or {})}
    return LoyaltyConfigRead(
        enabled=bool(merged.get("enabled", True)),
        points_per_100=float(merged.get("points_per_100", 5)),
        stay_points_per_night=int(merged.get("stay_points_per_night", 50)),
        stay_points_per_100=float(merged.get("stay_points_per_100", 2)),
        min_redeem_points=int(merged.get("min_redeem_points", 100)),
        point_value=float(merged.get("point_value", 1)),
        earn_on_room_charge=bool(merged.get("earn_on_room_charge", False)),
    )


def update_loyalty_config(
    db: Session,
    tenant_id: int,
    brand_id: int,
    data: LoyaltyConfigUpdate,
) -> LoyaltyConfigRead:
    current = get_loyalty_config(db, tenant_id, brand_id).model_dump()
    patch = data.model_dump(exclude_unset=True)
    current.update(patch)
    update_brand_setting(
        db,
        tenant_id,
        brand_id,
        SettingValueUpdate(setting_key="loyalty", value=current),
    )
    return LoyaltyConfigRead(**current)


def _tier_to_read(tier: LoyaltyTier) -> LoyaltyTierRead:
    return LoyaltyTierRead(
        id=tier.id,
        tenant_id=tier.tenant_id,
        brand_id=tier.brand_id,
        name=tier.name,
        code=tier.code,
        min_points=int(tier.min_points),
        earn_multiplier=float(tier.earn_multiplier),
        color=tier.color,
        perks=tier.perks,
        sort_order=int(tier.sort_order),
        is_active=tier.is_active,
        created_at=tier.created_at,
        updated_at=tier.updated_at,
    )


def list_tiers(db: Session, tenant_id: int) -> list[LoyaltyTierRead]:
    rows = (
        db.query(LoyaltyTier)
        .filter(LoyaltyTier.tenant_id == tenant_id, LoyaltyTier.is_active.is_(True))
        .order_by(LoyaltyTier.min_points.asc(), LoyaltyTier.sort_order.asc())
        .all()
    )
    return [_tier_to_read(row) for row in rows]


def ensure_default_tiers(
    db: Session,
    tenant_id: int,
    brand_id: int | None = None,
    reset: bool = False,
) -> list[LoyaltyTierRead]:
    existing = (
        db.query(LoyaltyTier)
        .filter(LoyaltyTier.tenant_id == tenant_id, LoyaltyTier.is_active.is_(True))
        .count()
    )
    if existing and not reset:
        return list_tiers(db, tenant_id)

    if reset:
        for row in db.query(LoyaltyTier).filter(LoyaltyTier.tenant_id == tenant_id).all():
            row.is_active = False

    for spec in DEFAULT_TIERS:
        db.add(
            LoyaltyTier(
                tenant_id=tenant_id,
                brand_id=brand_id,
                name=spec["name"],
                code=spec["code"],
                min_points=spec["min_points"],
                earn_multiplier=spec["earn_multiplier"],
                color=spec["color"],
                perks=spec["perks"],
                sort_order=spec["sort_order"],
            )
        )
    db.commit()
    return list_tiers(db, tenant_id)


def create_tier(
    db: Session,
    tenant_id: int,
    data: LoyaltyTierCreate,
    brand_id: int | None = None,
) -> LoyaltyTierRead:
    code = data.code.strip().upper()
    clash = (
        db.query(LoyaltyTier)
        .filter(LoyaltyTier.tenant_id == tenant_id, LoyaltyTier.code == code, LoyaltyTier.is_active.is_(True))
        .first()
    )
    if clash:
        raise ConflictError("Tier code already exists")
    tier = LoyaltyTier(
        tenant_id=tenant_id,
        brand_id=brand_id,
        name=data.name.strip(),
        code=code,
        min_points=data.min_points,
        earn_multiplier=data.earn_multiplier,
        color=data.color,
        perks=data.perks,
        sort_order=data.sort_order,
    )
    db.add(tier)
    db.commit()
    db.refresh(tier)
    return _tier_to_read(tier)


def update_tier(
    db: Session,
    tenant_id: int,
    tier_id: int,
    data: LoyaltyTierUpdate,
) -> LoyaltyTierRead:
    tier = (
        db.query(LoyaltyTier)
        .filter(LoyaltyTier.id == tier_id, LoyaltyTier.tenant_id == tenant_id)
        .first()
    )
    if tier is None:
        raise NotFoundError("Loyalty tier not found")
    for key, value in data.model_dump(exclude_unset=True).items():
        setattr(tier, key, value)
    db.commit()
    db.refresh(tier)
    return _tier_to_read(tier)


def resolve_tier(
    db: Session,
    tenant_id: int,
    points: int,
) -> LoyaltyTier | None:
    return (
        db.query(LoyaltyTier)
        .filter(
            LoyaltyTier.tenant_id == tenant_id,
            LoyaltyTier.is_active.is_(True),
            LoyaltyTier.min_points <= points,
        )
        .order_by(LoyaltyTier.min_points.desc())
        .first()
    )


def _ledger_to_read(row: LoyaltyLedger, customer: Customer | None = None) -> LoyaltyLedgerRead:
    return LoyaltyLedgerRead(
        id=row.id,
        customer_id=row.customer_id,
        customer_name=customer.full_name if customer else None,
        customer_mobile=customer.mobile if customer else None,
        outlet_id=row.outlet_id,
        txn_type=row.txn_type,
        source=row.source,
        points=int(row.points),
        balance_after=int(row.balance_after),
        amount_basis=float(row.amount_basis or 0),
        reference_type=row.reference_type,
        reference_id=row.reference_id,
        description=row.description,
        created_by=row.created_by,
        created_at=row.created_at,
        updated_at=row.updated_at,
        is_active=row.is_active,
    )


def _find_existing(
    db: Session,
    tenant_id: int,
    source: LoyaltySource,
    reference_type: str,
    reference_id: str,
    txn_type: LoyaltyTxnType,
) -> LoyaltyLedger | None:
    return (
        db.query(LoyaltyLedger)
        .filter(
            LoyaltyLedger.tenant_id == tenant_id,
            LoyaltyLedger.source == source,
            LoyaltyLedger.reference_type == reference_type,
            LoyaltyLedger.reference_id == str(reference_id),
            LoyaltyLedger.txn_type == txn_type,
            LoyaltyLedger.is_active.is_(True),
        )
        .first()
    )


def _apply_points(
    db: Session,
    *,
    tenant_id: int,
    brand_id: int | None,
    customer: Customer,
    points_delta: int,
    txn_type: LoyaltyTxnType,
    source: LoyaltySource,
    reference_type: str,
    reference_id: str,
    description: str,
    amount_basis: float = 0,
    outlet_id: int | None = None,
    created_by: int | None = None,
) -> LoyaltyLedger | None:
    if points_delta == 0:
        return None

    existing = _find_existing(db, tenant_id, source, reference_type, reference_id, txn_type)
    if existing:
        return existing

    new_balance = int(customer.loyalty_points or 0) + points_delta
    if new_balance < 0:
        raise ConflictError("Insufficient loyalty points")

    customer.loyalty_points = new_balance
    entry = LoyaltyLedger(
        tenant_id=tenant_id,
        brand_id=brand_id or customer.brand_id,
        customer_id=customer.id,
        outlet_id=outlet_id,
        txn_type=txn_type,
        source=source,
        points=points_delta,
        balance_after=new_balance,
        amount_basis=amount_basis,
        reference_type=reference_type,
        reference_id=str(reference_id),
        description=description,
        created_by=created_by,
    )
    db.add(entry)
    db.flush()
    return entry


def _earn_points_for_amount(
    amount: float,
    points_per_100: float,
    multiplier: float = 1.0,
) -> int:
    if amount <= 0 or points_per_100 <= 0:
        return 0
    return int((amount / 100.0) * points_per_100 * multiplier)


def earn_from_pos_bill(
    db: Session,
    tenant_id: int,
    bill,
    order,
    user_id: int | None = None,
) -> LoyaltyLedger | None:
    """Award F&B points when a POS bill becomes fully paid (skip room_charge unless configured)."""
    from app.modules.pos.models import Payment, PaymentMode, PaymentRecordStatus

    if not getattr(order, "customer_id", None):
        return None

    customer = db.get(Customer, order.customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        return None

    config = get_loyalty_config(db, tenant_id, order.brand_id or customer.brand_id)
    if not config.enabled:
        return None

    payments = (
        db.query(Payment)
        .filter(Payment.bill_id == bill.id, Payment.status == PaymentRecordStatus.SUCCESS)
        .all()
    )
    if not config.earn_on_room_charge:
        skip_modes = {PaymentMode.ROOM_CHARGE, PaymentMode.LOYALTY}
        if payments and all(p.payment_mode in skip_modes for p in payments):
            return None
        earn_basis = sum(
            float(p.amount)
            for p in payments
            if p.payment_mode not in skip_modes
        )
    else:
        earn_basis = sum(
            float(p.amount)
            for p in payments
            if p.payment_mode != PaymentMode.LOYALTY
        )
        if earn_basis <= 0:
            earn_basis = float(bill.grand_total)

    if earn_basis <= 0:
        earn_basis = float(bill.grand_total)

    tier = resolve_tier(db, tenant_id, int(customer.loyalty_points or 0))
    multiplier = float(tier.earn_multiplier) if tier else 1.0
    points = _earn_points_for_amount(earn_basis, config.points_per_100, multiplier)
    if points <= 0:
        record_customer_visit(
            db,
            tenant_id,
            customer.id,
            order.outlet_id,
            bill.id,
            datetime.utcnow(),
            float(bill.grand_total),
            brand_id=order.brand_id,
        )
        return None

    entry = _apply_points(
        db,
        tenant_id=tenant_id,
        brand_id=order.brand_id or customer.brand_id,
        customer=customer,
        points_delta=points,
        txn_type=LoyaltyTxnType.EARN,
        source=LoyaltySource.POS,
        reference_type="pos_bill",
        reference_id=str(bill.id),
        description=f"Café / restaurant · bill #{bill.bill_number}",
        amount_basis=earn_basis,
        outlet_id=order.outlet_id,
        created_by=user_id,
    )
    record_customer_visit(
        db,
        tenant_id,
        customer.id,
        order.outlet_id,
        bill.id,
        datetime.utcnow(),
        float(bill.grand_total),
        brand_id=order.brand_id,
    )
    return entry


def burn_for_pos_payment(
    db: Session,
    tenant_id: int,
    *,
    customer_id: int,
    bill_id: int,
    points: int,
    amount: float,
    outlet_id: int | None,
    brand_id: int | None,
    user_id: int | None,
) -> LoyaltyLedger:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise NotFoundError("Customer not found")

    config = get_loyalty_config(db, tenant_id, brand_id or customer.brand_id)
    if not config.enabled:
        raise ConflictError("Loyalty program is disabled")
    if points < config.min_redeem_points:
        raise ConflictError(f"Minimum redeem is {config.min_redeem_points} points")
    if int(customer.loyalty_points or 0) < points:
        raise ConflictError("Insufficient loyalty points")

    expected = round(points * float(config.point_value), 2)
    if abs(expected - round(float(amount), 2)) > 0.05:
        raise ConflictError("Redeem amount does not match point value")

    entry = _apply_points(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id or customer.brand_id,
        customer=customer,
        points_delta=-abs(points),
        txn_type=LoyaltyTxnType.BURN,
        source=LoyaltySource.REDEEM_POS,
        reference_type="pos_bill",
        reference_id=f"{bill_id}:burn",
        description=f"Redeemed {points} pts on bill",
        amount_basis=amount,
        outlet_id=outlet_id,
        created_by=user_id,
    )
    if entry is None:
        raise ConflictError("Could not redeem loyalty points")
    return entry


def earn_from_pms_checkout(
    db: Session,
    tenant_id: int,
    reservation,
    user_id: int | None = None,
) -> LoyaltyLedger | None:
    customer = None
    if reservation.customer_id:
        customer = db.get(Customer, reservation.customer_id)
    if customer is None and reservation.guest_mobile:
        customer = (
            db.query(Customer)
            .filter(Customer.tenant_id == tenant_id, Customer.mobile == reservation.guest_mobile)
            .first()
        )
        if customer and not reservation.customer_id:
            reservation.customer_id = customer.id

    if customer is None:
        return None

    config = get_loyalty_config(db, tenant_id, reservation.brand_id or customer.brand_id)
    if not config.enabled:
        return None

    nights = max(
        (reservation.check_out_date - reservation.check_in_date).days
        if not getattr(reservation, "day_use", False)
        else 1,
        1,
    )
    room_revenue = float(reservation.total_amount or 0)
    if reservation.folio:
        from app.modules.pms.models import FolioEntryType

        room_revenue = sum(
            float(e.amount)
            for e in reservation.folio.entries
            if e.entry_type == FolioEntryType.ROOM_CHARGE and e.is_active
        ) or room_revenue

    tier = resolve_tier(db, tenant_id, int(customer.loyalty_points or 0))
    multiplier = float(tier.earn_multiplier) if tier else 1.0
    night_pts = int(config.stay_points_per_night * nights * multiplier)
    spend_pts = _earn_points_for_amount(room_revenue, config.stay_points_per_100, multiplier)
    points = night_pts + spend_pts
    if points <= 0:
        return None

    return _apply_points(
        db,
        tenant_id=tenant_id,
        brand_id=reservation.brand_id or customer.brand_id,
        customer=customer,
        points_delta=points,
        txn_type=LoyaltyTxnType.EARN,
        source=LoyaltySource.PMS_STAY,
        reference_type="reservation",
        reference_id=str(reservation.id),
        description=f"Stay · {reservation.confirmation_number} · {nights} night(s)",
        amount_basis=room_revenue,
        outlet_id=reservation.outlet_id,
        created_by=user_id,
    )


def burn_for_folio_payment(
    db: Session,
    tenant_id: int,
    *,
    customer_id: int,
    reservation_id: int,
    points: int,
    amount: float,
    outlet_id: int | None,
    brand_id: int | None,
    user_id: int | None,
) -> LoyaltyLedger:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise NotFoundError("Customer not found")
    config = get_loyalty_config(db, tenant_id, brand_id or customer.brand_id)
    if not config.enabled:
        raise ConflictError("Loyalty program is disabled")
    if points < config.min_redeem_points:
        raise ConflictError(f"Minimum redeem is {config.min_redeem_points} points")
    if int(customer.loyalty_points or 0) < points:
        raise ConflictError("Insufficient loyalty points")

    expected = round(points * float(config.point_value), 2)
    if abs(expected - round(float(amount), 2)) > 0.05:
        raise ConflictError("Redeem amount does not match point value")

    entry = _apply_points(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id or customer.brand_id,
        customer=customer,
        points_delta=-abs(points),
        txn_type=LoyaltyTxnType.BURN,
        source=LoyaltySource.REDEEM_FOLIO,
        reference_type="reservation",
        reference_id=f"{reservation_id}:burn:{points}:{int(amount * 100)}",
        description=f"Redeemed {points} pts on folio",
        amount_basis=amount,
        outlet_id=outlet_id,
        created_by=user_id,
    )
    if entry is None:
        raise ConflictError("Could not redeem loyalty points")
    return entry


def adjust_points(
    db: Session,
    tenant_id: int,
    data: LoyaltyAdjustRequest,
    user_id: int | None = None,
    brand_id: int | None = None,
) -> LoyaltyLedgerRead:
    customer = db.get(Customer, data.customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise NotFoundError("Customer not found")
    if data.points == 0:
        raise ConflictError("Points adjustment cannot be zero")

    txn_type = LoyaltyTxnType.ADJUST
    entry = _apply_points(
        db,
        tenant_id=tenant_id,
        brand_id=brand_id or customer.brand_id,
        customer=customer,
        points_delta=data.points,
        txn_type=txn_type,
        source=LoyaltySource.MANUAL,
        reference_type="manual",
        reference_id=f"{customer.id}:{datetime.utcnow().timestamp()}",
        description=data.description.strip(),
        outlet_id=data.outlet_id,
        created_by=user_id,
    )
    db.commit()
    assert entry is not None
    return _ledger_to_read(entry, customer)


def get_redeem_preview(
    db: Session,
    tenant_id: int,
    customer_id: int,
    brand_id: int | None = None,
) -> LoyaltyRedeemPreview:
    customer = db.get(Customer, customer_id)
    if customer is None or customer.tenant_id != tenant_id:
        raise NotFoundError("Customer not found")
    config = get_loyalty_config(db, tenant_id, brand_id or customer.brand_id)
    balance = int(customer.loyalty_points or 0)
    can = config.enabled and balance >= config.min_redeem_points
    return LoyaltyRedeemPreview(
        customer_id=customer.id,
        points_balance=balance,
        min_redeem_points=config.min_redeem_points,
        point_value=config.point_value,
        max_redeem_points=balance if can else 0,
        max_redeem_value=round(balance * config.point_value, 2) if can else 0,
        can_redeem=can,
    )


def list_ledger(
    db: Session,
    tenant_id: int,
    *,
    customer_id: int | None = None,
    page: int = 1,
    page_size: int = 50,
) -> tuple[list[LoyaltyLedgerRead], int]:
    query = db.query(LoyaltyLedger, Customer).join(
        Customer, Customer.id == LoyaltyLedger.customer_id
    ).filter(LoyaltyLedger.tenant_id == tenant_id, LoyaltyLedger.is_active.is_(True))
    if customer_id:
        query = query.filter(LoyaltyLedger.customer_id == customer_id)
    total = query.count()
    rows = (
        query.order_by(LoyaltyLedger.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
        .all()
    )
    return [_ledger_to_read(ledger, customer) for ledger, customer in rows], total


def member_read(db: Session, tenant_id: int, customer: Customer) -> LoyaltyMemberRead:
    tier = resolve_tier(db, tenant_id, int(customer.loyalty_points or 0))
    return LoyaltyMemberRead(
        customer_id=customer.id,
        full_name=customer.full_name,
        mobile=customer.mobile,
        email=customer.email,
        loyalty_points=int(customer.loyalty_points or 0),
        total_spend=float(customer.total_spend or 0),
        total_visits=int(customer.total_visits or 0),
        tier_code=tier.code if tier else None,
        tier_name=tier.name if tier else None,
        tier_color=tier.color if tier else None,
        earn_multiplier=float(tier.earn_multiplier) if tier else 1,
        last_visit_at=customer.last_visit_at,
    )


def get_summary(db: Session, tenant_id: int, brand_id: int | None = None) -> LoyaltySummaryRead:
    ensure_default_tiers(db, tenant_id, brand_id)
    config = get_loyalty_config(db, tenant_id, brand_id)
    since = datetime.utcnow() - timedelta(days=30)

    members = db.query(func.count(Customer.id)).filter(Customer.tenant_id == tenant_id).scalar() or 0
    total_points = (
        db.query(func.coalesce(func.sum(Customer.loyalty_points), 0))
        .filter(Customer.tenant_id == tenant_id)
        .scalar()
        or 0
    )
    earned_30d = (
        db.query(func.coalesce(func.sum(LoyaltyLedger.points), 0))
        .filter(
            LoyaltyLedger.tenant_id == tenant_id,
            LoyaltyLedger.txn_type == LoyaltyTxnType.EARN,
            LoyaltyLedger.created_at >= since,
        )
        .scalar()
        or 0
    )
    redeemed_30d = (
        db.query(func.coalesce(func.sum(LoyaltyLedger.points), 0))
        .filter(
            LoyaltyLedger.tenant_id == tenant_id,
            LoyaltyLedger.txn_type == LoyaltyTxnType.BURN,
            LoyaltyLedger.created_at >= since,
        )
        .scalar()
        or 0
    )

    top = (
        db.query(Customer)
        .filter(Customer.tenant_id == tenant_id)
        .order_by(Customer.loyalty_points.desc())
        .limit(8)
        .all()
    )
    recent, _ = list_ledger(db, tenant_id, page=1, page_size=12)

    return LoyaltySummaryRead(
        members=int(members),
        total_points=int(total_points),
        earned_30d=int(earned_30d),
        redeemed_30d=abs(int(redeemed_30d)),
        config=config,
        tiers=list_tiers(db, tenant_id),
        top_members=[member_read(db, tenant_id, c) for c in top],
        recent_ledger=recent,
    )
