"""PMS demo reservations — arrivals, in-house, and upcoming stays."""

from __future__ import annotations

from datetime import date, timedelta

from sqlalchemy.orm import Session

from app.modules.housekeeping.models import HotelRoom, RoomType
from app.modules.pms import service as pms_service
from app.modules.pms.models import (
    CreditScope,
    GuaranteeType,
    GuestReservation,
    InclusionType,
    RatePlan,
    RatePlanInclusion,
    ReservationGroup,
    ReservationSource,
    ReservationStatus,
    RoomBlock,
    RoomBlockType,
)
from app.modules.pms.schemas import (
    CheckInRequest,
    GroupRoomingCreate,
    GroupRoomingStay,
    ReservationCreate,
    ReservationGroupCreate,
    RoomBlockCreate,
)
from app.seeds.base import SeedContext


def seed_rate_plans(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    existing = db.query(RatePlan).filter(RatePlan.tenant_id == tenant.id).first()
    if existing:
        return

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    if not room_types:
        return

    today = date.today()
    summer_start = date(today.year, 6, 1)
    summer_end = date(today.year, 8, 31)

    for room_type in room_types:
        base = float(room_type.base_rate)
        code_prefix = room_type.name.upper().replace(" ", "_")[:8]

        plans = [
            {
                "name": f"{room_type.name} Rack Rate",
                "code": f"{code_prefix}_RACK",
                "rate_per_night": base,
                "is_default": True,
                "source": None,
                "valid_from": None,
                "valid_to": None,
                "min_nights": 1,
                "description": "Standard walk-in and direct booking rate",
                "cancellation_fee_percent": 25,
                "no_show_fee_percent": 50,
                "default_guarantee": GuaranteeType.DEPOSIT,
            },
            {
                "name": f"{room_type.name} Booking.com",
                "code": f"{code_prefix}_BCOM",
                "rate_per_night": round(base * 0.9, 2),
                "is_default": False,
                "source": ReservationSource.OTA_BOOKING_COM,
                "valid_from": None,
                "valid_to": None,
                "min_nights": 1,
                "description": "OTA net rate for Booking.com",
                "cancellation_fee_percent": 100,
                "no_show_fee_percent": 100,
                "default_guarantee": GuaranteeType.NONE,
            },
            {
                "name": f"{room_type.name} MakeMyTrip",
                "code": f"{code_prefix}_MMT",
                "rate_per_night": round(base * 0.92, 2),
                "is_default": False,
                "source": ReservationSource.OTA_MMT,
                "valid_from": None,
                "valid_to": None,
                "min_nights": 1,
                "description": "OTA net rate for MakeMyTrip",
                "cancellation_fee_percent": 100,
                "no_show_fee_percent": 100,
                "default_guarantee": GuaranteeType.NONE,
            },
            {
                "name": f"{room_type.name} Summer Peak",
                "code": f"{code_prefix}_SUMMER",
                "rate_per_night": round(base * 1.15, 2),
                "is_default": False,
                "source": None,
                "valid_from": summer_start,
                "valid_to": summer_end,
                "min_nights": 2,
                "description": "Seasonal peak pricing (Jun–Aug)",
                "cancellation_fee_percent": 50,
                "no_show_fee_percent": 100,
                "default_guarantee": GuaranteeType.DEPOSIT,
            },
        ]

        for spec in plans:
            db.add(
                RatePlan(
                    tenant_id=tenant.id,
                    brand_id=ctx.brand.id,
                    room_type_id=room_type.id,
                    **spec,
                )
            )

    db.flush()


def seed_rate_plan_packages(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    existing = (
        db.query(RatePlanInclusion)
        .filter(RatePlanInclusion.tenant_id == tenant.id)
        .first()
    )
    if existing:
        return

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    if not room_types:
        return

    package_specs = [
        {
            "suffix": "BB",
            "name_suffix": "with Breakfast",
            "description": "Room rate plus daily continental breakfast",
            "inclusions": [
                {
                    "inclusion_type": InclusionType.BREAKFAST,
                    "name": "Continental Breakfast",
                    "price_per_night": 500,
                    "credit_amount": 0,
                    "credit_scope": CreditScope.STAY,
                    "qty_per_night": 0,
                    "qty_per_stay": 0,
                },
            ],
        },
        {
            "suffix": "SPA",
            "name_suffix": "Spa Escape",
            "description": "Room rate plus daily spa access",
            "inclusions": [
                {
                    "inclusion_type": InclusionType.SPA,
                    "name": "Spa & Wellness Access",
                    "price_per_night": 1200,
                    "credit_amount": 0,
                    "credit_scope": CreditScope.STAY,
                    "qty_per_night": 1,
                    "qty_per_stay": 0,
                },
            ],
        },
        {
            "suffix": "CAFE",
            "name_suffix": "Café Credit",
            "description": "Room rate plus resort café voucher for the stay",
            "inclusions": [
                {
                    "inclusion_type": InclusionType.CAFE,
                    "name": "Café Credit ₹2,000",
                    "price_per_night": 0,
                    "credit_amount": 2000,
                    "credit_scope": CreditScope.STAY,
                    "qty_per_night": 0,
                    "qty_per_stay": 0,
                },
                {
                    "inclusion_type": InclusionType.BREAKFAST,
                    "name": "Buffet Breakfast",
                    "price_per_night": 650,
                    "credit_amount": 0,
                    "credit_scope": CreditScope.STAY,
                    "qty_per_night": 0,
                    "qty_per_stay": 0,
                },
            ],
        },
    ]

    for room_type in room_types:
        base = float(room_type.base_rate)
        code_prefix = room_type.name.upper().replace(" ", "_")[:8]

        for spec in package_specs:
            code = f"{code_prefix}_{spec['suffix']}"
            plan_exists = (
                db.query(RatePlan)
                .filter(RatePlan.tenant_id == tenant.id, RatePlan.code == code)
                .first()
            )
            if plan_exists:
                plan = plan_exists
            else:
                plan = RatePlan(
                    tenant_id=tenant.id,
                    brand_id=ctx.brand.id,
                    room_type_id=room_type.id,
                    name=f"{room_type.name} {spec['name_suffix']}",
                    code=code,
                    rate_per_night=base,
                    is_default=False,
                    source=None,
                    min_nights=1,
                    description=spec["description"],
                )
                db.add(plan)
                db.flush()

            for inclusion_spec in spec["inclusions"]:
                db.add(
                    RatePlanInclusion(
                        tenant_id=tenant.id,
                        brand_id=ctx.brand.id,
                        rate_plan_id=plan.id,
                        inclusion_type=inclusion_spec["inclusion_type"],
                        name=inclusion_spec["name"],
                        price_per_night=inclusion_spec["price_per_night"],
                        is_included=True,
                        credit_amount=inclusion_spec.get("credit_amount", 0),
                        credit_scope=inclusion_spec.get("credit_scope", CreditScope.STAY),
                        qty_per_stay=inclusion_spec.get("qty_per_stay", 0),
                        qty_per_night=inclusion_spec.get("qty_per_night", 0),
                    )
                )

    db.flush()


def seed_pms_policy_fees(db: Session, ctx: SeedContext) -> None:
    """Backfill cancel/no-show fees on existing rack plans that still have 0%."""
    plans = (
        db.query(RatePlan)
        .filter(
            RatePlan.tenant_id == ctx.tenant.id,
            RatePlan.is_active.is_(True),
            RatePlan.cancellation_fee_percent == 0,
            RatePlan.no_show_fee_percent == 0,
        )
        .all()
    )
    for plan in plans:
        if plan.is_default or (plan.code or "").endswith("_RACK"):
            plan.cancellation_fee_percent = 25
            plan.no_show_fee_percent = 50
            plan.default_guarantee = GuaranteeType.DEPOSIT
        elif plan.source in {
            ReservationSource.OTA_BOOKING_COM,
            ReservationSource.OTA_MMT,
            ReservationSource.OTA_EXPEDIA,
        }:
            plan.cancellation_fee_percent = 100
            plan.no_show_fee_percent = 100
    db.flush()


def seed_pms_room_blocks(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    admin = ctx.users.get("admin@restrochain.test") or ctx.users.get("admin@example.com")
    if admin is None:
        return
    existing = db.query(RoomBlock).filter(RoomBlock.tenant_id == tenant.id).first()
    if existing:
        return

    andheri = ctx.outlets.get("Andheri West")
    if andheri is None:
        return

    room = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == tenant.id,
            HotelRoom.outlet_id == andheri.id,
            HotelRoom.is_active.is_(True),
        )
        .order_by(HotelRoom.room_number)
        .first()
    )
    if room is None:
        return

    today = date.today()
    pms_service.create_room_block(
        db,
        tenant.id,
        admin.id,
        RoomBlockCreate(
            outlet_id=andheri.id,
            room_id=room.id,
            start_date=today + timedelta(days=10),
            end_date=today + timedelta(days=12),
            block_type=RoomBlockType.MAINTENANCE,
            reason="Demo HVAC maintenance",
        ),
        default_brand_id=ctx.brand.id,
    )


def seed_pms_groups(db: Session, ctx: SeedContext) -> None:
    tenant = ctx.tenant
    admin = ctx.users.get("admin@restrochain.test") or ctx.users.get("admin@example.com")
    if admin is None:
        return

    andheri = ctx.outlets.get("Andheri West")
    if andheri is None:
        return

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    if not room_types:
        return
    type_map = {rt.name: rt for rt in room_types}
    standard = type_map.get("Standard") or room_types[0]
    deluxe = type_map.get("Deluxe") or room_types[-1]

    group = (
        db.query(ReservationGroup)
        .filter(ReservationGroup.tenant_id == tenant.id, ReservationGroup.group_code == "WEDDING-DEMO")
        .first()
    )
    if group is None:
        created = pms_service.create_reservation_group(
            db,
            tenant.id,
            admin.id,
            ReservationGroupCreate(
                outlet_id=andheri.id,
                name="Mehta Wedding Party",
                group_code="WEDDING-DEMO",
                shared_deposit=25000,
                notes="Demo group booking for rooming list",
            ),
            default_brand_id=ctx.brand.id,
        )
        group_id = created.id
    else:
        group_id = group.id

    linked = (
        db.query(GuestReservation)
        .filter(
            GuestReservation.tenant_id == tenant.id,
            GuestReservation.group_id == group_id,
            GuestReservation.is_active.is_(True),
        )
        .count()
    )
    if linked > 0:
        return

    today = date.today()
    pms_service.add_group_reservations(
        db,
        tenant.id,
        admin.id,
        group_id,
        GroupRoomingCreate(
            auto_confirm=True,
            stays=[
                GroupRoomingStay(
                    guest_name="Priya Mehta",
                    guest_mobile="+919810000201",
                    room_type_id=standard.id,
                    check_in_date=today + timedelta(days=14),
                    check_out_date=today + timedelta(days=16),
                    adults=2,
                    rate_per_night=float(standard.base_rate),
                    notes="Bride family",
                ),
                GroupRoomingStay(
                    guest_name="Rohan Mehta",
                    guest_mobile="+919810000202",
                    room_type_id=deluxe.id,
                    check_in_date=today + timedelta(days=14),
                    check_out_date=today + timedelta(days=16),
                    adults=2,
                    rate_per_night=float(deluxe.base_rate),
                    notes="Groom family",
                ),
            ],
        ),
        default_brand_id=ctx.brand.id,
    )


def seed_pms(db: Session, ctx: SeedContext) -> None:
    seed_rate_plans(db, ctx)
    seed_rate_plan_packages(db, ctx)
    seed_pms_policy_fees(db, ctx)
    seed_pms_room_blocks(db, ctx)
    seed_pms_groups(db, ctx)

    tenant, brand = ctx.tenant, ctx.brand
    admin = ctx.users.get("admin@restrochain.test") or ctx.users.get("admin@example.com")
    if admin is None:
        return

    existing = db.query(GuestReservation).filter(GuestReservation.tenant_id == tenant.id).first()
    if existing:
        return

    andheri = ctx.outlets.get("Andheri West")
    if andheri is None:
        return

    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
        .all()
    )
    if not room_types:
        return

    rooms = (
        db.query(HotelRoom)
        .filter(HotelRoom.tenant_id == tenant.id, HotelRoom.outlet_id == andheri.id, HotelRoom.is_active.is_(True))
        .order_by(HotelRoom.room_number)
        .all()
    )
    type_map = {rt.name: rt for rt in room_types}
    today = date.today()

    specs = [
        {
            "guest_name": "Rajesh Kumar",
            "guest_mobile": "+919810000101",
            "room_type": "Standard",
            "check_in": today,
            "check_out": today + timedelta(days=2),
            "status": ReservationStatus.CONFIRMED,
            "source": ReservationSource.DIRECT,
            "auto_confirm": True,
        },
        {
            "guest_name": "Sarah Mitchell",
            "guest_mobile": "+919810000102",
            "room_type": "Suite",
            "check_in": today - timedelta(days=1),
            "check_out": today + timedelta(days=1),
            "status": ReservationStatus.CHECKED_IN,
            "source": ReservationSource.OTA_BOOKING_COM,
            "room_number": "202",
        },
        {
            "guest_name": "Amit Patel",
            "guest_mobile": "+919810000103",
            "room_type": "Suite",
            "check_in": today + timedelta(days=1),
            "check_out": today + timedelta(days=4),
            "status": ReservationStatus.CONFIRMED,
            "source": ReservationSource.PHONE,
            "auto_confirm": True,
        },
        {
            "guest_name": "Neha Sharma",
            "guest_mobile": "+919810000104",
            "room_type": "Standard",
            "check_in": today + timedelta(days=3),
            "check_out": today + timedelta(days=5),
            "status": ReservationStatus.PENDING,
            "source": ReservationSource.WALK_IN,
        },
        {
            "guest_name": "Vikram Malhotra",
            "guest_mobile": "+919810000105",
            "room_type": "Deluxe",
            "check_in": today + timedelta(days=5),
            "check_out": today + timedelta(days=8),
            "status": ReservationStatus.CONFIRMED,
            "source": ReservationSource.OTA_MMT,
            "auto_confirm": True,
        },
    ]

    for spec in specs:
        room_type = type_map.get(spec["room_type"])
        if not room_type:
            continue

        room_id = None
        if spec.get("room_number"):
            match = next((r for r in rooms if r.room_number == spec["room_number"]), None)
            room_id = match.id if match else None

        reservation = pms_service.create_reservation(
            db,
            tenant.id,
            admin.id,
            ReservationCreate(
                outlet_id=andheri.id,
                guest_name=spec["guest_name"],
                guest_mobile=spec["guest_mobile"],
                room_type_id=room_type.id,
                room_id=room_id,
                check_in_date=spec["check_in"],
                check_out_date=spec["check_out"],
                source=spec["source"],
                rate_per_night=float(room_type.base_rate),
                auto_confirm=spec.get("auto_confirm", False),
            ),
            default_brand_id=brand.id,
        )

        if spec["status"] == ReservationStatus.CHECKED_IN and room_id:
            pms_service.check_in_reservation(
                db,
                tenant.id,
                admin.id,
                reservation.id,
                CheckInRequest(room_id=room_id),
            )

    db.flush()
