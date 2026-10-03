from __future__ import annotations

from datetime import date, datetime, timedelta

from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from app.common.pagination import paginate_query
from app.core.exceptions import ConflictError, NotFoundError
from app.modules.housekeeping.models import (
    Amenity,
    ChecklistTemplate,
    ChecklistTemplateItem,
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
    RoomTypeAmenity,
    TaskChecklistItem,
    TicketComment,
)
from app.modules.housekeeping.room_catalog import (
    dump_gallery_urls,
    serialize_amenity,
    serialize_room_type,
    sync_room_type_amenities,
)
from app.modules.housekeeping.schemas import (
    AmenityCreate,
    AmenityRead,
    AmenityUpdate,
    ChecklistTemplateCreate,
    ChecklistTemplateItemCreate,
    ChecklistTemplateRead,
    BulkRoomCreate,
    BulkRoomCreateResponse,
    BulkTaskCreate,
    BulkTaskCreateResponse,
    FloorAssignmentBulkUpsert,
    FloorAssignmentRead,
    RunDueSchedulesResponse,
    RunDueSchedulesGlobalResponse,
    SweepScheduleRead,
    SweepScheduleUpsert,
    TaskSweepCreate,
    TaskSweepResponse,
    HotelRoomCreate,
    HotelRoomRead,
    HotelRoomUpdate,
    HousekeepingDashboard,
    HousekeepingStaffRead,
    HousekeepingTaskCreate,
    HousekeepingTaskRead,
    HousekeepingTaskUpdate,
    MaintenanceTicketCreate,
    MaintenanceTicketGenerate,
    MaintenanceTicketRead,
    MaintenanceTicketUpdate,
    RoomStatusCount,
    RoomStatusUpdate,
    RoomTypeCreate,
    RoomTypeRead,
    RoomTypeUpdate,
    SetupDemoRequest,
    SetupDemoResponse,
    TaskChecklistItemRead,
    TaskChecklistItemUpdate,
    TicketCommentCreate,
    TicketCommentRead,
)
from app.modules.outlets.models import Outlet
from app.modules.roles.models import Role
from app.modules.users.models import User


DEFAULT_CHECKLIST_ITEMS: dict[HousekeepingTaskType, list[str]] = {
    HousekeepingTaskType.CHECKOUT: [
        "Strip bed linens",
        "Clean bathroom thoroughly",
        "Vacuum and mop floors",
        "Dust all surfaces",
        "Restock amenities",
        "Check minibar",
        "Inspect for damage",
    ],
    HousekeepingTaskType.DAILY: [
        "Make bed",
        "Clean bathroom",
        "Empty trash",
        "Replenish towels",
        "Dust surfaces",
    ],
    HousekeepingTaskType.DEEP_CLEAN: [
        "Move furniture and clean underneath",
        "Deep clean bathroom grout",
        "Wash windows",
        "Clean air vents",
        "Shampoo carpets",
        "Sanitize all touchpoints",
    ],
    HousekeepingTaskType.TURNDOWN: [
        "Turn down bed",
        "Place slippers",
        "Refresh water",
        "Close curtains",
        "Dim lighting",
    ],
    HousekeepingTaskType.INSPECTION: [
        "Check room cleanliness",
        "Verify amenities stocked",
        "Test all appliances",
        "Check for maintenance issues",
        "Sign off inspection",
    ],
    HousekeepingTaskType.GUEST_REQUEST: [
        "Fulfill guest request",
        "Confirm with guest if needed",
        "Update front desk when done",
    ],
}


def _get_outlet(db: Session, tenant_id: int, outlet_id: int) -> Outlet:
    outlet = db.query(Outlet).filter(Outlet.id == outlet_id, Outlet.tenant_id == tenant_id).first()
    if not outlet:
        raise NotFoundError("Outlet not found")
    return outlet


def _get_room(db: Session, tenant_id: int, room_id: int) -> HotelRoom:
    room = (
        db.query(HotelRoom)
        .options(joinedload(HotelRoom.room_type))
        .filter(HotelRoom.id == room_id, HotelRoom.tenant_id == tenant_id)
        .first()
    )
    if not room:
        raise NotFoundError("Room not found")
    return room


def _room_to_read(db: Session, room: HotelRoom) -> HotelRoomRead:
    active_task = (
        db.query(HousekeepingTask.id)
        .filter(
            HousekeepingTask.room_id == room.id,
            HousekeepingTask.status.in_([
                HousekeepingTaskStatus.PENDING,
                HousekeepingTaskStatus.IN_PROGRESS,
            ]),
        )
        .first()
    )
    open_tickets = (
        db.query(func.count(MaintenanceTicket.id))
        .filter(
            MaintenanceTicket.room_id == room.id,
            MaintenanceTicket.status.notin_([
                MaintenanceTicketStatus.RESOLVED,
                MaintenanceTicketStatus.CLOSED,
            ]),
        )
        .scalar()
        or 0
    )
    return HotelRoomRead(
        id=room.id,
        outlet_id=room.outlet_id,
        room_type_id=room.room_type_id,
        room_type_name=room.room_type.name if room.room_type else None,
        room_number=room.room_number,
        floor=room.floor,
        wing=room.wing,
        status=room.status,
        guest_name=room.guest_name,
        checkout_date=room.checkout_date,
        notes=room.notes,
        last_cleaned_at=room.last_cleaned_at,
        assigned_housekeeper_id=room.assigned_housekeeper_id,
        active_task_id=active_task[0] if active_task else None,
        open_ticket_count=open_tickets,
        created_at=room.created_at,
        updated_at=room.updated_at,
    )


def _task_progress(items: list[TaskChecklistItem]) -> int:
    if not items:
        return 0
    checked = sum(1 for i in items if i.is_checked)
    return round(checked / len(items) * 100)


def _task_to_read(task: HousekeepingTask, room_number: str | None = None) -> HousekeepingTaskRead:
    items = [_checklist_item_to_read(i) for i in task.checklist_items]
    return HousekeepingTaskRead(
        id=task.id,
        outlet_id=task.outlet_id,
        room_id=task.room_id,
        room_number=room_number,
        template_id=task.template_id,
        task_type=task.task_type,
        status=task.status,
        assigned_to=task.assigned_to,
        priority=task.priority,
        due_at=task.due_at,
        started_at=task.started_at,
        completed_at=task.completed_at,
        verified_by=task.verified_by,
        notes=task.notes,
        checklist_items=items,
        progress_percent=_task_progress(task.checklist_items),
        created_at=task.created_at,
        updated_at=task.updated_at,
    )


def _checklist_item_to_read(item: TaskChecklistItem) -> TaskChecklistItemRead:
    return TaskChecklistItemRead(
        id=item.id,
        label=item.label,
        sort_order=item.sort_order,
        is_required=item.is_required,
        is_checked=item.is_checked,
        checked_at=item.checked_at,
        checked_by=item.checked_by,
        notes=item.notes,
        created_at=item.created_at,
        updated_at=item.updated_at,
    )


def _ticket_to_read(ticket: MaintenanceTicket, room_number: str | None = None) -> MaintenanceTicketRead:
    return MaintenanceTicketRead(
        id=ticket.id,
        outlet_id=ticket.outlet_id,
        room_id=ticket.room_id,
        room_number=room_number,
        ticket_number=ticket.ticket_number,
        title=ticket.title,
        description=ticket.description,
        category=ticket.category,
        priority=ticket.priority,
        status=ticket.status,
        reported_by=ticket.reported_by,
        assigned_to=ticket.assigned_to,
        due_date=ticket.due_date,
        resolved_at=ticket.resolved_at,
        resolution_notes=ticket.resolution_notes,
        comments=[TicketCommentRead.model_validate(c) for c in ticket.comments],
        created_at=ticket.created_at,
        updated_at=ticket.updated_at,
    )


