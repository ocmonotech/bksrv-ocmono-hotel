from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import DateTime, Enum, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class TableStatus(str, enum.Enum):
    AVAILABLE = "available"
    OCCUPIED = "occupied"
    RESERVED = "reserved"
    BILLING = "billing"
    CLEANING = "cleaning"


class Floor(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "floors"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sort_order: Mapped[int] = mapped_column(Integer, default=0)

    tables: Mapped[list["RestaurantTable"]] = relationship(back_populates="floor")


class RestaurantTable(Base, BaseMixin, TenantBrandMixin):
    __tablename__ = "restaurant_tables"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True)
    floor_id: Mapped[Optional[int]] = mapped_column(ForeignKey("floors.id"), nullable=True, index=True)
    table_number: Mapped[str] = mapped_column(String(32), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, default=4)
    status: Mapped[TableStatus] = mapped_column(Enum(TableStatus), default=TableStatus.AVAILABLE)
    assigned_waiter_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("users.id"), nullable=True, index=True
    )
    current_order_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("pos_orders.id"), nullable=True, index=True
    )
    occupied_since: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    floor: Mapped["Floor | None"] = relationship(back_populates="tables")
