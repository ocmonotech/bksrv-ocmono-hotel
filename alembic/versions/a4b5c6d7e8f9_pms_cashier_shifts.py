"""PMS front-desk cashier shifts."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "a4b5c6d7e8f9"
down_revision: Union[str, None] = "z3a4b5c6d7e8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("cashier_shifts"):
        return
    op.create_table(
        "cashier_shifts",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("opened_at", sa.DateTime(), nullable=False),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        sa.Column("opened_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("closed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("opening_float", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("declared_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("expected_cash", sa.Numeric(12, 2), nullable=True),
        sa.Column("cash_variance", sa.Numeric(12, 2), nullable=True),
        sa.Column("tender_cash", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("tender_card", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("tender_upi", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("tender_other", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("payments_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("refunds_total", sa.Numeric(12, 2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    if _has_table("cashier_shifts"):
        op.drop_table("cashier_shifts")