def _generate_ticket_number(db: Session, tenant_id: int) -> str:
    today = date.today().strftime("%Y%m%d")
    prefix = f"MT-{today}-"
    count = (
        db.query(func.count(MaintenanceTicket.id))
        .filter(
            MaintenanceTicket.tenant_id == tenant_id,
            MaintenanceTicket.ticket_number.like(f"{prefix}%"),
        )
        .scalar()
        or 0
    )
    return f"{prefix}{count + 1:03d}"


def _create_checklist_from_template(
    db: Session,
    task: HousekeepingTask,
    template_id: int | None,
    task_type: HousekeepingTaskType,
) -> None:
    if template_id:
        template = (
            db.query(ChecklistTemplate)
            .options(joinedload(ChecklistTemplate.items))
            .filter(ChecklistTemplate.id == template_id)
            .first()
        )
        if template:
            for item in template.items:
                db.add(
                    TaskChecklistItem(
                        task_id=task.id,
                        label=item.label,
                        sort_order=item.sort_order,
                        is_required=item.is_required,
                    )
                )
            return

    labels = DEFAULT_CHECKLIST_ITEMS.get(task_type, DEFAULT_CHECKLIST_ITEMS[HousekeepingTaskType.DAILY])
    for idx, label in enumerate(labels):
        db.add(
            TaskChecklistItem(
                task_id=task.id,
                label=label,
                sort_order=idx,
                is_required=True,
            )
        )


# ── Dashboard ───────────────────────────────────────────────────────────────

def get_dashboard(db: Session, tenant_id: int, outlet_id: int | None = None) -> HousekeepingDashboard:
    q = db.query(HotelRoom).filter(HotelRoom.tenant_id == tenant_id, HotelRoom.is_active.is_(True))
    if outlet_id:
        q = q.filter(HotelRoom.outlet_id == outlet_id)
    rooms = q.all()
    total = len(rooms)

    status_counts: dict[RoomStatus, int] = {s: 0 for s in RoomStatus}
    floors: set[str] = set()
    for room in rooms:
        status_counts[room.status] = status_counts.get(room.status, 0) + 1
        floors.add(room.floor)

    occupied = status_counts.get(RoomStatus.OCCUPIED, 0) + status_counts.get(RoomStatus.CHECKOUT_PENDING, 0)
    occupancy_rate = round(occupied / total * 100, 1) if total else 0.0

    task_q = db.query(HousekeepingTask).filter(HousekeepingTask.tenant_id == tenant_id)
    if outlet_id:
        task_q = task_q.filter(HousekeepingTask.outlet_id == outlet_id)

    pending = task_q.filter(HousekeepingTask.status == HousekeepingTaskStatus.PENDING).count()
    in_progress = task_q.filter(HousekeepingTask.status == HousekeepingTaskStatus.IN_PROGRESS).count()

    today_start = datetime.combine(date.today(), datetime.min.time())
    completed_today = task_q.filter(
        HousekeepingTask.status.in_([HousekeepingTaskStatus.COMPLETED, HousekeepingTaskStatus.VERIFIED]),
        HousekeepingTask.completed_at >= today_start,
    ).count()
    awaiting_inspection = task_q.filter(
        HousekeepingTask.status == HousekeepingTaskStatus.COMPLETED
    ).count() + status_counts.get(RoomStatus.INSPECTING, 0)

    ticket_q = db.query(MaintenanceTicket).filter(MaintenanceTicket.tenant_id == tenant_id)
    if outlet_id:
        ticket_q = ticket_q.filter(MaintenanceTicket.outlet_id == outlet_id)
    open_tickets = ticket_q.filter(
        MaintenanceTicket.status.notin_([MaintenanceTicketStatus.RESOLVED, MaintenanceTicketStatus.CLOSED])
    ).count()
    urgent_tickets = ticket_q.filter(
        MaintenanceTicket.priority == MaintenancePriority.URGENT,
        MaintenanceTicket.status.notin_([MaintenanceTicketStatus.RESOLVED, MaintenanceTicketStatus.CLOSED]),
    ).count()

    needs_cleaning = status_counts.get(RoomStatus.VACANT_DIRTY, 0) + status_counts.get(
        RoomStatus.CHECKOUT_PENDING, 0
    )

    return HousekeepingDashboard(
        total_rooms=total,
        status_breakdown=[RoomStatusCount(status=s, count=c) for s, c in status_counts.items() if c > 0],
        pending_tasks=pending,
        in_progress_tasks=in_progress,
        completed_tasks_today=completed_today,
        awaiting_inspection=awaiting_inspection,
        open_tickets=open_tickets,
        urgent_tickets=urgent_tickets,
        rooms_needing_cleaning=needs_cleaning,
        occupancy_rate=occupancy_rate,
        floors=sorted(floors),
    )


def list_housekeeping_staff(db: Session, tenant_id: int) -> list[HousekeepingStaffRead]:
    rows = (
        db.query(User, Role.name)
        .outerjoin(Role, Role.id == User.role_id)
        .filter(User.tenant_id == tenant_id, User.is_active.is_(True))
        .order_by(User.full_name)
        .all()
    )
    return [
        HousekeepingStaffRead(
            id=user.id,
            full_name=user.full_name,
            email=user.email,
            role_name=role_name,
        )
        for user, role_name in rows
    ]


# ── Room Types ──────────────────────────────────────────────────────────────

def list_room_types(db: Session, tenant_id: int) -> list[RoomTypeRead]:
    rows = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .order_by(RoomType.name)
        .all()
    )
    return [serialize_room_type(r, db) for r in rows]


def create_room_type(
    db: Session, tenant_id: int, data: RoomTypeCreate, default_brand_id: int | None = None
) -> RoomTypeRead:
    payload = data.model_dump()
    amenity_ids = payload.pop("amenity_ids", []) or []
    gallery = payload.pop("gallery_urls", []) or []
    record = RoomType(
        tenant_id=tenant_id,
        brand_id=payload.pop("brand_id", None) or default_brand_id,
        name=payload["name"],
        description=payload.get("description"),
        base_rate=payload.get("base_rate", 0),
        max_occupancy=payload.get("max_occupancy", 2),
        amenities=payload.get("amenities"),
        image_url=payload.get("image_url"),
        gallery_urls=dump_gallery_urls(gallery),
        bed_type=payload.get("bed_type"),
        room_size_sqft=payload.get("room_size_sqft"),
    )
    db.add(record)
    db.flush()
    if amenity_ids:
        sync_room_type_amenities(db, record, amenity_ids)
    db.commit()
    db.refresh(record)
    record = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.id == record.id)
        .first()
    )
    return serialize_room_type(record, db)


def update_room_type(db: Session, tenant_id: int, type_id: int, data: RoomTypeUpdate) -> RoomTypeRead:
    record = db.query(RoomType).filter(RoomType.id == type_id, RoomType.tenant_id == tenant_id).first()
    if not record:
        raise NotFoundError("Room type not found")
    payload = data.model_dump(exclude_unset=True)
    amenity_ids = payload.pop("amenity_ids", None)
    if "gallery_urls" in payload:
        payload["gallery_urls"] = dump_gallery_urls(payload["gallery_urls"])
    for field, value in payload.items():
        setattr(record, field, value)
    if amenity_ids is not None:
        sync_room_type_amenities(db, record, amenity_ids)
    db.commit()
    record = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.id == type_id)
        .first()
    )
    return serialize_room_type(record, db)


