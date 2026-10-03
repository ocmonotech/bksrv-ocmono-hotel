"""Staff roster + tip pools + POS tip_amount.

Revision ID: k4e5f6a7b8c9
Revises: j3d4e5f6a7b8
Create Date: 2026-07-14 14:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "k4e5f6a7b8c9"
down_revision: Union[str, None] = "j3d4e5f6a7b8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if _has_table("pos_payments") and not _has_column("pos_payments", "tip_amount"):
        op.add_column(
            "pos_payments",
            sa.Column("tip_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
        )

    if not _has_table("staff_shifts"):
        op.create_table(
            "staff_shifts",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("role_type", sa.String(16), nullable=False, index=True),
            sa.Column("shift_date", sa.Date(), nullable=False, index=True),
            sa.Column("start_at", sa.DateTime(), nullable=False),
            sa.Column("end_at", sa.DateTime(), nullable=False),
            sa.Column("notes", sa.String(255), nullable=True),
            sa.Column("tip_eligible", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )

    if not _has_table("tip_pools"):
        op.create_table(
            "tip_pools",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
            sa.Column("shift_date", sa.Date(), nullable=False, index=True),
            sa.Column("status", sa.String(16), nullable=False, index=True),
            sa.Column("expected_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("declared_amount", sa.Numeric(12, 2), nullable=True),
            sa.Column("pool_amount", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("variance", sa.Numeric(12, 2), nullable=True),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("settled_at", sa.DateTime(), nullable=True),
            sa.Column("settled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.UniqueConstraint("tenant_id", "outlet_id", "shift_date", name="uq_tip_pool_tenant_outlet_date"),
        )

    if not _has_table("tip_pool_lines"):
        op.create_table(
            "tip_pool_lines",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column(
                "tip_pool_id",
                sa.Integer(),
                sa.ForeignKey("tip_pools.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column("user_id", sa.Integer(), sa.ForeignKey("users.id"), nullable=False, index=True),
            sa.Column("role_type", sa.String(16), nullable=True),
            sa.Column("share_percent", sa.Numeric(7, 3), nullable=True),
            sa.Column("amount", sa.Numeric(12, 2), nullable=False),
            sa.Column(
                "staff_shift_id",
                sa.Integer(),
                sa.ForeignKey("staff_shifts.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
        )


def downgrade() -> None:
    if _has_table("tip_pool_lines"):
        op.drop_table("tip_pool_lines")
    if _has_table("tip_pools"):
        op.drop_table("tip_pools")
    if _has_table("staff_shifts"):
        op.drop_table("staff_shifts")
    if _has_table("pos_payments") and _has_column("pos_payments", "tip_amount"):
        op.drop_column("pos_payments", "tip_amount")
