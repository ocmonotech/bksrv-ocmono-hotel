"""Amenity catalog and room-type amenity links."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "e8f9a0b1c2d3"
down_revision: Union[str, None] = "d7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if not _has_table("amenities"):
        op.create_table(
            "amenities",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("name", sa.String(100), nullable=False),
            sa.Column("code", sa.String(64), nullable=False),
            sa.Column("category", sa.String(32), nullable=False, server_default="other"),
            sa.Column("icon", sa.String(64), nullable=True),
            sa.Column("description", sa.String(255), nullable=True),
            sa.Column("sort_order", sa.Integer(), nullable=False, server_default="0"),
            sa.UniqueConstraint("tenant_id", "code", name="uq_amenities_tenant_code"),
        )
        op.create_index("ix_amenities_category", "amenities", ["category"])

    if not _has_table("room_type_amenities"):
        op.create_table(
            "room_type_amenities",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("room_type_id", sa.Integer(), sa.ForeignKey("room_types.id"), nullable=False, index=True),
            sa.Column("amenity_id", sa.Integer(), sa.ForeignKey("amenities.id"), nullable=False, index=True),
            sa.UniqueConstraint("room_type_id", "amenity_id", name="uq_room_type_amenity"),
        )


def downgrade() -> None:
    if _has_table("room_type_amenities"):
        op.drop_table("room_type_amenities")
    if _has_table("amenities"):
        op.drop_table("amenities")
