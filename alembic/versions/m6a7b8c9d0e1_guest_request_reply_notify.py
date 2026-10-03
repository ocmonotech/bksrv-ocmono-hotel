"""Guest service request staff reply + notify timestamp.

Revision ID: m6a7b8c9d0e1
Revises: l5f6a7b8c9d0
Create Date: 2026-07-14 15:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "m6a7b8c9d0e1"
down_revision: Union[str, None] = "l5f6a7b8c9d0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("guest_service_requests"):
        return
    if not _has_column("guest_service_requests", "staff_reply"):
        op.add_column(
            "guest_service_requests",
            sa.Column("staff_reply", sa.Text(), nullable=True),
        )
    if not _has_column("guest_service_requests", "guest_notified_at"):
        op.add_column(
            "guest_service_requests",
            sa.Column("guest_notified_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if not _has_table("guest_service_requests"):
        return
    if _has_column("guest_service_requests", "guest_notified_at"):
        op.drop_column("guest_service_requests", "guest_notified_at")
    if _has_column("guest_service_requests", "staff_reply"):
        op.drop_column("guest_service_requests", "staff_reply")
