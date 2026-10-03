"""Housekeeping demo data — room types, rooms, templates, tasks, and tickets."""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta

from sqlalchemy.orm import Session

from app.modules.housekeeping.models import (
    Amenity,
    HotelRoom,
    HousekeepingFloorAssignment,
    HousekeepingSweepSchedule,
    HousekeepingTask,
    HousekeepingTaskStatus,
    HousekeepingTaskType,
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceTicket,
    MaintenanceTicketStatus,
    RoomStatus,
    RoomType,
)
from app.modules.housekeeping import service
from app.modules.housekeeping.room_catalog import sync_room_type_amenities
from app.modules.housekeeping.service import seed_default_templates
from app.modules.outlets.models import Outlet
from app.seeds.base import SeedContext
from app.seeds.constants import SUPER_ADMIN_EMAIL


ROOM_TYPE_AMENITY_CODES = {
    "Standard": ["free_wifi", "ac", "led_tv", "mini_fridge", "tea_coffee", "work_desk"],
    "Deluxe": ["free_wifi", "ac", "smart_tv", "mini_bar", "bathtub", "room_service", "balcony"],
    "Suite": [
        "free_wifi",
        "smart_tv",
        "ac",
        "mini_bar",
        "jacuzzi",
        "living_area",
        "kitchenette",
        "butler",
    ],
}
ROOM_TYPE_CATALOG = {
    "Standard": {
        "description": "Comfortable city-view room with essentials for a restful stay.",
        "amenities": "Free WiFi, AC, LED TV, Mini fridge, Tea/coffee maker, Work desk",
        "bed_type": "1 Queen Bed",
        "room_size_sqft": 220,
        "image_url": "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80",
        "gallery_urls": [
            "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80",
        ],
    },
    "Deluxe": {
        "description": "Spacious deluxe room with balcony seating and upgraded bathroom.",
        "amenities": "Free WiFi, AC, Smart TV, Mini bar, Bathtub, Room service, Balcony",
        "bed_type": "1 King Bed",
        "room_size_sqft": 320,
        "image_url": "https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80",
        "gallery_urls": [
            "https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=1200&q=80",
        ],
    },
    "Suite": {
        "description": "Premium suite with separate living area, jacuzzi, and lounge seating.",
        "amenities": "Free WiFi, Smart TV, AC, Mini bar, Jacuzzi, Living area, Kitchenette, Butler service",
        "bed_type": "1 King + Sofa Bed",
        "room_size_sqft": 520,
        "image_url": "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
        "gallery_urls": [
            "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
            "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?auto=format&fit=crop&w=1200&q=80",
        ],
    },
}


def _link_room_types_to_amenities(db: Session, tenant_id: int) -> None:
    amenities = {
        row.code: row
        for row in db.query(Amenity)
        .filter(Amenity.tenant_id == tenant_id, Amenity.is_active.is_(True))
        .all()
    }
    if not amenities:
        return
    room_types = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .all()
    )
    for room_type in room_types:
        codes = ROOM_TYPE_AMENITY_CODES.get(room_type.name)
        if not codes:
            continue
        ids = [amenities[code].id for code in codes if code in amenities]
        if ids:
            sync_room_type_amenities(db, room_type, ids)
    db.flush()


