from __future__ import annotations

from typing import Optional

from sqlalchemy import Enum, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, RecordStatus


class Brand(Base, BaseMixin):
    __tablename__ = "brands"

    tenant_id: Mapped[int] = mapped_column(ForeignKey("tenants.id"), index=True, nullable=False)
    brand_name: Mapped[str] = mapped_column(String(255), nullable=False)
    gst_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    fssai_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    support_number: Mapped[Optional[str]] = mapped_column(String(32), nullable=True)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    logo_url: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    status: Mapped[RecordStatus] = mapped_column(
        Enum(RecordStatus), default=RecordStatus.ACTIVE, nullable=False
    )

    tenant: Mapped["Tenant"] = relationship(back_populates="brands")
    outlets: Mapped[list["Outlet"]] = relationship(back_populates="brand")
