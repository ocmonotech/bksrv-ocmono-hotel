from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import Boolean, Date, DateTime, Enum, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin
from app.modules.delivery.models import IntegrationStatus


class OtaPlatform(str, enum.Enum):
    BOOKING_COM = "booking_com"
    MMT = "mmt"
    EXPEDIA = "expedia"


class OtaSyncType(str, enum.Enum):
    ARI_PUSH = "ari_push"
    RESERVATION_PULL = "reservation_pull"


class OtaSyncStatus(str, enum.Enum):
    SUCCESS = "success"
    FAILED = "failed"


class OutletOtaIntegration(Base, BaseMixin, TenantBrandMixin):
    """Per-outlet connection to a hotel OTA channel."""

    __tablename__ = "outlet_ota_integrations"
    __table_args__ = (
        UniqueConstraint("outlet_id", "platform", name="uq_outlet_ota_platform"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    platform: Mapped[OtaPlatform] = mapped_column(Enum(OtaPlatform), nullable=False)
    external_property_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus), default=IntegrationStatus.PENDING, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_confirm_reservations: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    auto_push_availability: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    room_mappings: Mapped[list["OtaRoomTypeMapping"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    rate_plan_mappings: Mapped[list["OtaRatePlanMapping"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    reservation_links: Mapped[list["OtaReservationLink"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    sync_logs: Mapped[list["OtaSyncLog"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class OtaRoomTypeMapping(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ota_room_type_mappings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_room_type_id",
            name="uq_ota_room_type_external",
        ),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_ota_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    external_room_type_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_room_type_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    room_type_id: Mapped[int] = mapped_column(ForeignKey("room_types.id"), index=True, nullable=False)

    integration: Mapped["OutletOtaIntegration"] = relationship(back_populates="room_mappings")


class OtaRatePlanMapping(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ota_rate_plan_mappings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_rate_id",
            name="uq_ota_rate_plan_external",
        ),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_ota_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    rate_plan_id: Mapped[int] = mapped_column(ForeignKey("rate_plans.id"), index=True, nullable=False)
    external_rate_id: Mapped[str] = mapped_column(String(64), nullable=False)
    external_rate_name: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)

    integration: Mapped["OutletOtaIntegration"] = relationship(back_populates="rate_plan_mappings")


class OtaReservationLink(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ota_reservation_links"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_reservation_id",
            name="uq_ota_external_reservation",
        ),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_ota_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    guest_reservation_id: Mapped[int] = mapped_column(
        ForeignKey("guest_reservations.id"),
        unique=True,
        index=True,
        nullable=False,
    )
    platform: Mapped[OtaPlatform] = mapped_column(Enum(OtaPlatform), nullable=False)
    external_reservation_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_status: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}")

    integration: Mapped["OutletOtaIntegration"] = relationship(back_populates="reservation_links")


class OtaSyncLog(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "ota_sync_logs"

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_ota_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    sync_type: Mapped[OtaSyncType] = mapped_column(Enum(OtaSyncType), nullable=False)
    status: Mapped[OtaSyncStatus] = mapped_column(Enum(OtaSyncStatus), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date] = mapped_column(Date, nullable=False)
    room_types_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    days_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    external_reference: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    message: Mapped[str] = mapped_column(String(512), nullable=False)
    summary_json: Mapped[str] = mapped_column(Text, default="{}")

    integration: Mapped["OutletOtaIntegration"] = relationship(back_populates="sync_logs")
