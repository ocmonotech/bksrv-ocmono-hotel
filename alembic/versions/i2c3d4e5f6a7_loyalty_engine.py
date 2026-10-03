"""Loyalty ledger and tiers.

Revision ID: i2c3d4e5f6a7
Revises: h1b2c3d4e5f6
Create Date: 2026-07-14 12:50:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "i2c3d4e5f6a7"
down_revision: Union[str, None] = "h1b2c3d4e5f6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        # Expand payment modes for loyalty redeem at POS.
        try:
            op.execute(
                "ALTER TABLE pos_payments MODIFY payment_mode "
                "ENUM('cash','upi','card','online','split','room_charge','loyalty') NOT NULL"
            )
        except Exception:
            try:
                op.execute(
                    "ALTER TABLE pos_payments MODIFY payment_mode "
                    "ENUM('CASH','UPI','CARD','ONLINE','SPLIT','ROOM_CHARGE','LOYALTY') NOT NULL"
                )
            except Exception:
                pass

        # Folio tender is often a string/native enum — best-effort extend if present as ENUM.
        try:
            op.execute(
                "ALTER TABLE folio_entries MODIFY entry_type "
                "ENUM('ROOM_CHARGE','TAX','DEPOSIT','PAYMENT','POS_CHARGE','SPA_CHARGE',"
                "'BANQUET_CHARGE','ADJUSTMENT','REFUND','PACKAGE_CREDIT') NOT NULL"
            )
        except Exception:
            pass

    if not _has_table("loyalty_tiers"):
        op.create_table(
            "loyalty_tiers",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("name", sa.String(64), nullable=False),
            sa.Column("code", sa.String(32), nullable=False, index=True),
            sa.Column("min_points", sa.Integer(), server_default="0", nullable=False),
            sa.Column("earn_multiplier", sa.Numeric(5, 2), server_default="1", nullable=False),
            sa.Column("color", sa.String(32), server_default="slate", nullable=False),
            sa.Column("perks", sa.String(255), nullable=True),
            sa.Column("sort_order", sa.Integer(), server_default="0", nullable=False),
            sa.UniqueConstraint("tenant_id", "code", name="uq_loyalty_tier_tenant_code"),
        )

    if not _has_table("loyalty_ledger"):
        op.create_table(
            "loyalty_ledger",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("customer_id", sa.Integer(), sa.ForeignKey("customers.id"), nullable=False, index=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=True, index=True),
            sa.Column("txn_type", sa.String(16), nullable=False, index=True),
            sa.Column("source", sa.String(24), nullable=False, index=True),
            sa.Column("points", sa.Integer(), nullable=False),
            sa.Column("balance_after", sa.Integer(), nullable=False),
            sa.Column("amount_basis", sa.Numeric(12, 2), server_default="0", nullable=False),
            sa.Column("reference_type", sa.String(32), nullable=False),
            sa.Column("reference_id", sa.String(64), nullable=False),
            sa.Column("description", sa.String(255), nullable=False),
            sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
            sa.UniqueConstraint(
                "tenant_id",
                "source",
                "reference_type",
                "reference_id",
                "txn_type",
                name="uq_loyalty_ledger_idempotent",
            ),
        )


def downgrade() -> None:
    if _has_table("loyalty_ledger"):
        op.drop_table("loyalty_ledger")
    if _has_table("loyalty_tiers"):
        op.drop_table("loyalty_tiers")
