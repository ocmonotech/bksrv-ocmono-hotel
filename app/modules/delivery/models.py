from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, Enum, ForeignKey, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class DeliveryPlatform(str, enum.Enum):
    ZOMATO = "zomato"
    SWIGGY = "swiggy"
    ONDC = "ondc"
    DUNZO = "dunzo"
    MAGICPIN = "magicpin"


class IntegrationStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    PENDING = "pending"
    ERROR = "error"


class ExternalOrderStatus(str, enum.Enum):
    RECEIVED = "received"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    PICKED_UP = "picked_up"
    DELIVERED = "delivered"
    CANCELLED = "cancelled"
    REJECTED = "rejected"


class OutletDeliveryIntegration(Base, BaseMixin, TenantBrandMixin):
    """Per-outlet connection to a food delivery aggregator."""

    __tablename__ = "outlet_delivery_integrations"
    __table_args__ = (
        UniqueConstraint("outlet_id", "platform", name="uq_outlet_delivery_platform"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    platform: Mapped[DeliveryPlatform] = mapped_column(Enum(DeliveryPlatform), nullable=False)
    external_store_id: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    status: Mapped[IntegrationStatus] = mapped_column(
        Enum(IntegrationStatus), default=IntegrationStatus.PENDING, nullable=False
    )
    is_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_accept_orders: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    auto_send_kot: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    webhook_token: Mapped[str] = mapped_column(String(64), unique=True, index=True, nullable=False)
    config_json: Mapped[str] = mapped_column(Text, default="{}")
    encrypted_api_key: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    encrypted_webhook_secret: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    last_sync_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_error: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    menu_mappings: Mapped[list["DeliveryMenuMapping"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )
    order_links: Mapped[list["DeliveryOrderLink"]] = relationship(
        back_populates="integration",
        cascade="all, delete-orphan",
    )


class DeliveryMenuMapping(Base, BaseMixin, TenantBrandMixin):
    """Maps aggregator menu item IDs to internal menu items."""

    __tablename__ = "delivery_menu_mappings"
    __table_args__ = (
        UniqueConstraint(
            "integration_id",
            "external_item_id",
            name="uq_delivery_menu_external_item",
        ),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_delivery_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    external_item_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_item_name: Mapped[str] = mapped_column(String(255), nullable=False)
    menu_item_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("menu_items.id"), index=True, nullable=True
    )

    integration: Mapped["OutletDeliveryIntegration"] = relationship(back_populates="menu_mappings")


class DeliveryOrderLink(Base, BaseMixin, TenantBrandMixin):
    """Links an aggregator order to an internal POS order."""

    __tablename__ = "delivery_order_links"
    __table_args__ = (
        UniqueConstraint("integration_id", "external_order_id", name="uq_delivery_external_order"),
    )

    integration_id: Mapped[int] = mapped_column(
        ForeignKey("outlet_delivery_integrations.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    pos_order_id: Mapped[int] = mapped_column(
        ForeignKey("pos_orders.id", ondelete="CASCADE"), index=True, nullable=False
    )
    platform: Mapped[DeliveryPlatform] = mapped_column(Enum(DeliveryPlatform), nullable=False)
    external_order_id: Mapped[str] = mapped_column(String(128), nullable=False)
    external_status: Mapped[ExternalOrderStatus] = mapped_column(
        Enum(ExternalOrderStatus), default=ExternalOrderStatus.RECEIVED, nullable=False
    )
    customer_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    customer_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    delivery_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    rider_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    rider_phone: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    raw_payload_json: Mapped[str] = mapped_column(Text, default="{}")
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    integration: Mapped["OutletDeliveryIntegration"] = relationship(back_populates="order_links")
