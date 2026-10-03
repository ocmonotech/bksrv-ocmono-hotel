"""Stay package credits and entitlements.

Revision ID: h1b2c3d4e5f6
Revises: g0a1b2c3d4e5
Create Date: 2026-07-14 11:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "h1b2c3d4e5f6"
down_revision: Union[str, None] = "g0a1b2c3d4e5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE rate_plan_inclusions MODIFY inclusion_type "
            "ENUM('BREAKFAST','LUNCH','DINNER','CAFE','SPA','PARKING','OTHER') NOT NULL"
        )
        op.execute(
            "ALTER TABLE folio_entries MODIFY entry_type "
            "ENUM('ROOM_CHARGE','TAX','DEPOSIT','PAYMENT','POS_CHARGE','SPA_CHARGE',"
            "'BANQUET_CHARGE','ADJUSTMENT','REFUND','PACKAGE_CREDIT') NOT NULL"
        )
    elif _has_table("rate_plan_inclusions"):
        # Non-MySQL: recreate enum if needed via batch alter is dialect-specific; columns below are enough.
        pass

    if _has_table("rate_plan_inclusions"):
        if not _has_column("rate_plan_inclusions", "credit_amount"):
            op.add_column(
                "rate_plan_inclusions",
                sa.Column("credit_amount", sa.Numeric(10, 2), server_default="0", nullable=False),
            )
        if not _has_column("rate_plan_inclusions", "credit_scope"):
            op.add_column(
                "rate_plan_inclusions",
                sa.Column("credit_scope", sa.String(16), server_default="stay", nullable=False),
            )
        if not _has_column("rate_plan_inclusions", "qty_per_stay"):
            op.add_column(
                "rate_plan_inclusions",
                sa.Column("qty_per_stay", sa.Integer(), server_default="0", nullable=False),
            )
        if not _has_column("rate_plan_inclusions", "qty_per_night"):
            op.add_column(
                "rate_plan_inclusions",
                sa.Column("qty_per_night", sa.Integer(), server_default="0", nullable=False),
            )

    if not _has_table("reservation_package_entitlements"):
        op.create_table(
            "reservation_package_entitlements",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column(
                "reservation_id",
                sa.Integer(),
                sa.ForeignKey("guest_reservations.id", ondelete="CASCADE"),
                nullable=False,
                index=True,
            ),
            sa.Column(
                "source_inclusion_id",
                sa.Integer(),
                sa.ForeignKey("rate_plan_inclusions.id", ondelete="SET NULL"),
                nullable=True,
                index=True,
            ),
            sa.Column("inclusion_type", sa.String(32), nullable=False),
            sa.Column("name", sa.String(128), nullable=False),
            sa.Column("credit_total", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("credit_used", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("qty_total", sa.Integer(), server_default="0", nullable=False),
            sa.Column("qty_used", sa.Integer(), server_default="0", nullable=False),
        )


def downgrade() -> None:
    if _has_table("reservation_package_entitlements"):
        op.drop_table("reservation_package_entitlements")

    if _has_table("rate_plan_inclusions"):
        if _has_column("rate_plan_inclusions", "qty_per_night"):
            op.drop_column("rate_plan_inclusions", "qty_per_night")
        if _has_column("rate_plan_inclusions", "qty_per_stay"):
            op.drop_column("rate_plan_inclusions", "qty_per_stay")
        if _has_column("rate_plan_inclusions", "credit_scope"):
            op.drop_column("rate_plan_inclusions", "credit_scope")
        if _has_column("rate_plan_inclusions", "credit_amount"):
            op.drop_column("rate_plan_inclusions", "credit_amount")

    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            "ALTER TABLE rate_plan_inclusions MODIFY inclusion_type "
            "ENUM('BREAKFAST','SPA','PARKING','OTHER') NOT NULL"
        )
        op.execute(
            "ALTER TABLE folio_entries MODIFY entry_type "
            "ENUM('ROOM_CHARGE','TAX','DEPOSIT','PAYMENT','POS_CHARGE','SPA_CHARGE',"
            "'BANQUET_CHARGE','ADJUSTMENT','REFUND') NOT NULL"
        )
