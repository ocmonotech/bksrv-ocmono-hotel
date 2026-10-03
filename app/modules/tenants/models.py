from __future__ import annotations

from typing import Optional

from datetime import datetime

from sqlalchemy import DateTime, Enum, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, RecordStatus
from app.modules.tenants.enums import BusinessType


class Tenant(Base, BaseMixin):
    __tablename__ = "tenants"

    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    owner_name: Mapped[str] = mapped_column(String(255), nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    mobile: Mapped[str] = mapped_column(String(32), nullable=False)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), default=RecordStatus.TRIAL, nullable=False
    )
    subscription_plan: Mapped[str] = mapped_column(String(64), default="trial")
    trial_ends_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    business_type: Mapped[BusinessType] = mapped_column(
        Enum(BusinessType),
        default=BusinessType.RESORT,
        nullable=False,
    )

    brands: Mapped[list["Brand"]] = relationship(back_populates="tenant")
    outlets: Mapped[list["Outlet"]] = relationship(back_populates="tenant")
