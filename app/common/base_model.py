from __future__ import annotations

from typing import Optional

import enum
from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column


class Base(DeclarativeBase):
    """SQLAlchemy declarative base for all module models."""


class BaseMixin:
    """Shared primary key, timestamps, and soft-active flag for MySQL models."""

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime,
        server_default=func.now(),
        server_onupdate=func.now(),
        nullable=False,
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean,
        nullable=False,
        default=True,
        server_default="1",
    )


class TenantBrandMixin:
    """Standard SaaS scoping columns for tenant-isolated business data."""

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    brand_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("brands.id"), nullable=True, index=True
    )


class RecordStatus(str, enum.Enum):
    ACTIVE = "active"
    INACTIVE = "inactive"
    TRIAL = "trial"
    SUSPENDED = "suspended"


def apply_record_status(record, status: RecordStatus) -> None:
    record.status = status
    record.is_active = status == RecordStatus.ACTIVE
