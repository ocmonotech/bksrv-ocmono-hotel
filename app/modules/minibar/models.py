"""Minibar / in-room F&B catalog and folio postings."""

from __future__ import annotations

import enum
from typing import Optional

from sqlalchemy import Enum, ForeignKey, Integer, Numeric, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.common.base_model import Base, BaseMixin, TenantBrandMixin


class MinibarPostingStatus(str, enum.Enum):
    POSTED = "posted"
    VOIDED = "voided"


class MinibarCatalogItem(Base, BaseMixin, TenantBrandMixin):
    """Sellable minibar SKU — priced locally, optionally linked to menu/ingredients."""

    __tablename__ = "minibar_catalog_items"
    __table_args__ = (
        UniqueConstraint("tenant_id", "sku_code", name="uq_minibar_catalog_tenant_sku"),
    )

    outlet_id: Mapped[Optional[int]] = mapped_column(ForeignKey("outlets.id"), nullable=True, index=True)
    name: Mapped[str] = mapped_column(String(128), nullable=False)
    sku_code: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    barcode: Mapped[Optional[str]] = mapped_column(String(64), nullable=True, index=True)
    category: Mapped[str] = mapped_column(String(64), default="general", nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    gst_percent: Mapped[float] = mapped_column(Numeric(5, 2), default=0, nullable=False)
    menu_item_id: Mapped[Optional[int]] = mapped_column(ForeignKey("menu_items.id"), nullable=True, index=True)
    raw_material_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("raw_materials.id"), nullable=True, index=True
    )
    sort_order: Mapped[int] = mapped_column(Integer, default=0, nullable=False)


class MinibarPosting(Base, BaseMixin, TenantBrandMixin):
    """One staff minibar charge event against an in-house stay."""

    __tablename__ = "minibar_postings"

    outlet_id: Mapped[int] = mapped_column(ForeignKey("outlets.id"), index=True, nullable=False)
    room_id: Mapped[int] = mapped_column(ForeignKey("hotel_rooms.id"), index=True, nullable=False)
    reservation_id: Mapped[int] = mapped_column(
        ForeignKey("guest_reservations.id"), index=True, nullable=False
    )
    folio_entry_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("folio_entries.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    status: Mapped[MinibarPostingStatus] = mapped_column(
        Enum(MinibarPostingStatus, native_enum=False, length=16),
        default=MinibarPostingStatus.POSTED,
        nullable=False,
        index=True,
    )
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0, nullable=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    posted_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    voided_by: Mapped[Optional[int]] = mapped_column(ForeignKey("users.id"), nullable=True)
    void_reason: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)

    lines: Mapped[list["MinibarPostingLine"]] = relationship(
        back_populates="posting",
        cascade="all, delete-orphan",
    )


class MinibarPostingLine(Base, BaseMixin):
    __tablename__ = "minibar_posting_lines"

    posting_id: Mapped[int] = mapped_column(
        ForeignKey("minibar_postings.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    catalog_item_id: Mapped[int] = mapped_column(
        ForeignKey("minibar_catalog_items.id"),
        index=True,
        nullable=False,
    )
    item_name: Mapped[str] = mapped_column(String(128), nullable=False)
    quantity: Mapped[float] = mapped_column(Numeric(12, 3), nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    line_total: Mapped[float] = mapped_column(Numeric(12, 2), nullable=False)
    raw_material_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("raw_materials.id"), nullable=True, index=True
    )

    posting: Mapped["MinibarPosting"] = relationship(back_populates="lines")
