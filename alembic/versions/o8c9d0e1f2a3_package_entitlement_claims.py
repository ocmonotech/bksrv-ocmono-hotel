"""Package entitlement claim audit (breakfast / inclusion redeem).

Revision ID: o8c9d0e1f2a3
Revises: n7b8c9d0e1f2
Create Date: 2026-07-14 16:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "o8c9d0e1f2a3"
down_revision: Union[str, None] = "n7b8c9d0e1f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    if _has_table("package_entitlement_claims"):
        return
    op.create_table(
        "package_entitlement_claims",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
        sa.Column(
            "entitlement_id",
            sa.Integer(),
            sa.ForeignKey("reservation_package_entitlements.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column(
            "reservation_id",
            sa.Integer(),
            sa.ForeignKey("guest_reservations.id", ondelete="CASCADE"),
            nullable=False,
            index=True,
        ),
        sa.Column("claim_date", sa.Date(), nullable=False, index=True),
        sa.Column("qty", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("channel", sa.String(16), nullable=False, server_default="staff"),
        sa.Column("claimed_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("notes", sa.String(255), nullable=True),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )


def downgrade() -> None:
    if _has_table("package_entitlement_claims"):
        op.drop_table("package_entitlement_claims")
