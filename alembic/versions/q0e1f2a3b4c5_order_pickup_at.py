"""Click & collect pickup_at / ready_at on POS orders.

Revision ID: q0e1f2a3b4c5
Revises: p9d0e1f2a3b4
Create Date: 2026-07-14 16:45:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "q0e1f2a3b4c5"
down_revision: Union[str, None] = "p9d0e1f2a3b4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("pos_orders"):
        return
    if not _has_column("pos_orders", "pickup_at"):
        op.add_column("pos_orders", sa.Column("pickup_at", sa.DateTime(), nullable=True))
        op.create_index("ix_pos_orders_pickup_at", "pos_orders", ["pickup_at"])
    if not _has_column("pos_orders", "ready_at"):
        op.add_column("pos_orders", sa.Column("ready_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    if not _has_table("pos_orders"):
        return
    if _has_column("pos_orders", "ready_at"):
        op.drop_column("pos_orders", "ready_at")
    if _has_column("pos_orders", "pickup_at"):
        op.drop_index("ix_pos_orders_pickup_at", table_name="pos_orders")
        op.drop_column("pos_orders", "pickup_at")
