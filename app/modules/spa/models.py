from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class SpaServiceCategory(str, enum.Enum):
    SPA = "spa"
    ACTIVITY = "activity"


class SpaBookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"


class SpaService(Base, BaseMixin, TenantBrandMixin):
    """Bookable spa treatment or resort activity."""

    __tablename__ = "spa_services"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    category: Mapped[SpaServiceCategory] = mapped_column(Enum(SpaServiceCategory), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)
    max_capacity: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    slot_interval_minutes: Mapped[int] = mapped_column(Integer, default=30, nullable=False)
    operating_start: Mapped[str] = mapped_column(String(8), default="09:00", nullable=False)
    operating_end: Mapped[str] = mapped_column(String(8), default="21:00", nullable=False)

    bookings: Mapped[list["SpaBooking"]] = relationship(back_populates="service")


class SpaBooking(Base, BaseMixin, TenantBrandMixin):
    """Scheduled spa or activity appointment."""

    __tablename__ = "spa_bookings"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    service_id: Mapped[int] = mapped_column(ForeignKey("spa_services.id"), index=True, nullable=False)
    booking_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    status: Mapped[SpaBookingStatus] = mapped_column(
        Enum(SpaBookingStatus), default=SpaBookingStatus.PENDING
    )
    booked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False, index=True)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=60, nullable=False)
    party_size: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    price: Mapped[float] = mapped_column(Numeric(10, 2), default=0, nullable=False)

    guest_name: Mapped[str] = mapped_column(String(255), nullable=False)
    guest_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    guest_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_id: Mapped[Optional[int]] = mapped_column(ForeignKey("customers.id"), nullable=True, index=True)
    guest_reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("guest_reservations.id"), nullable=True, index=True
    )
    assigned_staff_id: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True, index=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    charge_to_folio: Mapped[bool] = mapped_column(default=True, nullable=False)
    folio_posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    service: Mapped["SpaService"] = relationship(back_populates="bookings")


class SpaTherapist(Base, BaseMixin, TenantBrandMixin):
    """Spa therapist or activity guide roster entry."""

    __tablename__ = "spa_therapists"
    __table_args__ = (
        UniqueConstraint("tenant_id", "outlet_id", "user_id", name="uq_spa_therapist_tenant_outlet_user"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    title: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    specialties: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    shift_start: Mapped[str] = mapped_column(String(8), default="09:00", nullable=False)
    shift_end: Mapped[str] = mapped_column(String(8), default="18:00", nullable=False)
    calendar_color: Mapped[str] = mapped_column(String(7), default="#8b5cf6", nullable=False)
