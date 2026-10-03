from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, Field, model_validator

from app.common.response import ORMSchema, TimestampSchema
from app.modules.housekeeping.models import (
    AmenityCategory,
    HousekeepingTaskStatus,
    HousekeepingTaskType,
    MaintenanceCategory,
    MaintenancePriority,
    MaintenanceTicketStatus,
    RoomStatus,
)


# ── Amenities catalog ───────────────────────────────────────────────────────

class AmenityCreate(BaseModel):
    name: str = Field(max_length=100)
    code: str | None = Field(default=None, max_length=64)
    category: AmenityCategory = AmenityCategory.OTHER
    icon: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int = Field(default=0, ge=0, le=9999)
    brand_id: int | None = None
    is_active: bool = True


class AmenityUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    code: str | None = Field(default=None, max_length=64)
    category: AmenityCategory | None = None
    icon: str | None = Field(default=None, max_length=64)
    description: str | None = Field(default=None, max_length=255)
    sort_order: int | None = Field(default=None, ge=0, le=9999)
    is_active: bool | None = None


class AmenityRead(ORMSchema, TimestampSchema):
    id: int
    name: str
    code: str
    category: AmenityCategory
    icon: str | None = None
    description: str | None = None
    sort_order: int = 0
    is_active: bool = True
    room_type_count: int = 0


class RoomTypeAmenityAssign(BaseModel):
    amenity_ids: list[int] = Field(default_factory=list)


class AmenityBulkAssignRequest(BaseModel):
    amenity_id: int
    room_type_ids: list[int] = Field(default_factory=list)


# ── Room Types ──────────────────────────────────────────────────────────────

class RoomTypeCreate(BaseModel):
    name: str = Field(max_length=100)
    description: str | None = None
    base_rate: float = Field(default=0, ge=0)
    max_occupancy: int = Field(default=2, ge=1, le=20)
    amenities: str | None = None
    amenity_ids: list[int] = Field(default_factory=list)
    image_url: str | None = Field(default=None, max_length=512)
    gallery_urls: list[str] = Field(default_factory=list)
    bed_type: str | None = Field(default=None, max_length=64)
    room_size_sqft: int | None = Field(default=None, ge=0, le=10000)
    brand_id: int | None = None


class RoomTypeUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=100)
    description: str | None = None
    base_rate: float | None = Field(default=None, ge=0)
    max_occupancy: int | None = Field(default=None, ge=1, le=20)
    amenities: str | None = None
    amenity_ids: list[int] | None = None
    image_url: str | None = Field(default=None, max_length=512)
    gallery_urls: list[str] | None = None
    bed_type: str | None = Field(default=None, max_length=64)
    room_size_sqft: int | None = Field(default=None, ge=0, le=10000)
    is_active: bool | None = None


class RoomTypeRead(ORMSchema, TimestampSchema):
    id: int
    name: str
    description: str | None = None
    base_rate: float
    max_occupancy: int
    amenities: str | None = None
    amenities_list: list[str] = Field(default_factory=list)
    amenity_ids: list[int] = Field(default_factory=list)
    catalog_amenities: list[AmenityRead] = Field(default_factory=list)
    image_url: str | None = None
    gallery_urls: list[str] = Field(default_factory=list)
    bed_type: str | None = None
    room_size_sqft: int | None = None
    is_active: bool = True
    room_count: int = 0


class AmenityBulkAssignResponse(BaseModel):
    amenity_id: int
    updated_room_types: int
    room_types: list[RoomTypeRead] = Field(default_factory=list)


# ── Rooms ───────────────────────────────────────────────────────────────────

class HotelRoomCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    room_type_id: int | None = None
    room_number: str = Field(max_length=32)
    floor: str = Field(default="1", max_length=16)
    wing: str | None = Field(default=None, max_length=32)
    status: RoomStatus = RoomStatus.VACANT_CLEAN
    guest_name: str | None = Field(default=None, max_length=255)
    checkout_date: date | None = None
    notes: str | None = None
    assigned_housekeeper_id: int | None = None


class BulkRoomCreate(BaseModel):
    outlet_id: int
    brand_id: int | None = None
    floor: str = Field(default="1", max_length=16)
    wing: str | None = Field(default=None, max_length=32)
    room_type_id: int | None = None
    prefix: str = Field(default="", max_length=8)
    start_number: int = Field(ge=1, le=9999)
    end_number: int = Field(ge=1, le=9999)
    status: RoomStatus = RoomStatus.VACANT_CLEAN

    @model_validator(mode="after")
    def validate_range(self) -> "BulkRoomCreate":
        if self.end_number < self.start_number:
            raise ValueError("end_number must be >= start_number")
        if self.end_number - self.start_number > 100:
            raise ValueError("Cannot create more than 101 rooms at once")
        return self


