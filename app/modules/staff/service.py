"""Staff roster and tip-pool settlement services."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from decimal import Decimal

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.core.exceptions import AppError, ConflictError, NotFoundError
from app.modules.outlets.models import Outlet
from app.modules.pos.models import Bill, Payment, PaymentRecordStatus
from app.modules.staff.models import StaffRoleType, StaffShift, TipPool, TipPoolLine, TipPoolStatus
from app.modules.staff.schemas import (
    StaffDaySummary,
    StaffMemberRead,
    StaffShiftCreate,
    StaffShiftRead,
    StaffShiftUpdate,
    TipPoolDistributeRequest,
    TipPoolLineRead,
    TipPoolRead,
)
from app.modules.users.models import User, UserOutlet
from app.modules.roles.models import Role


def _money(value: float | Decimal | None) -> float:
    return round(float(value or 0), 2)


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = (
        db.query(Outlet)
        .filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id, Outlet.is_active.is_(True))
        .first()
    )
    if not outlet:
        raise NotFoundError("Outlet not found")
    return outlet


def _user_name_map(db: Session, tenant_id: int, user_ids: list[int]) -> dict[int, str]:
    if not user_ids:
        return {}
    rows = (
        db.query(User.id, User.full_name)
        .filter(User.tenant_id == tenant_id, User.id.in_(user_ids))
        .all()
    )
    return {row.id: row.full_name for row in rows}


def _shift_read(shift: StaffShift, name: str | None = None) -> StaffShiftRead:
    return StaffShiftRead(
        id=shift.id,
        outlet_id=shift.outlet_id,
        brand_id=shift.brand_id,
        user_id=shift.user_id,
        user_name=name,
        role_type=shift.role_type,
        shift_date=shift.shift_date,
        start_at=shift.start_at,
        end_at=shift.end_at,
        notes=shift.notes,
        tip_eligible=shift.tip_eligible,
        is_active=shift.is_active,
    )


def _pool_read(pool: TipPool, names: dict[int, str] | None = None) -> TipPoolRead:
    names = names or {}
    lines = [
        TipPoolLineRead(
            id=line.id,
            tip_pool_id=line.tip_pool_id,
            user_id=line.user_id,
            user_name=names.get(line.user_id),
            role_type=line.role_type,
            share_percent=float(line.share_percent) if line.share_percent is not None else None,
            amount=_money(line.amount),
            staff_shift_id=line.staff_shift_id,
        )
        for line in (pool.lines or [])
    ]
    return TipPoolRead(
        id=pool.id,
        outlet_id=pool.outlet_id,
        brand_id=pool.brand_id,
        shift_date=pool.shift_date,
        status=pool.status,
        expected_amount=_money(pool.expected_amount),
        declared_amount=_money(pool.declared_amount) if pool.declared_amount is not None else None,
        pool_amount=_money(pool.pool_amount),
        variance=_money(pool.variance) if pool.variance is not None else None,
        notes=pool.notes,
        settled_at=pool.settled_at,
        settled_by=pool.settled_by,
        lines=lines,
    )


def sum_pos_tips(db: Session, tenant_id: int, outlet_id: int, shift_date: date) -> float:
    """Sum tip_amount on successful POS payments for bills created that day at the outlet."""
    day_start = datetime.combine(shift_date, time.min)
    day_end = day_start + timedelta(days=1)
    total = (
        db.query(func.coalesce(func.sum(Payment.tip_amount), 0))
        .join(Bill, Bill.id == Payment.bill_id)
        .filter(
            Bill.tenant_id == tenant_id,
            Bill.outlet_id == outlet_id,
            Payment.status == PaymentRecordStatus.SUCCESS,
            Bill.created_at >= day_start,
            Bill.created_at < day_end,
        )
        .scalar()
    )
    return _money(total)


def list_outlet_staff(db: Session, tenant_id: int, outlet_id: int) -> list[StaffMemberRead]:
    """Lightweight staff picker for roster (POS_READ) — avoids requiring users:read."""
    _get_outlet(db, tenant_id, outlet_id)
    rows = (
        db.query(User.id, User.full_name, Role.name)
        .outerjoin(Role, Role.id == User.role_id)
        .join(UserOutlet, UserOutlet.user_id == User.id)
        .filter(
            User.tenant_id == tenant_id,
            User.is_active.is_(True),
            UserOutlet.outlet_id == outlet_id,
        )
        .order_by(User.full_name.asc())
        .all()
    )
    # Also include tenant staff with no outlet assignment (fallback)
    if not rows:
        rows = (
            db.query(User.id, User.full_name, Role.name)
            .outerjoin(Role, Role.id == User.role_id)
            .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
            .order_by(User.full_name.asc())
            .limit(100)
            .all()
        )
    return [
        StaffMemberRead(id=row.id, full_name=row.full_name, role_name=row.name)
        for row in rows
    ]


def list_shifts(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
    shift_date: date | None = None,
    include_inactive: bool = False,
) -> list[StaffShiftRead]:
    q = db.query(StaffShift).filter(StaffShift.tenant_id == tenant_id)
    if not include_inactive:
        q = q.filter(StaffShift.is_active.is_(True))
    if outlet_id:
        q = q.filter(StaffShift.outlet_id == outlet_id)
    if shift_date:
        q = q.filter(StaffShift.shift_date == shift_date)
    shifts = q.order_by(StaffShift.start_at.asc(), StaffShift.id.asc()).all()
    names = _user_name_map(db, tenant_id, [s.user_id for s in shifts])
    return [_shift_read(s, names.get(s.user_id)) for s in shifts]


def create_shift(
    db: Session,
    tenant_id: int,
    data: StaffShiftCreate,
    *,
    brand_id: int | None,
    user_id: int | None,
) -> StaffShiftRead:
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    staff = (
        db.query(User)
        .filter(User.id == data.user_id, User.tenant_id == tenant_id, User.is_active.is_(True))
        .first()
    )
    if not staff:
        raise NotFoundError("Staff user not found")
    if data.end_at <= data.start_at:
        raise AppError("Shift end must be after start")

    overlap = (
        db.query(StaffShift)
        .filter(
            StaffShift.tenant_id == tenant_id,
            StaffShift.outlet_id == data.outlet_id,
            StaffShift.user_id == data.user_id,
            StaffShift.shift_date == data.shift_date,
            StaffShift.is_active.is_(True),
            StaffShift.start_at < data.end_at,
            StaffShift.end_at > data.start_at,
        )
        .first()
    )
    if overlap:
        raise ConflictError("This staff member already has an overlapping shift")

    shift = StaffShift(
        tenant_id=tenant_id,
        brand_id=brand_id or outlet.brand_id,
        outlet_id=data.outlet_id,
        user_id=data.user_id,
        role_type=data.role_type,
        shift_date=data.shift_date,
        start_at=data.start_at,
        end_at=data.end_at,
        notes=data.notes,
        tip_eligible=data.tip_eligible,
        created_by=user_id,
    )
    db.add(shift)
    db.commit()
    db.refresh(shift)
    return _shift_read(shift, staff.full_name)


def update_shift(
    db: Session,
    tenant_id: int,
    shift_id: int,
    data: StaffShiftUpdate,
) -> StaffShiftRead:
    shift = (
        db.query(StaffShift)
        .filter(StaffShift.id == shift_id, StaffShift.tenant_id == tenant_id)
        .first()
    )
    if not shift:
        raise NotFoundError("Shift not found")

    payload = data.model_dump(exclude_unset=True)
    start_at = payload.get("start_at", shift.start_at)
    end_at = payload.get("end_at", shift.end_at)
    if end_at <= start_at:
        raise AppError("Shift end must be after start")

    for key, value in payload.items():
        setattr(shift, key, value)

    db.commit()
    db.refresh(shift)
    names = _user_name_map(db, tenant_id, [shift.user_id])
    return _shift_read(shift, names.get(shift.user_id))


def ensure_tip_pool(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    shift_date: date,
    *,
    brand_id: int | None = None,
) -> TipPool:
    outlet = _get_outlet(db, tenant_id, outlet_id)
    pool = (
        db.query(TipPool)
        .options(joinedload(TipPool.lines))
        .filter(
            TipPool.tenant_id == tenant_id,
            TipPool.outlet_id == outlet_id,
            TipPool.shift_date == shift_date,
        )
        .first()
    )
    expected = sum_pos_tips(db, tenant_id, outlet_id, shift_date)
    if not pool:
        pool = TipPool(
            tenant_id=tenant_id,
            brand_id=brand_id or outlet.brand_id,
            outlet_id=outlet_id,
            shift_date=shift_date,
            status=TipPoolStatus.OPEN,
            expected_amount=expected,
            pool_amount=expected,
        )
        db.add(pool)
        db.commit()
        db.refresh(pool)
        pool = (
            db.query(TipPool)
            .options(joinedload(TipPool.lines))
            .filter(TipPool.id == pool.id)
            .first()
        )
        return pool  # type: ignore[return-value]

    if pool.status == TipPoolStatus.OPEN:
        pool.expected_amount = expected
        pool.pool_amount = expected
        db.commit()
        db.refresh(pool)
    return pool


def get_tip_pool(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int,
    shift_date: date,
    ensure: bool = True,
) -> TipPoolRead:
    if ensure:
        pool = ensure_tip_pool(db, tenant_id, outlet_id, shift_date)
    else:
        pool = (
            db.query(TipPool)
            .options(joinedload(TipPool.lines))
            .filter(
                TipPool.tenant_id == tenant_id,
                TipPool.outlet_id == outlet_id,
                TipPool.shift_date == shift_date,
            )
            .first()
        )
        if not pool:
            expected = sum_pos_tips(db, tenant_id, outlet_id, shift_date)
            return TipPoolRead(
                id=0,
                outlet_id=outlet_id,
                brand_id=None,
                shift_date=shift_date,
                status=TipPoolStatus.OPEN,
                expected_amount=expected,
                declared_amount=None,
                pool_amount=expected,
                variance=None,
                notes=None,
                settled_at=None,
                settled_by=None,
                lines=[],
            )
    names = _user_name_map(db, tenant_id, [line.user_id for line in (pool.lines or [])])
    return _pool_read(pool, names)


def list_tip_pools(
    db: Session,
    tenant_id: int,
    *,
    outlet_id: int | None = None,
    limit: int = 30,
) -> list[TipPoolRead]:
    q = (
        db.query(TipPool)
        .options(joinedload(TipPool.lines))
        .filter(TipPool.tenant_id == tenant_id)
    )
    if outlet_id:
        q = q.filter(TipPool.outlet_id == outlet_id)
    pools = q.order_by(TipPool.shift_date.desc(), TipPool.id.desc()).limit(limit).all()
    user_ids = [line.user_id for pool in pools for line in (pool.lines or [])]
    names = _user_name_map(db, tenant_id, user_ids)
    return [_pool_read(pool, names) for pool in pools]


def refresh_tip_pool(db: Session, tenant_id: int, pool_id: int) -> TipPoolRead:
    pool = (
        db.query(TipPool)
        .options(joinedload(TipPool.lines))
        .filter(TipPool.id == pool_id, TipPool.tenant_id == tenant_id)
        .first()
    )
    if not pool:
        raise NotFoundError("Tip pool not found")
    if pool.status != TipPoolStatus.OPEN:
        raise ConflictError("Only open tip pools can be refreshed")
    expected = sum_pos_tips(db, tenant_id, pool.outlet_id, pool.shift_date)
    pool.expected_amount = expected
    pool.pool_amount = expected
    db.commit()
    db.refresh(pool)
    return _pool_read(pool)


def distribute_tip_pool(
    db: Session,
    tenant_id: int,
    pool_id: int,
    data: TipPoolDistributeRequest,
    *,
    settled_by: int | None,
) -> TipPoolRead:
    pool = (
        db.query(TipPool)
        .options(joinedload(TipPool.lines))
        .filter(TipPool.id == pool_id, TipPool.tenant_id == tenant_id)
        .first()
    )
    if not pool:
        raise NotFoundError("Tip pool not found")
    if pool.status != TipPoolStatus.OPEN:
        raise ConflictError("Tip pool is already settled")

    expected = sum_pos_tips(db, tenant_id, pool.outlet_id, pool.shift_date)
    pool.expected_amount = expected
    declared = data.declared_amount if data.declared_amount is not None else expected
    pool.declared_amount = _money(declared)
    pool.pool_amount = _money(declared)
    pool.variance = _money(declared - expected)
    pool.notes = data.notes

    # Clear previous draft lines if any
    for line in list(pool.lines or []):
        db.delete(line)
    db.flush()

    shifts = (
        db.query(StaffShift)
        .filter(
            StaffShift.tenant_id == tenant_id,
            StaffShift.outlet_id == pool.outlet_id,
            StaffShift.shift_date == pool.shift_date,
            StaffShift.is_active.is_(True),
            StaffShift.tip_eligible.is_(True),
        )
        .order_by(StaffShift.start_at.asc())
        .all()
    )

    lines_to_add: list[TipPoolLine] = []

    if data.method == "custom":
        if not data.lines:
            raise AppError("Custom distribution requires lines")
        total = _money(sum(line.amount for line in data.lines))
        if abs(total - _money(declared)) > 0.05:
            raise AppError(
                f"Custom line total ({total}) must match declared pool ({_money(declared)})"
            )
        shift_by_user = {s.user_id: s for s in shifts}
        for item in data.lines:
            shift = shift_by_user.get(item.user_id)
            share = (_money(item.amount) / _money(declared) * 100) if declared else 0
            lines_to_add.append(
                TipPoolLine(
                    tip_pool_id=pool.id,
                    user_id=item.user_id,
                    role_type=item.role_type
                    or (shift.role_type if shift else StaffRoleType.OTHER),
                    share_percent=round(share, 3),
                    amount=_money(item.amount),
                    staff_shift_id=item.staff_shift_id or (shift.id if shift else None),
                )
            )
    else:
        if not shifts:
            raise AppError(
                "No tip-eligible staff on roster for this day — add shifts first or use custom split"
            )
        count = len(shifts)
        base = _money(declared / count)
        # Fix rounding on last share
        allocated = 0.0
        for idx, shift in enumerate(shifts):
            amount = _money(declared - allocated) if idx == count - 1 else base
            allocated = _money(allocated + amount)
            share = (amount / _money(declared) * 100) if declared else 0
            lines_to_add.append(
                TipPoolLine(
                    tip_pool_id=pool.id,
                    user_id=shift.user_id,
                    role_type=shift.role_type,
                    share_percent=round(share, 3),
                    amount=amount,
                    staff_shift_id=shift.id,
                )
            )

    for line in lines_to_add:
        db.add(line)

    pool.status = TipPoolStatus.DISTRIBUTED
    pool.settled_at = datetime.utcnow()
    pool.settled_by = settled_by
    db.commit()

    pool = (
        db.query(TipPool)
        .options(joinedload(TipPool.lines))
        .filter(TipPool.id == pool_id)
        .first()
    )
    names = _user_name_map(db, tenant_id, [line.user_id for line in (pool.lines or [])])  # type: ignore[union-attr]
    return _pool_read(pool, names)  # type: ignore[arg-type]


def get_day_summary(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    shift_date: date,
) -> StaffDaySummary:
    shifts = list_shifts(db, tenant_id, outlet_id=outlet_id, shift_date=shift_date)
    eligible = sum(1 for s in shifts if s.tip_eligible)
    expected = sum_pos_tips(db, tenant_id, outlet_id, shift_date)
    pool = get_tip_pool(db, tenant_id, outlet_id=outlet_id, shift_date=shift_date, ensure=False)
    return StaffDaySummary(
        outlet_id=outlet_id,
        shift_date=shift_date,
        shift_count=len(shifts),
        tip_eligible_count=eligible,
        tip_pool=pool if pool.id else None,
        expected_tips=expected,
    )
