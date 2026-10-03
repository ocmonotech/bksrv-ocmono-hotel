"""Minibar catalog and postings.

Revision ID: j3d4e5f6a7b8
Revises: i2c3d4e5f6a7
Create Date: 2026-07-14 13:10:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "j3d4e5f6a7b8"
down_revision: Union[str, None] = "i2c3d4e5f6a7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        try:
            op.execute(
                "ALTER TABLE folio_entries MODIFY entry_type "
                "ENUM('ROOM_CHARGE','TAX','DEPOSIT','PAYMENT','POS_CHARGE','SPA_CHARGE',"
                "'BANQUET_CHARGE','ADJUSTMENT','REFUND','PACKAGE_CREDIT','MINIBAR_CHARGE') NOT NULL"
            )
        except Exception:
            pass

    if not _has_table("minibar_catalog_items"):
        op.create_table(
            "minibar_catalog_items",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=True, index=True),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("sku_code", sa.String(64), nullable=True, index=True),
            sa.Column("barcode", sa.String(64), nullable=True, index=True),
            sa.Column("category", sa.String(64), server_default="general", nullable=False),
            sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("gst_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
            sa.Column("menu_item_id", sa.Integer(), sa.ForeignKey("menu_items.id"), nullable=True, index=True),
            sa.Column(
                "raw_material_id",
                sa.Integer(),
                sa.ForeignKey("raw_materials.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.UniqueConstraint("tenant_id", "sku_code", name="uq_minibar_catalog_tenant_sku"),
        )

    if not _has_table("minibar_postings"):
        op.create_table(
            "minibar_postings",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
            sa.Column("room_id", sa.Integer(), sa.ForeignKey("hotel_rooms.id"), nullable=False, index=True),
            sa.Column(
                "reservation_id",
                sa.Integer(),
                sa.ForeignKey("guest_reservations.id"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "folio_entry_id",
                sa.Integer(),
                sa.ForeignKey("folio_entries.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("status", sa.String(16), server_default="posted", nullable=False, index=True),
            sa.Column("total_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("posted_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("voided_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.Column("void_reason", sa.String(255), nullable=True),
        )

    if not _has_table("minibar_posting_lines"):
        op.create_table(
            "minibar_posting_lines",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column(
                "posting_id",
                sa.Integer(),
                sa.ForeignKey("minibar_postings.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "catalog_item_id",
                sa.Integer(),
                sa.ForeignKey("minibar_catalog_items.id"),
                nullable=False,
                index=True,
            ),
            sa.Column("item_name", sa.String(128), nullable=False),
            sa.Column("quantity", sa.Numeric(12, 3), nullable=False),
            sa.Column("unit_price", sa.Numeric(10, 2), nullable=False),
            sa.Column("line_total", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "raw_material_id",
                sa.Integer(),
                sa.ForeignKey("raw_materials.id"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    if _has_table("minibar_posting_lines"):
        op.drop_table("minibar_posting_lines")
    if _has_table("minibar_postings"):
        op.drop_table("minibar_postings")
    if _has_table("minibar_catalog_items"):
        op.drop_table("minibar_catalog_items")