def _slugify_amenity_code(name: str) -> str:
    import re

    slug = re.sub(r"[^a-z0-9]+", "_", name.strip().lower()).strip("_")
    return (slug or "amenity")[:64]


def list_amenities(
    db: Session,
    tenant_id: int,
    *,
    include_inactive: bool = False,
    category: str | None = None,
) -> list[AmenityRead]:
    q = db.query(Amenity).filter(Amenity.tenant_id == tenant_id)
    if not include_inactive:
        q = q.filter(Amenity.is_active.is_(True))
    if category:
        q = q.filter(Amenity.category == category)
    rows = q.order_by(Amenity.sort_order, Amenity.name).all()
    counts = dict(
        db.query(RoomTypeAmenity.amenity_id, func.count(RoomTypeAmenity.id))
        .join(RoomType, RoomType.id == RoomTypeAmenity.room_type_id)
        .filter(RoomType.tenant_id == tenant_id, RoomTypeAmenity.is_active.is_(True))
        .group_by(RoomTypeAmenity.amenity_id)
        .all()
    )
    return [serialize_amenity(row, room_type_count=int(counts.get(row.id, 0))) for row in rows]


def create_amenity(
    db: Session,
    tenant_id: int,
    data: AmenityCreate,
    default_brand_id: int | None = None,
) -> AmenityRead:
    code = (data.code or _slugify_amenity_code(data.name)).strip().lower()
    existing = (
        db.query(Amenity)
        .filter(Amenity.tenant_id == tenant_id, Amenity.code == code)
        .first()
    )
    if existing is not None:
        raise ConflictError(f"Amenity code '{code}' already exists")
    record = Amenity(
        tenant_id=tenant_id,
        brand_id=data.brand_id or default_brand_id,
        name=data.name.strip(),
        code=code,
        category=data.category,
        icon=data.icon,
        description=data.description,
        sort_order=data.sort_order,
        is_active=data.is_active,
    )
    db.add(record)
    db.commit()
    db.refresh(record)
    return serialize_amenity(record)


def update_amenity(db: Session, tenant_id: int, amenity_id: int, data: AmenityUpdate) -> AmenityRead:
    record = (
        db.query(Amenity)
        .filter(Amenity.id == amenity_id, Amenity.tenant_id == tenant_id)
        .first()
    )
    if record is None:
        raise NotFoundError("Amenity not found")
    payload = data.model_dump(exclude_unset=True)
    if "code" in payload and payload["code"]:
        payload["code"] = str(payload["code"]).strip().lower()
        clash = (
            db.query(Amenity)
            .filter(
                Amenity.tenant_id == tenant_id,
                Amenity.code == payload["code"],
                Amenity.id != amenity_id,
            )
            .first()
        )
        if clash is not None:
            raise ConflictError(f"Amenity code '{payload['code']}' already exists")
    if "name" in payload and payload["name"]:
        payload["name"] = str(payload["name"]).strip()
    for field, value in payload.items():
        setattr(record, field, value)
    db.commit()
    db.refresh(record)
    count = (
        db.query(func.count(RoomTypeAmenity.id))
        .filter(RoomTypeAmenity.amenity_id == record.id, RoomTypeAmenity.is_active.is_(True))
        .scalar()
    )
    return serialize_amenity(record, room_type_count=int(count or 0))


def set_room_type_amenities(
    db: Session,
    tenant_id: int,
    type_id: int,
    amenity_ids: list[int],
) -> RoomTypeRead:
    record = (
        db.query(RoomType)
        .filter(RoomType.id == type_id, RoomType.tenant_id == tenant_id)
        .first()
    )
    if record is None:
        raise NotFoundError("Room type not found")
    sync_room_type_amenities(db, record, amenity_ids)
    db.commit()
    record = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.id == type_id)
        .first()
    )
    return serialize_room_type(record, db)


def bulk_assign_amenity_to_room_types(
    db: Session,
    tenant_id: int,
    amenity_id: int,
    room_type_ids: list[int],
) -> tuple[int, list[RoomTypeRead]]:
    amenity = (
        db.query(Amenity)
        .filter(Amenity.id == amenity_id, Amenity.tenant_id == tenant_id, Amenity.is_active.is_(True))
        .first()
    )
    if amenity is None:
        raise NotFoundError("Amenity not found")

    selected = set(int(item) for item in room_type_ids if item)
    records = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.tenant_id == tenant_id, RoomType.is_active.is_(True))
        .all()
    )
    updated: list[RoomTypeRead] = []
    for record in records:
        current_ids = [link.amenity_id for link in (record.amenity_links or []) if link.is_active]
        has_amenity = amenity_id in current_ids
        should_have = record.id in selected
        if should_have and not has_amenity:
            current_ids.append(amenity_id)
        elif not should_have and has_amenity:
            current_ids = [item for item in current_ids if item != amenity_id]
        else:
            continue
        sync_room_type_amenities(db, record, current_ids)
        updated.append(serialize_room_type(record, db))
    db.commit()
    return len(updated), updated


def attach_room_type_image(
    db: Session,
    tenant_id: int,
    type_id: int,
    image_url: str,
    *,
    as_cover: bool = True,
) -> RoomTypeRead:
    from app.modules.housekeeping.room_catalog import dump_gallery_urls, parse_gallery_urls

    record = (
        db.query(RoomType)
        .filter(RoomType.id == type_id, RoomType.tenant_id == tenant_id)
        .first()
    )
    if record is None:
        raise NotFoundError("Room type not found")

    gallery = parse_gallery_urls(record.gallery_urls)
    if image_url not in gallery:
        gallery.insert(0 if as_cover else len(gallery), image_url)
    if as_cover or not record.image_url:
        record.image_url = image_url
    record.gallery_urls = dump_gallery_urls(gallery)
    db.commit()
    record = (
        db.query(RoomType)
        .options(joinedload(RoomType.amenity_links).joinedload(RoomTypeAmenity.amenity))
        .filter(RoomType.id == type_id)
        .first()
    )
    return serialize_room_type(record, db)


def seed_default_amenities(db: Session, tenant_id: int, brand_id: int | None = None) -> list[AmenityRead]:
    specs = [
        ("Free WiFi", "free_wifi", "connectivity", "wifi", 10),
        ("AC", "ac", "comfort", "wind", 20),
        ("LED TV", "led_tv", "entertainment", "tv", 30),
        ("Smart TV", "smart_tv", "entertainment", "tv", 40),
        ("Mini bar", "mini_bar", "food_drink", "wine", 50),
        ("Mini fridge", "mini_fridge", "food_drink", "refrigerator", 60),
        ("Tea/coffee maker", "tea_coffee", "food_drink", "coffee", 70),
        ("Bathtub", "bathtub", "bathroom", "bath", 80),
        ("Jacuzzi", "jacuzzi", "bathroom", "bath", 90),
        ("Hair dryer", "hair_dryer", "bathroom", "wind", 100),
        ("Work desk", "work_desk", "comfort", "desk", 110),
        ("Balcony", "balcony", "view", "sun", 120),
        ("Living area", "living_area", "comfort", "sofa", 130),
        ("Kitchenette", "kitchenette", "food_drink", "utensils", 140),
        ("Butler service", "butler", "other", "bell", 150),
        ("Safe", "safe", "safety", "shield", 160),
        ("Room service", "room_service", "food_drink", "concierge", 170),
    ]
    from app.modules.housekeeping.models import AmenityCategory

    created: list[Amenity] = []
    for name, code, category, icon, sort_order in specs:
        existing = (
            db.query(Amenity)
            .filter(Amenity.tenant_id == tenant_id, Amenity.code == code)
            .first()
        )
        if existing is not None:
            created.append(existing)
            continue
        row = Amenity(
            tenant_id=tenant_id,
            brand_id=brand_id,
            name=name,
            code=code,
            category=AmenityCategory(category),
            icon=icon,
            sort_order=sort_order,
            is_active=True,
        )
        db.add(row)
        created.append(row)
    db.flush()
    return [serialize_amenity(row) for row in created]


