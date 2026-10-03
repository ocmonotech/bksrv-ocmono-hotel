from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin
from app.modules.delivery.models import IntegrationStatus


class BookingPlatform(str, enum.Enum):
    ZOMATO = "zomato"
    SWIGGY_DINEOUT = "swiggy_dineout"
    EAZYDINER = "eazydiner"
    DINEOUT = "dineout"
    GOOGLE = "google"
    DIRECT = "direct"


class BookingStatus(str, enum.Enum):
    PENDING = "pending"
    CONFIRMED = "confirmed"
    SEATED = "seated"
    COMPLETED = "completed"
    CANCELLED = "cancelled"
    NO_SHOW = "no_show"
    REJECTED = "rejected"


class OutletBookingIntegration(Base, BaseMixin, TenantBrandMixin):
    """Per-outlet connection to a table-booking platform."""

    __tablename__ = "outlet_booking_integrations"
    __table_args__ = (
        UniqueConstraint("outlet_id", "platform", name="uq_outlet_booking_platform"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    platform: Mapped[BookingPlatform] = mapped_column(Enum(BookingPlatform), nullable=False)
    external_store_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus), default=IntegrationStatus.PENDING, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_confirm_bookings: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_reserve_table: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    bookings: Mapped[list["TableBooking"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class TableBooking(Base, BaseMixin, TenantBrandMixin):
    """A table reservation from an aggregator or created in-house."""

    __tablename__ = "table_bookings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_booking_id",
            name="uq_booking_external_id",
        ),
    )

    integration_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("outlet_booking_integrations.id", ondelete="SET NULL"),
        index=True,
        nullable=True,
    )
    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    platform: Mapped[BookingPlatform] = mapped_column(Enum(BookingPlatform), nullable=False)
    external_booking_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[BookingStatus] = mapped_column(
        Enum(BookingStatus), default=BookingStatus.PENDING, nullable=False
    )
    customer_name: Mapped[str] = mapped_column(String(255), nullable=False)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    customer_email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    guest_count: Mapped[int] = mapped_column(Integer, default=2, nullable=False)
    booked_for: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_minutes: Mapped[int] = mapped_column(Integer, default=90, nullable=False)
    table_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("restaurant_tables.id"), index=True, nullable=True
    )
    special_requests: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}")

    integration: Mapped["OutletBookingIntegration | None"] = relationship(back_populates="bookings")
