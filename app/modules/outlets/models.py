from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, RecordStatus


class Outlet(Base, BaseMixin):
    __tablename__ = "outlets"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"), index=True, nullable=False)
    outlet_name: Mapped[str] = mapped_column(String(255), nullable=False)
    location: Mapped[str] = mapped_column(String(128), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    manager_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    manager_mobile: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    opening_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    closing_time: Mapped[Optional[str]] = mapped_column(String(8), nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), default=RecordStatus.ACTIVE, nullable=False
    )
    gst_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fssai_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)

    tenant: Mapped["Tenant"] = relationship(back_populates="outlets")
    brand: Mapped["Brand"] = relationship(back_populates="outlets")