# ── Rooms ─────────────────────────────────────────────────────────────────────

def list_rooms(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    floor: str | None = None,
    wing: str | None = None,
    status: RoomStatus | None = None,
) -> tuple[list[HotelRoomRead], int]:
    q = (
        db.query(HotelRoom)
        .options(joinedload(HotelRoom.room_type))
        .filter(HotelRoom.tenant_id == tenant_id, HotelRoom.is_active.is_(True))
    )
    if outlet_id:
        q = q.filter(HotelRoom.outlet_id == outlet_id)
    if floor:
        q = q.filter(HotelRoom.floor == floor)
    if wing:
        q = q.filter(HotelRoom.wing == wing)
    if status:
        q = q.filter(HotelRoom.status == status)
    q = q.order_by(HotelRoom.wing, HotelRoom.floor, HotelRoom.room_number)
    rows, total = paginate_query(q, page, page_size)
    return [_room_to_read(db, r) for r in rows], total


def get_room(db: Session, tenant_id: int, room_id: int) -> HotelRoomRead:
    room = _get_room(db, tenant_id, room_id)
    return _room_to_read(db, room)


def create_room(
    db: Session, tenant_id: int, data: HotelRoomCreate, default_brand_id: int | None = None
) -> HotelRoomRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    existing = (
        db.query(HotelRoom)
        .filter(
            HotelRoom.tenant_id == tenant_id,
            HotelRoom.outlet_id == data.outlet_id,
            HotelRoom.room_number == data.room_number,
        )
        .first()
    )
    if existing:
        raise ConflictError(f"Room {data.room_number} already exists at this outlet")

    room = HotelRoom(
        tenant_id=tenant_id,
        brand_id=data.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        room_type_id=data.room_type_id,
        room_number=data.room_number,
        floor=data.floor,
        wing=data.wing,
        status=data.status,
        guest_name=data.guest_name,
        checkout_date=data.checkout_date,
        notes=data.notes,
        assigned_housekeeper_id=data.assigned_housekeeper_id,
    )
    db.add(room)
    db.commit()
    db.refresh(room)
    return _room_to_read(db, room)


def bulk_create_rooms(
    db: Session, tenant_id: int, data: BulkRoomCreate, default_brand_id: int | None = None
) -> BulkRoomCreateResponse:
    _get_outlet(db, tenant_id, data.outlet_id)
    created: list[HotelRoomRead] = []

    for num in range(data.start_number, data.end_number + 1):
        room_number = f"{data.prefix}{num}"
        existing = (
            db.query(HotelRoom)
            .filter(
                HotelRoom.tenant_id == tenant_id,
                HotelRoom.outlet_id == data.outlet_id,
                HotelRoom.room_number == room_number,
            )
            .first()
        )
        if existing:
            continue

        room = HotelRoom(
            tenant_id=tenant_id,
            brand_id=data.brand_id or default_brand_id,
            outlet_id=data.outlet_id,
            room_type_id=data.room_type_id,
            room_number=room_number,
            floor=data.floor,
            wing=data.wing,
            status=data.status,
        )
        db.add(room)
        db.flush()
        created.append(_room_to_read(db, room))

    if not created:
        raise ConflictError("No new rooms created — all room numbers already exist")

    db.commit()
    return BulkRoomCreateResponse(
        message=f"Created {len(created)} room(s)",
        rooms_created=len(created),
        rooms=created,
    )


def update_room(db: Session, tenant_id: int, room_id: int, data: HotelRoomUpdate) -> HotelRoomRead:
    room = _get_room(db, tenant_id, room_id)
    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(room, field, value)
    db.commit()
    db.refresh(room)
    return _room_to_read(db, room)


def update_room_status(
    db: Session, tenant_id: int, room_id: int, data: RoomStatusUpdate
) -> HotelRoomRead:
    room = _get_room(db, tenant_id, room_id)
    room.status = data.status
    if data.guest_name is not None:
        room.guest_name = data.guest_name
    if data.checkout_date is not None:
        room.checkout_date = data.checkout_date
    if data.notes is not None:
        room.notes = data.notes

    if data.status == RoomStatus.CHECKOUT_PENDING:
        _auto_create_task(db, tenant_id, room, HousekeepingTaskType.CHECKOUT)
    elif data.status == RoomStatus.VACANT_CLEAN:
        room.last_cleaned_at = datetime.utcnow()
        room.guest_name = None
        room.checkout_date = None

    db.commit()
    db.refresh(room)
    return _room_to_read(db, room)


def _auto_create_task(
    db: Session, tenant_id: int, room: HotelRoom, task_type: HousekeepingTaskType
) -> HousekeepingTask:
    existing = (
        db.query(HousekeepingTask)
        .filter(
            HousekeepingTask.room_id == room.id,
            HousekeepingTask.task_type == task_type,
            HousekeepingTask.status.in_([
                HousekeepingTaskStatus.PENDING,
                HousekeepingTaskStatus.IN_PROGRESS,
            ]),
        )
        .first()
    )
    if existing:
        return existing

    task = HousekeepingTask(
        tenant_id=tenant_id,
        brand_id=room.brand_id,
        outlet_id=room.outlet_id,
        room_id=room.id,
        task_type=task_type,
        status=HousekeepingTaskStatus.PENDING,
        assigned_to=room.assigned_housekeeper_id,
        priority=MaintenancePriority.HIGH if task_type == HousekeepingTaskType.CHECKOUT else MaintenancePriority.MEDIUM,
        due_at=datetime.utcnow() + timedelta(hours=2),
    )
    db.add(task)
    db.flush()
    _create_checklist_from_template(db, task, None, task_type)
    return task


def ensure_room_task(
    db: Session,
    tenant_id: int,
    room: HotelRoom,
    task_type: HousekeepingTaskType,
    *,
    notes: str | None = None,
) -> bool:
    """Create a pending task if none is active. Returns True when a new task was created."""
    existing = (
        db.query(HousekeepingTask)
        .filter(
            HousekeepingTask.room_id == room.id,
            HousekeepingTask.task_type == task_type,
            HousekeepingTask.status.in_(
                [
                    HousekeepingTaskStatus.PENDING,
                    HousekeepingTaskStatus.IN_PROGRESS,
                ]
            ),
        )
        .first()
    )
    if existing:
        return False
    task = _auto_create_task(db, tenant_id, room, task_type)
    if notes:
        task.notes = notes
    return True


def skip_open_room_tasks(
    db: Session,
    room_id: int,
    task_types: list[HousekeepingTaskType],
    *,
    reason: str | None = None,
) -> int:
    """Mark open tasks of the given types as skipped. Returns count skipped."""
    rows = (
        db.query(HousekeepingTask)
        .filter(
            HousekeepingTask.room_id == room_id,
            HousekeepingTask.task_type.in_(task_types),
            HousekeepingTask.status.in_(
                [
                    HousekeepingTaskStatus.PENDING,
                    HousekeepingTaskStatus.IN_PROGRESS,
                ]
            ),
        )
        .all()
    )
    for task in rows:
        task.status = HousekeepingTaskStatus.SKIPPED
        if reason:
            task.notes = ((task.notes or "") + f"\n{reason}").strip()
    return len(rows)