def _enrich_room_type_catalog(db: Session, tenant_id: int) -> None:
    """Backfill images/amenities on existing demo room types."""
    rows = (
        db.query(RoomType)
        .filter(RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .all()
    )
    for row in rows:
        catalog = ROOM_TYPE_CATALOG.get(row.name)
        if catalog is None:
            continue
        if not row.image_url:
            row.image_url = catalog["image_url"]
        if not row.gallery_urls:
            row.gallery_urls = json.dumps(catalog["gallery_urls"])
        if not row.description:
            row.description = catalog["description"]
        if not row.bed_type:
            row.bed_type = catalog["bed_type"]
        if not row.room_size_sqft:
            row.room_size_sqft = catalog["room_size_sqft"]
        if not row.amenities or "Free WiFi" not in (row.amenities or ""):
            row.amenities = catalog["amenities"]
    db.flush()


def seed_housekeeping(db: Session, ctx: SeedContext) -> None:
    tenant, brand = ctx.tenant, ctx.brand
    admin = ctx.users.get(SUPER_ADMIN_EMAIL)
    housekeeper = ctx.users.get("housekeeper@restrochain.test")
    if admin is None:
        return

    _enrich_room_type_catalog(db, tenant.id)
    service.seed_default_amenities(db, tenant.id, brand.id)
    _link_room_types_to_amenities(db, tenant.id)
    # Resolve by outlet_name — ctx.outlets keys can drift when DB rows predate OUTLET_SPECS order.
    andheri = (
        db.query(Outlet)
        .filter(Outlet.tenant_id == tenant.id, Outlet.outlet_name == "Andheri West")
        .first()
    ) or ctx.outlets.get("Andheri West")
    bandra = (
        db.query(Outlet)
        .filter(Outlet.tenant_id == tenant.id, Outlet.outlet_name == "Bandra")
        .first()
    ) or ctx.outlets.get("Bandra")

    rooms: dict[str, HotelRoom] = {}
    if andheri is not None:
        existing_rooms = (
            db.query(HotelRoom)
            .filter(HotelRoom.tenant_id == tenant.id)
            .all()
        )
        rooms = {r.room_number: r for r in existing_rooms}

        if not rooms:
            room_types: dict[str, RoomType] = {}
            for name, rate, occ, amenities, description, bed, size, image, gallery in [
                (
                    "Standard",
                    3500,
                    2,
                    "Free WiFi, AC, LED TV, Mini fridge, Tea/coffee maker, Work desk",
                    "Comfortable city-view room with essentials for a restful stay.",
                    "1 Queen Bed",
                    220,
                    "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80",
                    [
                        "https://images.unsplash.com/photo-1631049307264-da0ec9d70304?auto=format&fit=crop&w=1200&q=80",
                        "https://images.unsplash.com/photo-1590490360182-c33d57733427?auto=format&fit=crop&w=1200&q=80",
                    ],
                ),
                (
                    "Deluxe",
                    5500,
                    3,
                    "Free WiFi, AC, Smart TV, Mini bar, Bathtub, Room service, Balcony",
                    "Spacious deluxe room with balcony seating and upgraded bathroom.",
                    "1 King Bed",
                    320,
                    "https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80",
                    [
                        "https://images.unsplash.com/photo-1611892440504-42a792e24d32?auto=format&fit=crop&w=1200&q=80",
                        "https://images.unsplash.com/photo-1566665797739-1674de7a421a?auto=format&fit=crop&w=1200&q=80",
                    ],
                ),
                (
                    "Suite",
                    9500,
                    4,
                    "Free WiFi, Smart TV, AC, Mini bar, Jacuzzi, Living area, Kitchenette, Butler service",
                    "Premium suite with separate living area, jacuzzi, and lounge seating.",
                    "1 King + Sofa Bed",
                    520,
                    "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
                    [
                        "https://images.unsplash.com/photo-1582719478250-c89cae4dc85b?auto=format&fit=crop&w=1200&q=80",
                        "https://images.unsplash.com/photo-1578683010236-d716f9a3f461?auto=format&fit=crop&w=1200&q=80",
                    ],
                ),
            ]:
                rt = RoomType(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    name=name,
                    description=description,
                    base_rate=rate,
                    max_occupancy=occ,
                    amenities=amenities,
                    bed_type=bed,
                    room_size_sqft=size,
                    image_url=image,
                    gallery_urls=json.dumps(gallery),
                )
                db.add(rt)
                db.flush()
                room_types[name] = rt

            seed_default_templates(db, tenant.id, brand.id)

            room_specs = [
                ("101", "1", "Standard", RoomStatus.VACANT_CLEAN),
                ("102", "1", "Standard", RoomStatus.OCCUPIED),
                ("103", "1", "Deluxe", RoomStatus.CHECKOUT_PENDING),
                ("104", "1", "Deluxe", RoomStatus.VACANT_DIRTY),
                ("105", "1", "Standard", RoomStatus.INSPECTING),
                ("201", "2", "Deluxe", RoomStatus.OCCUPIED),
                ("202", "2", "Suite", RoomStatus.VACANT_CLEAN),
                ("203", "2", "Standard", RoomStatus.MAINTENANCE),
                ("204", "2", "Standard", RoomStatus.VACANT_CLEAN),
                ("205", "2", "Deluxe", RoomStatus.OUT_OF_ORDER),
            ]

            for number, floor, type_name, status in room_specs:
                room = HotelRoom(
                    tenant_id=tenant.id,
                    brand_id=brand.id,
                    outlet_id=andheri.id,
                    room_type_id=room_types[type_name].id,
                    room_number=number,
                    floor=floor,
                    status=status,
                    guest_name="Guest" if status == RoomStatus.OCCUPIED else None,
                    checkout_date=date.today() if status == RoomStatus.CHECKOUT_PENDING else None,
                    last_cleaned_at=datetime.utcnow() - timedelta(hours=4) if status == RoomStatus.VACANT_CLEAN else None,
                )
                db.add(room)
                db.flush()
                rooms[number] = room

            for sweep_type, run_time in [("checkout", "06:00"), ("daily", "07:00")]:
                existing_sweep = (
                    db.query(HousekeepingSweepSchedule)
                    .filter(
                        HousekeepingSweepSchedule.tenant_id == tenant.id,
                        HousekeepingSweepSchedule.outlet_id == andheri.id,
                        HousekeepingSweepSchedule.sweep_type == sweep_type,
                    )
                    .first()
                )
                if existing_sweep is None:
                    db.add(
                        HousekeepingSweepSchedule(
                            tenant_id=tenant.id,
                            brand_id=brand.id,
                            outlet_id=andheri.id,
                            sweep_type=sweep_type,
                            run_time=run_time,
                            enabled=True,
                            distribute_by_floor=True,
                            use_floor_assignments=True,
                        )
                    )

            if housekeeper:
                for floor in ("1", "2"):
                    existing_fa = (
                        db.query(HousekeepingFloorAssignment)
                        .filter(
                            HousekeepingFloorAssignment.tenant_id == tenant.id,
                            HousekeepingFloorAssignment.outlet_id == andheri.id,
                            HousekeepingFloorAssignment.floor == floor,
                            HousekeepingFloorAssignment.housekeeper_id == housekeeper.id,
                        )
                        .first()
                    )
                    if existing_fa is None:
                        db.add(
                            HousekeepingFloorAssignment(
                                tenant_id=tenant.id,
                                outlet_id=andheri.id,
                                floor=floor,
                                housekeeper_id=housekeeper.id,
                            )
                        )

    # Seed a small inventory for Bandra when that outlet has no hotel rooms yet.
    if bandra is not None:
        bandra_room_count = (
            db.query(HotelRoom)
            .filter(
                HotelRoom.tenant_id == tenant.id,
                HotelRoom.outlet_id == bandra.id,
                HotelRoom.is_active.is_(True),
            )
            .count()
        )
        if bandra_room_count == 0:
            type_rows = (
                db.query(RoomType)
                .filter(RoomType.tenant_id == tenant.id, RoomType.is_active.is_(True))
                .order_by(RoomType.name)
                .all()
            )
            type_by_name = {rt.name: rt for rt in type_rows}
            bandra_specs = [
                ("B101", "1", "Standard", RoomStatus.VACANT_CLEAN),
                ("B102", "1", "Standard", RoomStatus.VACANT_CLEAN),
                ("B103", "1", "Deluxe", RoomStatus.VACANT_DIRTY),
                ("B201", "2", "Suite", RoomStatus.VACANT_CLEAN),
                ("B202", "2", "Deluxe", RoomStatus.VACANT_CLEAN),
            ]
            for number, floor, type_name, status in bandra_specs:
                room_type = type_by_name.get(type_name)
                if room_type is None and type_rows:
                    room_type = type_rows[0]
                if room_type is None:
                    continue
                db.add(
                    HotelRoom(
                        tenant_id=tenant.id,
                        brand_id=brand.id,
                        outlet_id=bandra.id,
                        room_type_id=room_type.id,
                        room_number=number,
                        floor=floor,
                        status=status,
                        last_cleaned_at=(
                            datetime.utcnow() - timedelta(hours=2)
                            if status == RoomStatus.VACANT_CLEAN
                            else None
                        ),
                    )
                )
            db.flush()

    if andheri is None:
        return

    # Always ensure ≥5 housekeeping tasks (idempotent by room + task_type)
    task_specs = [
        ("103", HousekeepingTaskType.CHECKOUT, HousekeepingTaskStatus.PENDING, MaintenancePriority.HIGH, 2),
        ("104", HousekeepingTaskType.DEEP_CLEAN, HousekeepingTaskStatus.IN_PROGRESS, MaintenancePriority.MEDIUM, 4),
        ("105", HousekeepingTaskType.INSPECTION, HousekeepingTaskStatus.PENDING, MaintenancePriority.MEDIUM, 3),
        ("201", HousekeepingTaskType.TURNDOWN, HousekeepingTaskStatus.COMPLETED, MaintenancePriority.LOW, -1),
        ("202", HousekeepingTaskType.DAILY, HousekeepingTaskStatus.PENDING, MaintenancePriority.MEDIUM, 5),
    ]

    from app.modules.housekeeping.service import _create_checklist_from_template  # noqa: PLC0415

    for room_number, task_type, task_status, priority, due_hours in task_specs:
        room = rooms.get(room_number)
        if room is None:
            continue
        existing_task = (
            db.query(HousekeepingTask)
            .filter(
                HousekeepingTask.tenant_id == tenant.id,
                HousekeepingTask.room_id == room.id,
                HousekeepingTask.task_type == task_type,
            )
            .first()
        )
        if existing_task is not None:
            continue
        task = HousekeepingTask(
            tenant_id=tenant.id,
            brand_id=brand.id,
            outlet_id=andheri.id,
            room_id=room.id,
            task_type=task_type,
            status=task_status,
            assigned_to=housekeeper.id if housekeeper else None,
            priority=priority,
            due_at=datetime.utcnow() + timedelta(hours=due_hours),
        )
        db.add(task)
        db.flush()
        if task_type == HousekeepingTaskType.CHECKOUT:
            _create_checklist_from_template(db, task, None, HousekeepingTaskType.CHECKOUT)

    # Always ensure ≥5 maintenance tickets (idempotent by ticket_number)
    ticket_specs = [
        ("MT-DEMO-001", "203", "AC not cooling properly",
         "Guest reported AC blowing warm air. Needs technician inspection.",
         MaintenanceCategory.HVAC, MaintenancePriority.HIGH, MaintenanceTicketStatus.IN_PROGRESS),
        ("MT-DEMO-002", "205", "Bathroom leak — pipe repair needed",
         "Water leaking from ceiling in bathroom. Room blocked until resolved.",
         MaintenanceCategory.PLUMBING, MaintenancePriority.URGENT, MaintenanceTicketStatus.OPEN),
        ("MT-DEMO-003", "104", "Wardrobe door hinge broken",
         "Guest reported wardrobe door not closing properly.",
         MaintenanceCategory.FURNITURE, MaintenancePriority.LOW, MaintenanceTicketStatus.OPEN),
        ("MT-DEMO-004", "201", "TV remote not working",
         "Remote control batteries dead and replacement not available.",
         MaintenanceCategory.ELECTRICAL, MaintenancePriority.MEDIUM, MaintenanceTicketStatus.RESOLVED),
        ("MT-DEMO-005", "102", "Shower drain blocked",
         "Slow drain reported by current guest. Plumber dispatched.",
         MaintenanceCategory.PLUMBING, MaintenancePriority.HIGH, MaintenanceTicketStatus.IN_PROGRESS),
    ]

    for ticket_number, room_number, title, description, category, priority, status in ticket_specs:
        existing_ticket = (
            db.query(MaintenanceTicket)
            .filter(
                MaintenanceTicket.tenant_id == tenant.id,
                MaintenanceTicket.ticket_number == ticket_number,
            )
            .first()
        )
        if existing_ticket is not None:
            continue
        room = rooms.get(room_number)
        if room is None:
            continue
        db.add(
            MaintenanceTicket(
                tenant_id=tenant.id,
                brand_id=brand.id,
                outlet_id=andheri.id,
                room_id=room.id,
                ticket_number=ticket_number,
                title=title,
                description=description,
                category=category,
                priority=priority,
                status=status,
                reported_by=admin.id,
            )
        )
