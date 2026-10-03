from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class RoomStatus(str, enum.Enum):
    VACANT_CLEAN = "vacant_clean"
    VACANT_DIRTY = "vacant_dirty"
    OCCUPIED = "occupied"
    CHECKOUT_PENDING = "checkout_pending"
    INSPECTING = "inspecting"
    OUT_OF_ORDER = "out_of_order"
    MAINTENANCE = "maintenance"


class HousekeepingTaskStatus(str, enum.Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    VERIFIED = "verified"
    SKIPPED = "skipped"


class HousekeepingTaskType(str, enum.Enum):
    CHECKOUT = "checkout"
    DAILY = "daily"
    DEEP_CLEAN = "deep_clean"
    TURNDOWN = "turndown"
    INSPECTION = "inspection"
    GUEST_REQUEST = "guest_request"


class MaintenanceTicketStatus(str, enum.Enum):
    OPEN = "open"
    ASSIGNED = "assigned"
    IN_PROGRESS = "in_progress"
    ON_HOLD = "on_hold"
    RESOLVED = "resolved"
    CLOSED = "closed"


class MaintenancePriority(str, enum.Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"


class MaintenanceCategory(str, enum.Enum):
    PLUMBING = "plumbing"
    ELECTRICAL = "electrical"
    HVAC = "hvac"
    FURNITURE = "furniture"
    APPLIANCE = "appliance"
    CLEANING = "cleaning"
    OTHER = "other"


class AmenityCategory(str, enum.Enum):
    CONNECTIVITY = "connectivity"
    COMFORT = "comfort"
    BATHROOM = "bathroom"
    FOOD_DRINK = "food_drink"
    ENTERTAINMENT = "entertainment"
    VIEW = "view"
    ACCESSIBILITY = "accessibility"
    SAFETY = "safety"
    OTHER = "other"


class Amenity(Base, BaseMixin, TenantBrandMixin):
    """Reusable amenity catalog item for room types / guest portal."""

    __tablename__ = "amenities"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    code: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    category: Mapped[AmenityCategory] = mapped_column(
        Enum(
            AmenityCategory,
            values_callable=lambda enum_cls: [item.value for item in enum_cls],
            native_enum=False,
            length=32,
        ),
        default=AmenityCategory.OTHER,
        nullable=False,
    )
    icon: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    room_type_links: Mapped[list["RoomTypeAmenity"]] = relationship(
        back_populates="amenity",
        cascade="all, delete-orphan",
    )


class RoomTypeAmenity(Base, BaseMixin):
    """Many-to-many link between room types and amenity catalog items."""

    __tablename__ = "room_type_amenities"

    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True, nullable=False)
    amenity_id: Mapped[int] = mapped_column(ForeignKey("amenities.id"), index=True, nullable=False)

    room_type: Mapped["RoomType"] = relationship(back_populates="amenity_links")
    amenity: Mapped["Amenity"] = relationship(back_populates="room_type_links")


class RoomType(Base, BaseMixin, TenantBrandMixin):
    """Room category such as Standard, Deluxe, Suite."""

    __tablename__ = "room_types"

    name: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    base_rate: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    max_occupancy: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    amenities: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    image_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    gallery_urls: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    bed_type: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    room_size_sqft: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    rooms: Mapped[list["HotelRoom"]] = relationship(back_populates="room_type")
    amenity_links: Mapped[list["RoomTypeAmenity"]] = relationship(
        back_populates="room_type",
        cascade="all, delete-orphan",
    )


class HotelRoom(Base, BaseMixin, TenantBrandMixin):
    """Guest room / private dining room for housekeeping tracking."""

    __tablename__ = "hotel_rooms"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_type_id: Mapped[Optional[int]] = mapped_column(ForeignKey("room_types.id"), nullable=True, index=True)
    room_number: Mapped[str] = mapped_column(String(32), nullable=False, index=True)
    floor: Mapped[str] = mapped_column(String(16), nullable=False, default="1")
    wing: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    status: Mapped[RoomStatus] = mapped_column(Enum(RoomStatus), default=RoomStatus.VACANT_CLEAN)
    guest_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    checkout_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_cleaned_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    assigned_housekeeper_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    room_type: Mapped[Optional["RoomType"]] = relationship(back_populates="rooms")
    tasks: Mapped[list["HousekeepingTask"]] = relationship(back_populates="room")
    tickets: Mapped[list["MaintenanceTicket"]] = relationship(back_populates="room")


class ChecklistTemplate(Base, BaseMixin, TenantBrandMixin):
    """Reusable checklist template for room cleaning."""

    __tablename__ = "checklist_templates"

    name: Mapped[str] = mapped_column(String(128), nullable=False)
    task_type: Mapped[HousekeepingTaskType] = mapped_column(Enum(HousekeepingTaskType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    is_default: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    items: Mapped[list["ChecklistTemplateItem"]] = relationship(
        back_populates="template",
        cascade="all, delete-orphan",
        order_by="ChecklistTemplateItem.sort_order",
    )


class ChecklistTemplateItem(Base, BaseMixin):
    __tablename__ = "checklist_template_items"

    template_id: Mapped[int] = mapped_column(ForeignKey("checklist_templates.id"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    template: Mapped["ChecklistTemplate"] = relationship(back_populates="items")


class HousekeepingTask(Base, BaseMixin, TenantBrandMixin):
    """Assigned cleaning task with checklist progress."""

    __tablename__ = "housekeeping_tasks"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("hotel_rooms.id"), index=True, nullable=False)
    template_id: Mapped[Optional[int]] = mapped_column(ForeignKey("checklist_templates.id"), nullable=True)
    task_type: Mapped[HousekeepingTaskType] = mapped_column(Enum(HousekeepingTaskType), nullable=False)
    status: Mapped[HousekeepingTaskStatus] = mapped_column(
        Enum(HousekeepingTaskStatus), default=HousekeepingTaskStatus.PENDING
    )
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    priority: Mapped[MaintenancePriority] = mapped_column(
        Enum(MaintenancePriority), default=MaintenancePriority.MEDIUM
    )
    due_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    verified_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room: Mapped["HotelRoom"] = relationship(back_populates="tasks")
    checklist_items: Mapped[list["TaskChecklistItem"]] = relationship(
        back_populates="task",
        cascade="all, delete-orphan",
        order_by="TaskChecklistItem.sort_order",
    )


class TaskChecklistItem(Base, BaseMixin):
    __tablename__ = "task_checklist_items"

    task_id: Mapped[int] = mapped_column(ForeignKey("housekeeping_tasks.id"), index=True, nullable=False)
    label: Mapped[str] = mapped_column(String(255), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    is_checked: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    checked_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    checked_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    task: Mapped["HousekeepingTask"] = relationship(back_populates="checklist_items")


class MaintenanceTicket(Base, BaseMixin, TenantBrandMixin):
    """Work order ticket for room maintenance issues."""

    __tablename__ = "maintenance_tickets"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("hotel_rooms.id"), index=True, nullable=False)
    ticket_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    category: Mapped[MaintenanceCategory] = mapped_column(Enum(MaintenanceCategory), nullable=False)
    priority: Mapped[MaintenancePriority] = mapped_column(
        Enum(MaintenancePriority), default=MaintenancePriority.MEDIUM
    )
    status: Mapped[MaintenanceTicketStatus] = mapped_column(
        Enum(MaintenanceTicketStatus), default=MaintenanceTicketStatus.OPEN
    )
    reported_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    due_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    resolution_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room: Mapped["HotelRoom"] = relationship(back_populates="tickets")
    comments: Mapped[list["TicketComment"]] = relationship(
        back_populates="ticket",
        cascade="all, delete-orphan",
        order_by="TicketComment.created_at.desc()",
    )


class TicketComment(Base, BaseMixin):
    __tablename__ = "ticket_comments"

    ticket_id: Mapped[int] = mapped_column(ForeignKey("maintenance_tickets.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)
    comment: Mapped[str] = mapped_column(Text, nullable=False)

    ticket: Mapped["MaintenanceTicket"] = relationship(back_populates="comments")


class HousekeepingFloorAssignment(Base, BaseMixin):
    """Permanent floor → housekeeper mapping per outlet."""

    __tablename__ = "housekeeping_floor_assignments"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    floor: Mapped[str] = mapped_column(String(16), nullable=False)
    housekeeper_id: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)


class HousekeepingSweepSchedule(Base, BaseMixin, TenantBrandMixin):
    """Daily automated sweep configuration (run via API or Celery Beat)."""

    __tablename__ = "housekeeping_sweep_schedules"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    sweep_type: Mapped[str] = mapped_column(String(16), nullable=False)
    run_time: Mapped[str] = mapped_column(String(5), nullable=False, default="06:00")
    enabled: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    distribute_by_floor: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    use_floor_assignments: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    last_run_date: Mapped[Optional[date]] = mapped_column(Date, nullable=True)