def delete_room(db: Session, tenant_id: int, room_id: int) -> None:
    room = _get_room(db, tenant_id, room_id)
    room.is_active = False
    db.commit()


# ── Checklist Templates ───────────────────────────────────────────────────────

def list_checklist_templates(db: Session, tenant_id: int) -> list[ChecklistTemplateRead]:
    rows = (
        db.query(ChecklistTemplate)
        .options(joinedload(ChecklistTemplate.items))
        .filter(ChecklistTemplate.tenant_id == tenant_id, ChecklistTemplate.is_active.is_(True))
        .all()
    )
    return [ChecklistTemplateRead.model_validate(r) for r in rows]


def create_checklist_template(
    db: Session, tenant_id: int, data: ChecklistTemplateCreate, default_brand_id: int | None = None
) -> ChecklistTemplateRead:
    template = ChecklistTemplate(
        tenant_id=tenant_id,
        brand_id=data.brand_id or default_brand_id,
        name=data.name,
        task_type=data.task_type,
        description=data.description,
        is_default=data.is_default,
    )
    db.add(template)
    db.flush()
    for item in data.items:
        db.add(
            ChecklistTemplateItem(
                template_id=template.id,
                label=item.label,
                sort_order=item.sort_order,
                is_required=item.is_required,
            )
        )
    db.commit()
    db.refresh(template)
    return ChecklistTemplateRead.model_validate(template)


def seed_default_templates(db: Session, tenant_id: int, brand_id: int | None = None) -> list[ChecklistTemplateRead]:
    existing = db.query(ChecklistTemplate).filter(ChecklistTemplate.tenant_id == tenant_id).count()
    if existing:
        return list_checklist_templates(db, tenant_id)

    created = []
    for task_type, labels in DEFAULT_CHECKLIST_ITEMS.items():
        items = [ChecklistTemplateItemCreate(label=l, sort_order=i) for i, l in enumerate(labels)]
        tpl = create_checklist_template(
            db,
            tenant_id,
            ChecklistTemplateCreate(
                name=f"Default {task_type.value.replace('_', ' ').title()}",
                task_type=task_type,
                is_default=True,
                brand_id=brand_id,
                items=items,
            ),
            brand_id,
        )
        created.append(tpl)
    return created


# ── Housekeeping Tasks ────────────────────────────────────────────────────────

def list_tasks(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    status: HousekeepingTaskStatus | None = None,
    assigned_to: int | None = None,
) -> tuple[list[HousekeepingTaskRead], int]:
    q = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.tenant_id == tenant_id, HousekeepingTask.is_active.is_(True))
    )
    if outlet_id:
        q = q.filter(HousekeepingTask.outlet_id == outlet_id)
    if status:
        q = q.filter(HousekeepingTask.status == status)
    if assigned_to:
        q = q.filter(HousekeepingTask.assigned_to == assigned_to)
    q = q.order_by(HousekeepingTask.created_at.desc())
    rows, total = paginate_query(q, page, page_size)
    return [_task_to_read(t, t.room.room_number if t.room else None) for t in rows], total


def get_task(db: Session, tenant_id: int, task_id: int) -> HousekeepingTaskRead:
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task_id, HousekeepingTask.tenant_id == tenant_id)
        .first()
    )
    if not task:
        raise NotFoundError("Task not found")
    return _task_to_read(task, task.room.room_number if task.room else None)


def create_task(
    db: Session, tenant_id: int, data: HousekeepingTaskCreate, default_brand_id: int | None = None
) -> HousekeepingTaskRead:
    room = _get_room(db, tenant_id, data.room_id)
    if room.outlet_id != data.outlet_id:
        raise ConflictError("Room does not belong to this outlet")

    task = HousekeepingTask(
        tenant_id=tenant_id,
        brand_id=data.brand_id or room.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        room_id=data.room_id,
        template_id=data.template_id,
        task_type=data.task_type,
        status=HousekeepingTaskStatus.PENDING,
        assigned_to=data.assigned_to or room.assigned_housekeeper_id,
        priority=data.priority,
        due_at=data.due_at,
        notes=data.notes,
    )
    db.add(task)
    db.flush()
    _create_checklist_from_template(db, task, data.template_id, data.task_type)

    if data.task_type in (HousekeepingTaskType.CHECKOUT, HousekeepingTaskType.DEEP_CLEAN):
        room.status = RoomStatus.VACANT_DIRTY

    db.commit()
    db.refresh(task)
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task.id)
        .first()
    )
    return _task_to_read(task, task.room.room_number if task.room else None)


def bulk_create_tasks(
    db: Session, tenant_id: int, data: BulkTaskCreate, default_brand_id: int | None = None
) -> BulkTaskCreateResponse:
    created: list[HousekeepingTaskRead] = []
    for room_id in data.room_ids:
        task = create_task(
            db,
            tenant_id,
            HousekeepingTaskCreate(
                outlet_id=data.outlet_id,
                room_id=room_id,
                task_type=data.task_type,
                assigned_to=data.assigned_to,
                priority=data.priority,
                notes=data.notes,
                brand_id=data.brand_id,
            ),
            default_brand_id=default_brand_id,
        )
        created.append(task)
    return BulkTaskCreateResponse(
        message=f"Created {len(created)} cleaning task(s)",
        tasks_created=len(created),
        tasks=created,
    )


_SWEEP_ROOM_STATUS: dict[str, tuple[RoomStatus, HousekeepingTaskType]] = {
    "checkout": (RoomStatus.CHECKOUT_PENDING, HousekeepingTaskType.CHECKOUT),
    "daily": (RoomStatus.VACANT_DIRTY, HousekeepingTaskType.DAILY),
}

# Daily/stayover sweep also includes occupied in-house rooms.
_DAILY_SWEEP_STATUSES = (RoomStatus.VACANT_DIRTY, RoomStatus.OCCUPIED)


def _room_has_active_task(db: Session, room_id: int) -> bool:
    return (
        db.query(HousekeepingTask.id)
        .filter(
            HousekeepingTask.room_id == room_id,
            HousekeepingTask.status.in_([
                HousekeepingTaskStatus.PENDING,
                HousekeepingTaskStatus.IN_PROGRESS,
            ]),
        )
        .first()
        is not None
    )


def _get_floor_assignment_map(db: Session, tenant_id: int, outlet_id: int) -> dict[str, int]:
    rows = (
        db.query(HousekeepingFloorAssignment)
        .filter(
            HousekeepingFloorAssignment.tenant_id == tenant_id,
            HousekeepingFloorAssignment.outlet_id == outlet_id,
            HousekeepingFloorAssignment.is_active.is_(True),
        )
        .all()
    )
    return {row.floor: row.housekeeper_id for row in rows}


def _resolve_floor_assignments(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    rooms: list[HotelRoom],
    *,
    use_floor_assignments: bool,
) -> dict[str, int]:
    if use_floor_assignments:
        saved = _get_floor_assignment_map(db, tenant_id, outlet_id)
        if saved:
            return saved
    staff = list_housekeeping_staff(db, tenant_id)
    staff_ids = [s.id for s in staff]
    if not staff_ids:
        return {}
    floors = sorted({room.floor for room in rooms}, key=lambda f: (len(f), f))
    return {floor: staff_ids[index % len(staff_ids)] for index, floor in enumerate(floors)}