class BulkRoomCreateResponse(BaseModel):
    message: str
    rooms_created: int
    rooms: list["HotelRoomRead"] = Field(default_factory=list)


class HotelRoomUpdate(BaseModel):
    room_type_id: int | None = None
    room_number: str | None = Field(default=None, max_length=32)
    floor: str | None = Field(default=None, max_length=16)
    wing: str | None = Field(default=None, max_length=32)
    status: RoomStatus | None = None
    guest_name: str | None = Field(default=None, max_length=255)
    checkout_date: date | None = None
    notes: str | None = None
    assigned_housekeeper_id: int | None = None


class RoomStatusUpdate(BaseModel):
    status: RoomStatus
    guest_name: str | None = None
    checkout_date: date | None = None
    notes: str | None = None


class HotelRoomRead(ORMSchema, TimestampSchema):
    id: int
    outlet_id: int
    room_type_id: int | None = None
    room_type_name: str | None = None
    room_number: str
    floor: str
    wing: str | None = None
    status: RoomStatus
    guest_name: str | None = None
    checkout_date: date | None = None
    notes: str | None = None
    last_cleaned_at: datetime | None = None
    assigned_housekeeper_id: int | None = None
    active_task_id: int | None = None
    open_ticket_count: int = 0


# ── Checklist Templates ─────────────────────────────────────────────────────

class ChecklistTemplateItemCreate(BaseModel):
    label: str = Field(max_length=255)
    sort_order: int = 0
    is_required: bool = True


class ChecklistTemplateCreate(BaseModel):
    name: str = Field(max_length=128)
    task_type: HousekeepingTaskType
    description: str | None = Field(default=None, max_length=255)
    is_default: bool = False
    brand_id: int | None = None
    items: list[ChecklistTemplateItemCreate] = Field(default_factory=list)


class ChecklistTemplateItemRead(ORMSchema, TimestampSchema):
    id: int
    label: str
    sort_order: int
    is_required: bool


class ChecklistTemplateRead(ORMSchema, TimestampSchema):
    id: int
    name: str
    task_type: HousekeepingTaskType
    description: str | None = None
    is_default: bool
    items: list[ChecklistTemplateItemRead] = Field(default_factory=list)


# ── Housekeeping Tasks ──────────────────────────────────────────────────────

class HousekeepingTaskCreate(BaseModel):
    outlet_id: int
    room_id: int
    task_type: HousekeepingTaskType
    template_id: int | None = None
    assigned_to: int | None = None
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    due_at: datetime | None = None
    notes: str | None = None
    brand_id: int | None = None


class BulkTaskCreate(BaseModel):
    outlet_id: int
    room_ids: list[int] = Field(min_length=1, max_length=50)
    task_type: HousekeepingTaskType
    assigned_to: int | None = None
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    notes: str | None = None
    brand_id: int | None = None


class BulkTaskCreateResponse(BaseModel):
    message: str
    tasks_created: int
    tasks: list["HousekeepingTaskRead"] = Field(default_factory=list)


class TaskSweepCreate(BaseModel):
    outlet_id: int
    sweep_type: Literal["checkout", "daily"]
    distribute_by_floor: bool = False
    use_floor_assignments: bool = True
    assigned_to: int | None = None
    brand_id: int | None = None


class TaskSweepResponse(BaseModel):
    message: str
    tasks_created: int
    rooms_skipped: int


class HousekeepingTaskUpdate(BaseModel):
    status: HousekeepingTaskStatus | None = None
    assigned_to: int | None = None
    priority: MaintenancePriority | None = None
    due_at: datetime | None = None
    notes: str | None = None


class TaskChecklistItemRead(ORMSchema, TimestampSchema):
    id: int
    label: str
    sort_order: int
    is_required: bool
    is_checked: bool
    checked_at: datetime | None = None
    checked_by: int | None = None
    notes: str | None = None


class TaskChecklistItemUpdate(BaseModel):
    is_checked: bool
    notes: str | None = None


