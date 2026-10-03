from __future__ import annotations

from typing import Optional

import enum
from datetime import date, datetime

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class EventType(str, enum.Enum):
    BIRTHDAY = "birthday"
    ANNIVERSARY = "anniversary"
    CORPORATE = "corporate"
    PRIVATE_DINING = "private_dining"
    KIDS_PARTY = "kids_party"
    CELEBRATION = "celebration"
    CUSTOM = "custom"


class EventStatus(str, enum.Enum):
    INQUIRY = "inquiry"
    QUOTED = "quoted"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class EventSource(str, enum.Enum):
    WALK_IN = "walk_in"
    PHONE = "phone"
    WHATSAPP = "whatsapp"
    WEBSITE = "website"
    LEAD = "lead"
    OTHER = "other"


class EventActivityType(str, enum.Enum):
    NOTE = "note"
    CALL = "call"
    WHATSAPP = "whatsapp"
    STATUS_CHANGE = "status_change"
    PAYMENT = "payment"


class RestaurantEvent(Base, BaseMixin, TenantBrandMixin):
    """A planned restaurant event such as a birthday party or private dining."""

    __tablename__ = "restaurant_events"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    lead_id: Mapped[Optional[int]] = mapped_column(ForeignKey("leads.id"), nullable=True, index=True)
    booking_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("table_bookings.id"), nullable=True, index=True
    )
    pos_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pos_orders.id"), nullable=True, index=True
    )
    offer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("offers.id"), nullable=True)

    event_type: Mapped[EventType] = mapped_column(Enum(EventType), nullable=False)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_of_honor: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)
    end_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=180, nullable=False)

    expected_guests: Mapped[int] = mapped_column(Integer, default=10, nullable=False)
    confirmed_guests: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    status: Mapped[EventStatus] = mapped_column(Enum(EventStatus), default=EventStatus.INQUIRY)
    source: Mapped[EventSource] = mapped_column(Enum(EventSource), default=EventSource.WALK_IN)
    assigned_to: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)

    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    decoration_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    dietary_notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    estimated_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    advance_paid: Mapped[float] = mapped_column(Numeric(12, 2), default=0)

    table_assignments: Mapped[list["EventTableAssignment"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )
    activities: Mapped[list["EventActivity"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
        order_by="EventActivity.created_at.desc()",
    )
    preorders: Mapped[list["EventPreOrderItem"]] = relationship(
        back_populates="event",
        cascade="all, delete-orphan",
    )


class EventPreOrderItem(Base, BaseMixin):
    """Menu items pre-ordered for an event."""

    __tablename__ = "event_preorder_items"

    event_id: Mapped[int] = mapped_column(ForeignKey("restaurant_events.id"), index=True, nullable=False)
    menu_item_id: Mapped[int] = mapped_column(ForeignKey("menu_items.id"), index=True, nullable=False)
    item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), default=0)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    event: Mapped["RestaurantEvent"] = relationship(back_populates="preorders")


class EventTableAssignment(Base, BaseMixin):
    __tablename__ = "event_table_assignments"

    event_id: Mapped[int] = mapped_column(ForeignKey("restaurant_events.id"), index=True, nullable=False)
    table_id: Mapped[int] = mapped_column(ForeignKey("restaurant_tables.id"), index=True, nullable=False)
    reserved_from: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    reserved_until: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    event: Mapped["RestaurantEvent"] = relationship(back_populates="table_assignments")


class EventActivity(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "event_activities"

    event_id: Mapped[int] = mapped_column(ForeignKey("restaurant_events.id"), index=True, nullable=False)
    activity_type: Mapped[EventActivityType] = mapped_column(Enum(EventActivityType))
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_by: Mapped[int] = mapped_column(ForeignKey("users.id"), nullable=False)

    event: Mapped["RestaurantEvent"] = relationship(back_populates="activities")
