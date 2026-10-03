from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Date, DateTime, Enum, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class BanquetVenueType(str, enum.Enum):
    INDOOR = "indoor"
    OUTDOOR = "outdoor"
    LAWN = "lawn"
    CONFERENCE = "conference"
    POOL_DECK = "pool_deck"


class BanquetEventType(str, enum.Enum):
    WEDDING = "wedding"
    CONFERENCE = "conference"
    RECEPTION = "reception"
    CORPORATE = "corporate"
    SOCIAL = "social"
    OTHER = "other"


class BanquetBookingStatus(str, enum.Enum):
    INQUIRY = "inquiry"
    TENTATIVE = "tentative"
    CONFIRMED = "confirmed"
    COMPLETED = "completed"
    CANCELLED = "cancelled"


class BanquetVenue(Base, BaseMixin, TenantBrandMixin):
    """Bookable banquet hall or event space."""

    __tablename__ = "banquet_venues"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    venue_type: Mapped[BanquetVenueType] = mapped_column(Enum(BanquetVenueType), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    capacity_min: Mapped[int] = mapped_column(Integer, default=20, nullable=False)
    capacity_max: Mapped[int] = mapped_column(Integer, default=200, nullable=False)
    half_day_rate: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    full_day_rate: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    amenities: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)

    bookings: Mapped[list["BanquetBooking"]] = relationship(back_populates="venue")


class BanquetBooking(Base, BaseMixin, TenantBrandMixin):
    """Banquet or MICE event booking."""

    __tablename__ = "banquet_bookings"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    venue_id: Mapped[int] = mapped_column(ForeignKey("banquet_venues.id"), index=True, nullable=False)
    booking_number: Mapped[str] = mapped_column(String(32), nullable=False, unique=True, index=True)
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    event_type: Mapped[BanquetEventType] = mapped_column(Enum(BanquetEventType), nullable=False)
    status: Mapped[BanquetBookingStatus] = mapped_column(
        Enum(BanquetBookingStatus), default=BanquetBookingStatus.INQUIRY
    )
    event_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_time: Mapped[str] = mapped_column(String(8), nullable=False)
    end_time: Mapped[str] = mapped_column(String(8), nullable=False)
    guest_count: Mapped[int] = mapped_column(Integer, default=50, nullable=False)
    contact_name: Mapped[str] = mapped_column(String(255), nullable=False)
    contact_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    contact_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_reservation_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("guest_reservations.id"), nullable=True, index=True
    )
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    estimated_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    advance_paid: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    charge_to_folio: Mapped[bool] = mapped_column(default=True, nullable=False)
    folio_posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    deposit_folio_posted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    reminder_sent_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    cancelled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    venue: Mapped["BanquetVenue"] = relationship(back_populates="bookings")
