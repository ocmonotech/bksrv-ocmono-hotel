from __future__ import annotations

from fastapi import APIRouter, Depends, File, Form, Query, Response, UploadFile, status
from sqlalchemy.orm import Session

from app.common.dependencies import require_permission
from app.common.pagination import PaginatedSuccessResponse, success_paginated
from app.core.database import get_db
from app.core.permissions import Permission
from app.modules.housekeeping import service
from app.modules.housekeeping.models import (
    HousekeepingTaskStatus,
    MaintenancePriority,
    MaintenanceTicketStatus,
    RoomStatus,
)
from app.modules.housekeeping.schemas import (
    AmenityBulkAssignRequest,
    AmenityBulkAssignResponse,
    AmenityCreate,
    AmenityRead,
    AmenityUpdate,
    BulkRoomCreate,
    BulkRoomCreateResponse,
    BulkTaskCreate,
    BulkTaskCreateResponse,
    FloorAssignmentBulkUpsert,
    FloorAssignmentRead,
    RunDueSchedulesResponse,
    SweepScheduleRead,
    SweepScheduleUpsert,
    TaskSweepCreate,
    TaskSweepResponse,
    ChecklistTemplateCreate,
    ChecklistTemplateRead,
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
    RoomStatusUpdate,
    RoomTypeAmenityAssign,
    RoomTypeCreate,
    RoomTypeRead,
    RoomTypeUpdate,
    SetupDemoRequest,
    SetupDemoResponse,
    TaskChecklistItemUpdate,
    TicketCommentCreate,
    TicketCommentRead,
)
from app.modules.users.models import User

router = APIRouter()


