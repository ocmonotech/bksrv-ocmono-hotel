"""Dated staff shifts and tip pool settlement."""

from __future__ import annotations

import enum
from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean,
    Date,
    DateTime,
    Enum,
    ForeignKey,
    Numeric,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class StaffRoleType(str, enum.Enum):
    WAITER = "waiter"
    HK = "hk"
    SPA = "spa"
    FRONT_DESK = "front_desk"
    KITCHEN = "kitchen"
    OTHER = "other"


class TipPoolStatus(str, enum.Enum):
    OPEN = "open"
    DISTRIBUTED = "distributed"
    CLOSED = "closed"


class StaffShift(Base, BaseMixin, TenantBrandMixin):
    """One person's scheduled / clocked shift for a business day."""

    __tablename__ = "staff_shifts"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    role_type: Mapped[StaffRoleType] = mapped_column(
        Enum(StaffRoleType, native_enum=False, length=16),
        default=StaffRoleType.WAITER,
        nullable=False,
        index=True,
    )
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    start_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    end_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    tip_eligible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)


class TipPool(Base, BaseMixin, TenantBrandMixin):
    """Daily tip pot for an outlet — collected from POS tips then distributed."""

    __tablename__ = "tip_pools"
    __table_args__ = (
        UniqueConstraint("tenant_id", "outlet_id", "shift_date", name="uq_tip_pool_tenant_outlet_date"),
    )

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    shift_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    status: Mapped[TipPoolStatus] = mapped_column(
        Enum(TipPoolStatus, native_enum=False, length=16),
        default=TipPoolStatus.OPEN,
        nullable=False,
        index=True,
    )
    expected_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    declared_amount: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    pool_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    variance: Mapped[Optional[float]] = mapped_column(Numeric(12, 2), nullable=True)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    settled_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    settled_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)

    lines: Mapped[list["TipPoolLine"]] = relationship(
        back_populates="tip_pool",
        cascade="all, delete-orphan",
    )


class TipPoolLine(Base, BaseMixin):
    __tablename__ = "tip_pool_lines"

    tip_pool_id: Mapped[int] = mapped_column(
        ForeignKey("tip_pools.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id"), index=True, nullable=False)
    role_type: Mapped[Optional[StaffRoleType]] = mapped_column(
        Enum(StaffRoleType, native_enum=False, length=16),
        nullable=True,
    )
    share_percent: Mapped[Optional[float]] = mapped_column(Numeric(7, 3), nullable=True)
    amount: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    staff_shift_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("staff_shifts.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )

    tip_pool: Mapped["TipPool"] = relationship(back_populates="lines")