def run_task_sweep(
    db: Session, tenant_id: int, data: TaskSweepCreate, default_brand_id: int | None = None
) -> TaskSweepResponse:
    if data.sweep_type not in _SWEEP_ROOM_STATUS:
        raise ConflictError("Invalid sweep type")

    room_status, task_type = _SWEEP_ROOM_STATUS[data.sweep_type]
    _get_outlet(db, tenant_id, data.outlet_id)

    room_q = db.query(HotelRoom).filter(
        HotelRoom.tenant_id == tenant_id,
        HotelRoom.outlet_id == data.outlet_id,
        HotelRoom.is_active.is_(True),
    )
    if data.sweep_type == "daily":
        room_q = room_q.filter(HotelRoom.status.in_(_DAILY_SWEEP_STATUSES))
    else:
        room_q = room_q.filter(HotelRoom.status == room_status)
    rooms = room_q.order_by(HotelRoom.floor, HotelRoom.room_number).all()

    floor_assignments: dict[str, int] = {}
    if data.distribute_by_floor:
        floor_assignments = _resolve_floor_assignments(
            db,
            tenant_id,
            data.outlet_id,
            rooms,
            use_floor_assignments=data.use_floor_assignments,
        )

    created = 0
    skipped = 0
    for room in rooms:
        if _room_has_active_task(db, room.id):
            skipped += 1
            continue
        assigned_to = floor_assignments.get(room.floor) if data.distribute_by_floor else data.assigned_to
        if assigned_to is None and room.assigned_housekeeper_id:
            assigned_to = room.assigned_housekeeper_id
        create_task(
            db,
            tenant_id,
            HousekeepingTaskCreate(
                outlet_id=data.outlet_id,
                room_id=room.id,
                task_type=task_type,
                assigned_to=assigned_to,
                brand_id=data.brand_id,
            ),
            default_brand_id=default_brand_id,
        )
        created += 1

    label = "checkout" if data.sweep_type == "checkout" else "daily cleaning"
    return TaskSweepResponse(
        message=f"Created {created} {label} task(s)" + (f", skipped {skipped} with active tasks" if skipped else ""),
        tasks_created=created,
        rooms_skipped=skipped,
    )


def update_task(db: Session, tenant_id: int, task_id: int, data: HousekeepingTaskUpdate) -> HousekeepingTaskRead:
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task_id, HousekeepingTask.tenant_id == tenant_id)
        .first()
    )
    if not task:
        raise NotFoundError("Task not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(task, field, value)

    if data.status == HousekeepingTaskStatus.IN_PROGRESS and not task.started_at:
        task.started_at = datetime.utcnow()
    elif data.status == HousekeepingTaskStatus.COMPLETED:
        task.completed_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return _task_to_read(task, task.room.room_number if task.room else None)


def start_task(db: Session, tenant_id: int, task_id: int) -> HousekeepingTaskRead:
    return update_task(
        db, tenant_id, task_id, HousekeepingTaskUpdate(status=HousekeepingTaskStatus.IN_PROGRESS)
    )


def update_checklist_item(
    db: Session, tenant_id: int, task_id: int, item_id: int, user_id: int, data: TaskChecklistItemUpdate
) -> HousekeepingTaskRead:
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task_id, HousekeepingTask.tenant_id == tenant_id)
        .first()
    )
    if not task:
        raise NotFoundError("Task not found")

    item = next((i for i in task.checklist_items if i.id == item_id), None)
    if not item:
        raise NotFoundError("Checklist item not found")

    item.is_checked = data.is_checked
    item.checked_at = datetime.utcnow() if data.is_checked else None
    item.checked_by = user_id if data.is_checked else None
    if data.notes is not None:
        item.notes = data.notes

    if task.status == HousekeepingTaskStatus.PENDING:
        task.status = HousekeepingTaskStatus.IN_PROGRESS
        task.started_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return _task_to_read(task, task.room.room_number if task.room else None)


def complete_task(db: Session, tenant_id: int, task_id: int, user_id: int) -> HousekeepingTaskRead:
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task_id, HousekeepingTask.tenant_id == tenant_id)
        .first()
    )
    if not task:
        raise NotFoundError("Task not found")

    required_unchecked = [i for i in task.checklist_items if i.is_required and not i.is_checked]
    if required_unchecked:
        raise ConflictError(f"{len(required_unchecked)} required checklist items are not completed")

    task.status = HousekeepingTaskStatus.COMPLETED
    task.completed_at = datetime.utcnow()
    if task.room:
        task.room.status = RoomStatus.INSPECTING
        task.room.last_cleaned_at = datetime.utcnow()

    db.commit()
    db.refresh(task)
    return _task_to_read(task, task.room.room_number if task.room else None)


def verify_task(db: Session, tenant_id: int, task_id: int, user_id: int) -> HousekeepingTaskRead:
    task = (
        db.query(HousekeepingTask)
        .options(joinedload(HousekeepingTask.checklist_items), joinedload(HousekeepingTask.room))
        .filter(HousekeepingTask.id == task_id, HousekeepingTask.tenant_id == tenant_id)
        .first()
    )
    if not task:
        raise NotFoundError("Task not found")
    if task.status != HousekeepingTaskStatus.COMPLETED:
        raise ConflictError("Task must be completed before verification")

    task.status = HousekeepingTaskStatus.VERIFIED
    task.verified_by = user_id
    if task.room:
        task.room.status = RoomStatus.VACANT_CLEAN

    db.commit()
    db.refresh(task)
    return _task_to_read(task, task.room.room_number if task.room else None)


# ── Maintenance Tickets ───────────────────────────────────────────────────────

def list_tickets(
    db: Session,
    tenant_id: int,
    page: int,
    page_size: int,
    outlet_id: int | None = None,
    status: MaintenanceTicketStatus | None = None,
    priority: MaintenancePriority | None = None,
    room_id: int | None = None,
) -> tuple[list[MaintenanceTicketRead], int]:
    q = (
        db.query(MaintenanceTicket)
        .options(joinedload(MaintenanceTicket.comments), joinedload(MaintenanceTicket.room))
        .filter(MaintenanceTicket.tenant_id == tenant_id, MaintenanceTicket.is_active.is_(True))
    )
    if outlet_id:
        q = q.filter(MaintenanceTicket.outlet_id == outlet_id)
    if status:
        q = q.filter(MaintenanceTicket.status == status)
    if priority:
        q = q.filter(MaintenanceTicket.priority == priority)
    if room_id:
        q = q.filter(MaintenanceTicket.room_id == room_id)
    q = q.order_by(MaintenanceTicket.created_at.desc())
    rows, total = paginate_query(q, page, page_size)
    return [_ticket_to_read(t, t.room.room_number if t.room else None) for t in rows], total


def get_ticket(db: Session, tenant_id: int, ticket_id: int) -> MaintenanceTicketRead:
    ticket = (
        db.query(MaintenanceTicket)
        .options(joinedload(MaintenanceTicket.comments), joinedload(MaintenanceTicket.room))
        .filter(MaintenanceTicket.id == ticket_id, MaintenanceTicket.tenant_id == tenant_id)
        .first()
    )
    if not ticket:
        raise NotFoundError("Ticket not found")
    return _ticket_to_read(ticket, ticket.room.room_number if ticket.room else None)


def create_ticket(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: MaintenanceTicketCreate,
    default_brand_id: int | None = None,
) -> MaintenanceTicketRead:
    room = _get_room(db, tenant_id, data.room_id)
    ticket = MaintenanceTicket(
        tenant_id=tenant_id,
        brand_id=data.brand_id or room.brand_id or default_brand_id,
        outlet_id=data.outlet_id,
        room_id=data.room_id,
        ticket_number=_generate_ticket_number(db, tenant_id),
        title=data.title,
        description=data.description,
        category=data.category,
        priority=data.priority,
        status=MaintenanceTicketStatus.ASSIGNED if data.assigned_to else MaintenanceTicketStatus.OPEN,
        reported_by=user_id,
        assigned_to=data.assigned_to,
        due_date=data.due_date,
    )
    db.add(ticket)
    db.commit()
    db.refresh(ticket)
    ticket = (
        db.query(MaintenanceTicket)
        .options(joinedload(MaintenanceTicket.comments), joinedload(MaintenanceTicket.room))
        .filter(MaintenanceTicket.id == ticket.id)
        .first()
    )
    return _ticket_to_read(ticket, ticket.room.room_number if ticket.room else None)