@router.get("/dashboard", response_model=HousekeepingDashboard)
def get_dashboard(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> HousekeepingDashboard:
    return service.get_dashboard(db, current_user.tenant_id, outlet_id=outlet_id)


@router.post("/setup-demo", response_model=SetupDemoResponse, status_code=status.HTTP_201_CREATED)
def setup_demo(
    body: SetupDemoRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> SetupDemoResponse:
    return service.setup_demo_for_outlet(
        db,
        current_user.tenant_id,
        current_user.id,
        body,
        default_brand_id=current_user.brand_id,
    )


@router.get("/staff", response_model=list[HousekeepingStaffRead])
def list_housekeeping_staff(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[HousekeepingStaffRead]:
    return service.list_housekeeping_staff(db, current_user.tenant_id)


@router.get("/floor-assignments", response_model=list[FloorAssignmentRead])
def list_floor_assignments(
    outlet_id: int = Query(...),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[FloorAssignmentRead]:
    return service.list_floor_assignments(db, current_user.tenant_id, outlet_id)


@router.put("/floor-assignments", response_model=list[FloorAssignmentRead])
def upsert_floor_assignments(
    body: FloorAssignmentBulkUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> list[FloorAssignmentRead]:
    return service.upsert_floor_assignments(db, current_user.tenant_id, body)


@router.get("/schedules", response_model=list[SweepScheduleRead])
def list_sweep_schedules(
    outlet_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[SweepScheduleRead]:
    return service.list_sweep_schedules(db, current_user.tenant_id, outlet_id=outlet_id)


@router.put("/schedules", response_model=SweepScheduleRead)
def upsert_sweep_schedule(
    body: SweepScheduleUpsert,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> SweepScheduleRead:
    return service.upsert_sweep_schedule(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.post("/schedules/run-due", response_model=RunDueSchedulesResponse)
def run_due_sweep_schedules(
    outlet_id: int | None = Query(None),
    force: bool = Query(False),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> RunDueSchedulesResponse:
    return service.run_due_sweep_schedules(
        db, current_user.tenant_id, outlet_id=outlet_id, force=force
    )


# ── Amenities catalog ───────────────────────────────────────────────────────

@router.get("/amenities", response_model=list[AmenityRead])
def list_amenities(
    include_inactive: bool = Query(False),
    category: str | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[AmenityRead]:
    return service.list_amenities(
        db,
        current_user.tenant_id,
        include_inactive=include_inactive,
        category=category,
    )


@router.post("/amenities", response_model=AmenityRead, status_code=status.HTTP_201_CREATED)
def create_amenity(
    body: AmenityCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> AmenityRead:
    return service.create_amenity(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.patch("/amenities/{amenity_id}", response_model=AmenityRead)
def update_amenity(
    amenity_id: int,
    body: AmenityUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> AmenityRead:
    return service.update_amenity(db, current_user.tenant_id, amenity_id, body)


@router.post("/amenities/seed", response_model=list[AmenityRead])
def seed_amenities(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> list[AmenityRead]:
    rows = service.seed_default_amenities(db, current_user.tenant_id, current_user.brand_id)
    db.commit()
    return service.list_amenities(db, current_user.tenant_id, include_inactive=True)


@router.put("/room-types/{type_id}/amenities", response_model=RoomTypeRead)
def assign_room_type_amenities(
    type_id: int,
    body: RoomTypeAmenityAssign,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> RoomTypeRead:
    return service.set_room_type_amenities(db, current_user.tenant_id, type_id, body.amenity_ids)


@router.post("/amenities/bulk-assign", response_model=AmenityBulkAssignResponse)
def bulk_assign_amenity(
    body: AmenityBulkAssignRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> AmenityBulkAssignResponse:
    count, rows = service.bulk_assign_amenity_to_room_types(
        db, current_user.tenant_id, body.amenity_id, body.room_type_ids
    )
    return AmenityBulkAssignResponse(
        amenity_id=body.amenity_id,
        updated_room_types=count,
        room_types=rows,
    )


@router.post("/room-types/{type_id}/images", response_model=RoomTypeRead)
async def upload_room_type_image(
    type_id: int,
    file: UploadFile = File(...),
    as_cover: bool = Form(True),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> RoomTypeRead:
    from app.modules.housekeeping.media import save_room_type_image

    url = await save_room_type_image(current_user.tenant_id, file)
    return service.attach_room_type_image(
        db, current_user.tenant_id, type_id, url, as_cover=as_cover
    )


# ── Room Types ──────────────────────────────────────────────────────────────

@router.get("/room-types", response_model=list[RoomTypeRead])
def list_room_types(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[RoomTypeRead]:
    return service.list_room_types(db, current_user.tenant_id)


@router.post("/room-types", response_model=RoomTypeRead, status_code=status.HTTP_201_CREATED)
def create_room_type(
    body: RoomTypeCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> RoomTypeRead:
    return service.create_room_type(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.patch("/room-types/{type_id}", response_model=RoomTypeRead)
def update_room_type(
    type_id: int,
    body: RoomTypeUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> RoomTypeRead:
    return service.update_room_type(db, current_user.tenant_id, type_id, body)


# ── Rooms ───────────────────────────────────────────────────────────────────

@router.get("/rooms", response_model=PaginatedSuccessResponse[HotelRoomRead])
def list_rooms(
    page: int = Query(1, ge=1),
    page_size: int = Query(100, ge=1, le=500),
    outlet_id: int | None = Query(None),
    floor: str | None = Query(None),
    wing: str | None = Query(None),
    status: RoomStatus | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> PaginatedSuccessResponse[HotelRoomRead]:
    items, total = service.list_rooms(
        db, current_user.tenant_id, page, page_size,
        outlet_id=outlet_id, floor=floor, wing=wing, status=status,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/rooms/{room_id}", response_model=HotelRoomRead)
def get_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> HotelRoomRead:
    return service.get_room(db, current_user.tenant_id, room_id)


@router.post("/rooms", response_model=HotelRoomRead, status_code=status.HTTP_201_CREATED)
def create_room(
    body: HotelRoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HotelRoomRead:
    return service.create_room(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.post("/rooms/bulk", response_model=BulkRoomCreateResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_rooms(
    body: BulkRoomCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> BulkRoomCreateResponse:
    return service.bulk_create_rooms(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.patch("/rooms/{room_id}", response_model=HotelRoomRead)
def update_room(
    room_id: int,
    body: HotelRoomUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HotelRoomRead:
    return service.update_room(db, current_user.tenant_id, room_id, body)


@router.patch("/rooms/{room_id}/status", response_model=HotelRoomRead)
def update_room_status(
    room_id: int,
    body: RoomStatusUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HotelRoomRead:
    return service.update_room_status(db, current_user.tenant_id, room_id, body)


@router.delete("/rooms/{room_id}", status_code=status.HTTP_204_NO_CONTENT, response_class=Response)
def delete_room(
    room_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> Response:
    service.delete_room(db, current_user.tenant_id, room_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ── Checklist Templates ─────────────────────────────────────────────────────

@router.get("/checklist-templates", response_model=list[ChecklistTemplateRead])
def list_checklist_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> list[ChecklistTemplateRead]:
    return service.list_checklist_templates(db, current_user.tenant_id)


@router.post("/checklist-templates/seed", response_model=list[ChecklistTemplateRead])
def seed_checklist_templates(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> list[ChecklistTemplateRead]:
    return service.seed_default_templates(
        db, current_user.tenant_id, brand_id=current_user.brand_id
    )


@router.post("/checklist-templates", response_model=ChecklistTemplateRead, status_code=status.HTTP_201_CREATED)
def create_checklist_template(
    body: ChecklistTemplateCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> ChecklistTemplateRead:
    return service.create_checklist_template(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


# ── Housekeeping Tasks ──────────────────────────────────────────────────────

@router.get("/tasks", response_model=PaginatedSuccessResponse[HousekeepingTaskRead])
def list_tasks(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    outlet_id: int | None = Query(None),
    status: HousekeepingTaskStatus | None = Query(None),
    assigned_to: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> PaginatedSuccessResponse[HousekeepingTaskRead]:
    items, total = service.list_tasks(
        db, current_user.tenant_id, page, page_size,
        outlet_id=outlet_id, status=status, assigned_to=assigned_to,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/tasks/{task_id}", response_model=HousekeepingTaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> HousekeepingTaskRead:
    return service.get_task(db, current_user.tenant_id, task_id)


@router.post("/tasks", response_model=HousekeepingTaskRead, status_code=status.HTTP_201_CREATED)
def create_task(
    body: HousekeepingTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.create_task(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.post("/tasks/bulk", response_model=BulkTaskCreateResponse, status_code=status.HTTP_201_CREATED)
def bulk_create_tasks(
    body: BulkTaskCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> BulkTaskCreateResponse:
    return service.bulk_create_tasks(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.post("/sweeps", response_model=TaskSweepResponse, status_code=status.HTTP_201_CREATED)
def run_task_sweep(
    body: TaskSweepCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> TaskSweepResponse:
    return service.run_task_sweep(
        db, current_user.tenant_id, body, default_brand_id=current_user.brand_id
    )


@router.patch("/tasks/{task_id}", response_model=HousekeepingTaskRead)
def update_task(
    task_id: int,
    body: HousekeepingTaskUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.update_task(db, current_user.tenant_id, task_id, body)


@router.post("/tasks/{task_id}/start", response_model=HousekeepingTaskRead)
def start_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.start_task(db, current_user.tenant_id, task_id)


@router.patch("/tasks/{task_id}/checklist/{item_id}", response_model=HousekeepingTaskRead)
def update_checklist_item(
    task_id: int,
    item_id: int,
    body: TaskChecklistItemUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.update_checklist_item(
        db, current_user.tenant_id, task_id, item_id, current_user.id, body
    )


@router.post("/tasks/{task_id}/complete", response_model=HousekeepingTaskRead)
def complete_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.complete_task(db, current_user.tenant_id, task_id, current_user.id)


@router.post("/tasks/{task_id}/verify", response_model=HousekeepingTaskRead)
def verify_task(
    task_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> HousekeepingTaskRead:
    return service.verify_task(db, current_user.tenant_id, task_id, current_user.id)


# ── Maintenance Tickets ─────────────────────────────────────────────────────

@router.get("/tickets", response_model=PaginatedSuccessResponse[MaintenanceTicketRead])
def list_tickets(
    page: int = Query(1, ge=1),
    page_size: int = Query(50, ge=1, le=200),
    outlet_id: int | None = Query(None),
    status: MaintenanceTicketStatus | None = Query(None),
    priority: MaintenancePriority | None = Query(None),
    room_id: int | None = Query(None),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> PaginatedSuccessResponse[MaintenanceTicketRead]:
    items, total = service.list_tickets(
        db, current_user.tenant_id, page, page_size,
        outlet_id=outlet_id, status=status, priority=priority, room_id=room_id,
    )
    return success_paginated(items, total, page, page_size)


@router.get("/tickets/{ticket_id}", response_model=MaintenanceTicketRead)
def get_ticket(
    ticket_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_READ)),
) -> MaintenanceTicketRead:
    return service.get_ticket(db, current_user.tenant_id, ticket_id)


@router.post("/tickets", response_model=MaintenanceTicketRead, status_code=status.HTTP_201_CREATED)
def create_ticket(
    body: MaintenanceTicketCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> MaintenanceTicketRead:
    return service.create_ticket(
        db, current_user.tenant_id, current_user.id, body, default_brand_id=current_user.brand_id
    )


@router.post("/tickets/generate", response_model=MaintenanceTicketRead, status_code=status.HTTP_201_CREATED)
def generate_ticket(
    body: MaintenanceTicketGenerate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> MaintenanceTicketRead:
    return service.generate_ticket(
        db, current_user.tenant_id, current_user.id, body, default_brand_id=current_user.brand_id
    )


@router.patch("/tickets/{ticket_id}", response_model=MaintenanceTicketRead)
def update_ticket(
    ticket_id: int,
    body: MaintenanceTicketUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> MaintenanceTicketRead:
    return service.update_ticket(db, current_user.tenant_id, ticket_id, body)


@router.post("/tickets/{ticket_id}/comments", response_model=TicketCommentRead, status_code=status.HTTP_201_CREATED)
def add_ticket_comment(
    ticket_id: int,
    body: TicketCommentCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_permission(Permission.HOUSEKEEPING_WRITE)),
) -> TicketCommentRead:
    return service.add_ticket_comment(
        db, current_user.tenant_id, ticket_id, current_user.id, body
    )
