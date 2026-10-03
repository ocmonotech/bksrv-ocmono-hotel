from __future__ import annotations

from typing import Optional

import enum

from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin
from app.modules.menu.models import PreparationArea


class KotStatus(str, enum.Enum):
    NEW = "new"
    ACCEPTED = "accepted"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"


class KotItemStatus(str, enum.Enum):
    NEW = "new"
    PREPARING = "preparing"
    READY = "ready"
    SERVED = "served"
    CANCELLED = "cancelled"


class KOT(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "kots"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("pos_orders.id"), index=True)
    kot_number: Mapped[str] = mapped_column(String(32), index=True)
    preparation_area: Mapped[PreparationArea] = mapped_column(
        Enum(PreparationArea), default=PreparationArea.KITCHEN
    )
    status: Mapped[KotStatus] = mapped_column(Enum(KotStatus), default=KotStatus.NEW)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    items: Mapped[list["KOTItem"]] = relationship(
        back_populates="kot",
        cascade="all, delete-orphan",
    )


class KOTItem(Base):
    __tablename__ = "kot_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    kot_id: Mapped[int] = mapped_column(ForeignKey("kots.id", ondelete="CASCADE"), index=True)
    order_item_id: Mapped[int] = mapped_column(ForeignKey("pos_order_items.id"), index=True)
    item_name: Mapped[str] = mapped_column(String(255))
    quantity: Mapped[int] = mapped_column(Integer, default=1)
    note: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[KotItemStatus] = mapped_column(Enum(KotItemStatus), default=KotItemStatus.NEW)

    kot: Mapped["KOT"] = relationship(back_populates="items")


# Backward-compatible alias
KotTicket = KOT