def generate_ticket(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: MaintenanceTicketGenerate,
    default_brand_id: int | None = None,
) -> MaintenanceTicketRead:
    room = _get_room(db, tenant_id, data.room_id)
    if data.set_room_out_of_order:
        room.status = RoomStatus.OUT_OF_ORDER

    ticket = create_ticket(
        db,
        tenant_id,
        user_id,
        MaintenanceTicketCreate(
            outlet_id=data.outlet_id,
            room_id=data.room_id,
            title=data.title,
            description=data.description,
            category=data.category,
            priority=data.priority,
            assigned_to=data.assign_to,
            brand_id=data.brand_id,
        ),
        default_brand_id,
    )
    return ticket


def update_ticket(
    db: Session, tenant_id: int, ticket_id: int, data: MaintenanceTicketUpdate
) -> MaintenanceTicketRead:
    ticket = (
        db.query(MaintenanceTicket)
        .options(joinedload(MaintenanceTicket.comments), joinedload(MaintenanceTicket.room))
        .filter(MaintenanceTicket.id == ticket_id, MaintenanceTicket.tenant_id == tenant_id)
        .first()
    )
    if not ticket:
        raise NotFoundError("Ticket not found")

    for field, value in data.model_dump(exclude_unset=True).items():
        setattr(ticket, field, value)

    if data.status in (MaintenanceTicketStatus.RESOLVED, MaintenanceTicketStatus.CLOSED):
        ticket.resolved_at = datetime.utcnow()
        if ticket.room and ticket.room.status in (RoomStatus.OUT_OF_ORDER, RoomStatus.MAINTENANCE):
            ticket.room.status = RoomStatus.VACANT_DIRTY

    db.commit()
    db.refresh(ticket)
    return _ticket_to_read(ticket, ticket.room.room_number if ticket.room else None)


def add_ticket_comment(
    db: Session, tenant_id: int, ticket_id: int, user_id: int, data: TicketCommentCreate
) -> TicketCommentRead:
    ticket = (
        db.query(MaintenanceTicket)
        .filter(MaintenanceTicket.id == ticket_id, MaintenanceTicket.tenant_id == tenant_id)
        .first()
    )
    if not ticket:
        raise NotFoundError("Ticket not found")

    comment = TicketComment(ticket_id=ticket_id, user_id=user_id, comment=data.comment)
    db.add(comment)
    db.commit()
    db.refresh(comment)
    return TicketCommentRead.model_validate(comment)


def setup_demo_for_outlet(
    db: Session,
    tenant_id: int,
    user_id: int,
    data: SetupDemoRequest,
    default_brand_id: int | None = None,
) -> SetupDemoResponse:
    """Create demo room types, rooms, templates, a sample task and tickets for an outlet."""
    outlet = _get_outlet(db, tenant_id, data.outlet_id)
    brand_id = data.brand_id or outlet.brand_id or default_brand_id

    existing = (
        db.query(HotelRoom)
        .filter(HotelRoom.tenant_id == tenant_id, HotelRoom.outlet_id == data.outlet_id)
        .count()
    )
    if existing:
        raise ConflictError("This outlet already has rooms. Demo setup is only for empty outlets.")

    room_types_created = 0
    type_map: dict[str, RoomType] = {}
    for name, rate, occ, amenities in [
        ("Standard", 3500, 2, "WiFi, TV, AC"),
        ("Deluxe", 5500, 3, "WiFi, TV, AC, Bathtub"),
        ("Suite", 9500, 4, "WiFi, Smart TV, Jacuzzi, Living area"),
    ]:
        existing_type = (
            db.query(RoomType)
            .filter(RoomType.tenant_id == tenant_id, RoomType.name == name)
            .first()
        )
        if existing_type:
            type_map[name] = existing_type
        else:
            rt = RoomType(
                tenant_id=tenant_id,
                brand_id=brand_id,
                name=name,
                base_rate=rate,
                max_occupancy=occ,
                amenities=amenities,
            )
            db.add(rt)
            db.flush()
            type_map[name] = rt
            room_types_created += 1

    templates_before = db.query(ChecklistTemplate).filter(ChecklistTemplate.tenant_id == tenant_id).count()
    seed_default_templates(db, tenant_id, brand_id)
    templates_after = db.query(ChecklistTemplate).filter(ChecklistTemplate.tenant_id == tenant_id).count()
    templates_created = max(0, templates_after - templates_before)

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

    rooms: dict[str, HotelRoom] = {}
    for number, floor, type_name, status in room_specs:
        room = HotelRoom(
            tenant_id=tenant_id,
            brand_id=brand_id,
            outlet_id=data.outlet_id,
            room_type_id=type_map[type_name].id,
            room_number=number,
            floor=floor,
            status=status,
            guest_name="Demo Guest" if status == RoomStatus.OCCUPIED else None,
            checkout_date=date.today() if status == RoomStatus.CHECKOUT_PENDING else None,
            last_cleaned_at=datetime.utcnow() - timedelta(hours=4)
            if status == RoomStatus.VACANT_CLEAN
            else None,
        )
        db.add(room)
        db.flush()
        rooms[number] = room

    tasks_created = 0
    checkout_room = rooms.get("103")
    if checkout_room:
        task = HousekeepingTask(
            tenant_id=tenant_id,
            brand_id=brand_id,
            outlet_id=data.outlet_id,
            room_id=checkout_room.id,
            task_type=HousekeepingTaskType.CHECKOUT,
            status=HousekeepingTaskStatus.PENDING,
            priority=MaintenancePriority.HIGH,
            due_at=datetime.utcnow() + timedelta(hours=2),
        )
        db.add(task)
        db.flush()
        _create_checklist_from_template(db, task, None, HousekeepingTaskType.CHECKOUT)
        tasks_created = 1

    tickets_created = 0
    for room_num, title, desc, cat, pri, stat in [
        (
            "203",
            "AC not cooling properly",
            "Guest reported AC blowing warm air.",
            MaintenanceCategory.HVAC,
            MaintenancePriority.HIGH,
            MaintenanceTicketStatus.IN_PROGRESS,
        ),
        (
            "205",
            "Bathroom leak — pipe repair needed",
            "Water leaking from ceiling. Room blocked.",
            MaintenanceCategory.PLUMBING,
            MaintenancePriority.URGENT,
            MaintenanceTicketStatus.OPEN,
        ),
    ]:
        room = rooms.get(room_num)
        if room:
            db.add(
                MaintenanceTicket(
                    tenant_id=tenant_id,
                    brand_id=brand_id,
                    outlet_id=data.outlet_id,
                    room_id=room.id,
                    ticket_number=_generate_ticket_number(db, tenant_id),
                    title=title,
                    description=desc,
                    category=cat,
                    priority=pri,
                    status=stat,
                    reported_by=user_id,
                )
            )
            tickets_created += 1

    _ensure_default_sweep_schedules(db, tenant_id, data.outlet_id, brand_id)

    db.commit()
    return SetupDemoResponse(
        message="Demo housekeeping data created successfully",
        rooms_created=len(room_specs),
        room_types_created=room_types_created,
        templates_created=templates_created,
        tasks_created=tasks_created,
        tickets_created=tickets_created,
    )