class HousekeepingTaskRead(ORMSchema, TimestampSchema):
    id: int
    outlet_id: int
    room_id: int
    room_number: str | None = None
    template_id: int | None = None
    task_type: HousekeepingTaskType
    status: HousekeepingTaskStatus
    assigned_to: int | None = None
    priority: MaintenancePriority
    due_at: datetime | None = None
    started_at: datetime | None = None
    completed_at: datetime | None = None
    verified_by: int | None = None
    notes: str | None = None
    checklist_items: list[TaskChecklistItemRead] = Field(default_factory=list)
    progress_percent: int = 0


# ── Maintenance Tickets ─────────────────────────────────────────────────────

class MaintenanceTicketCreate(BaseModel):
    outlet_id: int
    room_id: int
    title: str = Field(max_length=255)
    description: str | None = None
    category: MaintenanceCategory
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    assigned_to: int | None = None
    due_date: date | None = None
    brand_id: int | None = None


class MaintenanceTicketGenerate(BaseModel):
    """Quick ticket generation from room issue report."""
    outlet_id: int
    room_id: int
    title: str = Field(max_length=255)
    description: str | None = None
    category: MaintenanceCategory = MaintenanceCategory.OTHER
    priority: MaintenancePriority = MaintenancePriority.MEDIUM
    assign_to: int | None = None
    set_room_out_of_order: bool = False
    brand_id: int | None = None


class MaintenanceTicketUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=255)
    description: str | None = None
    category: MaintenanceCategory | None = None
    priority: MaintenancePriority | None = None
    status: MaintenanceTicketStatus | None = None
    assigned_to: int | None = None
    due_date: date | None = None
    resolution_notes: str | None = None


class TicketCommentCreate(BaseModel):
    comment: str = Field(min_length=1)


class TicketCommentRead(ORMSchema, TimestampSchema):
    id: int
    ticket_id: int
    user_id: int
    comment: str


class MaintenanceTicketRead(ORMSchema, TimestampSchema):
    id: int
    outlet_id: int
    room_id: int
    room_number: str | None = None
    ticket_number: str
    title: str
    description: str | None = None
    category: MaintenanceCategory
    priority: MaintenancePriority
    status: MaintenanceTicketStatus
    reported_by: int | None = None
    assigned_to: int | None = None
    due_date: date | None = None
    resolved_at: datetime | None = None
    resolution_notes: str | None = None
    comments: list[TicketCommentRead] = Field(default_factory=list)


# ── Dashboard ───────────────────────────────────────────────────────────────

class RoomStatusCount(BaseModel):
    status: RoomStatus
    count: int


class HousekeepingDashboard(BaseModel):
    total_rooms: int
    status_breakdown: list[RoomStatusCount]
    pending_tasks: int
    in_progress_tasks: int
    completed_tasks_today: int
    awaiting_inspection: int = 0
    open_tickets: int
    urgent_tickets: int
    rooms_needing_cleaning: int
    occupancy_rate: float
    avg_cleaning_time_minutes: float | None = None
    floors: list[str] = Field(default_factory=list)


class SetupDemoRequest(BaseModel):
    outlet_id: int
    brand_id: int | None = None


class SetupDemoResponse(BaseModel):
    message: str
    rooms_created: int
    room_types_created: int
    templates_created: int
    tasks_created: int
    tickets_created: int


class HousekeepingStaffRead(BaseModel):
    id: int
    full_name: str
    email: str
    role_name: str | None = None


class FloorAssignmentRead(BaseModel):
    id: int
    outlet_id: int
    floor: str
    housekeeper_id: int
    housekeeper_name: str | None = None


class FloorAssignmentItem(BaseModel):
    floor: str = Field(max_length=16)
    housekeeper_id: int


class FloorAssignmentBulkUpsert(BaseModel):
    outlet_id: int
    assignments: list[FloorAssignmentItem] = Field(default_factory=list)


class SweepScheduleRead(ORMSchema, TimestampSchema):
    id: int
    outlet_id: int
    sweep_type: str
    run_time: str
    enabled: bool
    distribute_by_floor: bool
    use_floor_assignments: bool
    last_run_date: date | None = None


class SweepScheduleUpsert(BaseModel):
    outlet_id: int
    sweep_type: Literal["checkout", "daily"]
    run_time: str = Field(pattern=r"^\d{2}:\d{2}$")
    enabled: bool = True
    distribute_by_floor: bool = True
    use_floor_assignments: bool = True


class RunDueSchedulesResponse(BaseModel):
    message: str
    schedules_run: int
    tasks_created: int


class RunDueSchedulesGlobalResponse(BaseModel):
    message: str
    schedules_run: int
    tasks_created: int
    tenants_processed: int