# ── Floor assignments & sweep schedules ─────────────────────────────────────


def list_floor_assignments(
    db: Session, tenant_id: int, outlet_id: int
) -> list[FloorAssignmentRead]:
    _get_outlet(db, tenant_id, outlet_id)
    rows = (
        db.query(HousekeepingFloorAssignment, User.full_name)
        .join(User, User.id == HousekeepingFloorAssignment.housekeeper_id)
        .filter(
            HousekeepingFloorAssignment.tenant_id == tenant_id,
            HousekeepingFloorAssignment.outlet_id == outlet_id,
            HousekeepingFloorAssignment.is_active.is_(True),
        )
        .order_by(HousekeepingFloorAssignment.floor)
        .all()
    )
    return [
        FloorAssignmentRead(
            id=row.id,
            outlet_id=row.outlet_id,
            floor=row.floor,
            housekeeper_id=row.housekeeper_id,
            housekeeper_name=name,
        )
        for row, name in rows
    ]


def upsert_floor_assignments(
    db: Session, tenant_id: int, data: FloorAssignmentBulkUpsert
) -> list[FloorAssignmentRead]:
    _get_outlet(db, tenant_id, data.outlet_id)
    existing = {
        row.floor: row
        for row in db.query(HousekeepingFloorAssignment)
        .filter(
            HousekeepingFloorAssignment.tenant_id == tenant_id,
            HousekeepingFloorAssignment.outlet_id == data.outlet_id,
            HousekeepingFloorAssignment.is_active.is_(True),
        )
        .all()
    }
    seen_floors: set[str] = set()
    for item in data.assignments:
        seen_floors.add(item.floor)
        if item.floor in existing:
            existing[item.floor].housekeeper_id = item.housekeeper_id
        else:
            db.add(
                HousekeepingFloorAssignment(
                    tenant_id=tenant_id,
                    outlet_id=data.outlet_id,
                    floor=item.floor,
                    housekeeper_id=item.housekeeper_id,
                )
            )
    for floor, row in existing.items():
        if floor not in seen_floors:
            row.is_active = False
    db.commit()
    return list_floor_assignments(db, tenant_id, data.outlet_id)


def list_sweep_schedules(
    db: Session, tenant_id: int, outlet_id: int | None = None
) -> list[SweepScheduleRead]:
    q = db.query(HousekeepingSweepSchedule).filter(
        HousekeepingSweepSchedule.tenant_id == tenant_id,
        HousekeepingSweepSchedule.is_active.is_(True),
    )
    if outlet_id:
        q = q.filter(HousekeepingSweepSchedule.outlet_id == outlet_id)
    return [SweepScheduleRead.model_validate(row) for row in q.order_by(HousekeepingSweepSchedule.outlet_id).all()]


def upsert_sweep_schedule(
    db: Session, tenant_id: int, data: SweepScheduleUpsert, default_brand_id: int | None = None
) -> SweepScheduleRead:
    _get_outlet(db, tenant_id, data.outlet_id)
    row = (
        db.query(HousekeepingSweepSchedule)
        .filter(
            HousekeepingSweepSchedule.tenant_id == tenant_id,
            HousekeepingSweepSchedule.outlet_id == data.outlet_id,
            HousekeepingSweepSchedule.sweep_type == data.sweep_type,
            HousekeepingSweepSchedule.is_active.is_(True),
        )
        .first()
    )
    if row:
        row.run_time = data.run_time
        row.enabled = data.enabled
        row.distribute_by_floor = data.distribute_by_floor
        row.use_floor_assignments = data.use_floor_assignments
    else:
        row = HousekeepingSweepSchedule(
            tenant_id=tenant_id,
            brand_id=default_brand_id,
            outlet_id=data.outlet_id,
            sweep_type=data.sweep_type,
            run_time=data.run_time,
            enabled=data.enabled,
            distribute_by_floor=data.distribute_by_floor,
            use_floor_assignments=data.use_floor_assignments,
        )
        db.add(row)
    db.commit()
    db.refresh(row)
    return SweepScheduleRead.model_validate(row)


def run_due_sweep_schedules(
    db: Session, tenant_id: int, outlet_id: int | None = None, force: bool = False
) -> RunDueSchedulesResponse:
    today = date.today()
    now = datetime.now().strftime("%H:%M")
    q = db.query(HousekeepingSweepSchedule).filter(
        HousekeepingSweepSchedule.tenant_id == tenant_id,
        HousekeepingSweepSchedule.is_active.is_(True),
        HousekeepingSweepSchedule.enabled.is_(True),
    )
    if outlet_id:
        q = q.filter(HousekeepingSweepSchedule.outlet_id == outlet_id)

    schedules_run = 0
    tasks_created = 0
    for schedule in q.all():
        if not force:
            if schedule.last_run_date == today:
                continue
            if schedule.run_time > now:
                continue
        result = run_task_sweep(
            db,
            tenant_id,
            TaskSweepCreate(
                outlet_id=schedule.outlet_id,
                sweep_type=schedule.sweep_type,  # type: ignore[arg-type]
                distribute_by_floor=schedule.distribute_by_floor,
                use_floor_assignments=schedule.use_floor_assignments,
            ),
        )
        schedule.last_run_date = today
        schedules_run += 1
        tasks_created += result.tasks_created
    db.commit()
    return RunDueSchedulesResponse(
        message=f"Ran {schedules_run} schedule(s), created {tasks_created} task(s)",
        schedules_run=schedules_run,
        tasks_created=tasks_created,
    )


def run_due_sweep_schedules_all_tenants(
    db: Session, force: bool = False
) -> RunDueSchedulesGlobalResponse:
    """Run due sweep schedules for every tenant that has enabled schedules."""
    tenant_ids = [
        row[0]
        for row in db.query(HousekeepingSweepSchedule.tenant_id)
        .filter(
            HousekeepingSweepSchedule.is_active.is_(True),
            HousekeepingSweepSchedule.enabled.is_(True),
        )
        .distinct()
        .all()
    ]

    schedules_run = 0
    tasks_created = 0
    tenants_processed = 0
    for tenant_id in tenant_ids:
        result = run_due_sweep_schedules(db, tenant_id, force=force)
        if result.schedules_run > 0:
            tenants_processed += 1
        schedules_run += result.schedules_run
        tasks_created += result.tasks_created

    return RunDueSchedulesGlobalResponse(
        message=(
            f"Ran {schedules_run} schedule(s) across {tenants_processed} tenant(s), "
            f"created {tasks_created} task(s)"
        ),
        schedules_run=schedules_run,
        tasks_created=tasks_created,
        tenants_processed=tenants_processed,
    )


def _ensure_default_sweep_schedules(
    db: Session,
    tenant_id: int,
    outlet_id: int,
    brand_id: int | None,
) -> None:
    for sweep_type, run_time in [("checkout", "06:00"), ("daily", "07:00")]:
        exists = (
            db.query(HousekeepingSweepSchedule)
            .filter(
                HousekeepingSweepSchedule.tenant_id == tenant_id,
                HousekeepingSweepSchedule.outlet_id == outlet_id,
                HousekeepingSweepSchedule.sweep_type == sweep_type,
                HousekeepingSweepSchedule.is_active.is_(True),
            )
            .first()
        )
        if exists:
            continue
        db.add(
            HousekeepingSweepSchedule(
                tenant_id=tenant_id,
                brand_id=brand_id,
                outlet_id=outlet_id,
                sweep_type=sweep_type,
                run_time=run_time,
                enabled=True,
                distribute_by_floor=True,
                use_floor_assignments=True,
            )
        )
