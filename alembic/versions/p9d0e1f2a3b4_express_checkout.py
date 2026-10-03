"""Express checkout request fields on guest reservations.

Revision ID: p9d0e1f2a3b4
Revises: o8c9d0e1f2a3
Create Date: 2026-07-14 16:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "p9d0e1f2a3b4"
down_revision: Union[str, None] = "o8c9d0e1f2a3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("guest_reservations"):
        return
    if not _has_column("guest_reservations", "express_checkout_status"):
        op.add_column(
            "guest_reservations",
            sa.Column(
                "express_checkout_status",
                sa.String(16),
                nullable=False,
                server_default="none",
            ),
        )
    if not _has_column("guest_reservations", "express_checkout_at"):
        op.add_column(
            "guest_reservations",
            sa.Column("express_checkout_at", sa.DateTime(), nullable=True),
        )
    if not _has_column("guest_reservations", "express_checkout_notes"):
        op.add_column(
            "guest_reservations",
            sa.Column("express_checkout_notes", sa.Text(), nullable=True),
        )
    if not _has_column("guest_reservations", "estimated_departure_time"):
        op.add_column(
            "guest_reservations",
            sa.Column("estimated_departure_time", sa.String(16), nullable=True),
        )
    if not _has_column("guest_reservations", "express_checkout_reviewed_at"):
        op.add_column(
            "guest_reservations",
            sa.Column("express_checkout_reviewed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if not _has_table("guest_reservations"):
        return
    for col in (
        "express_checkout_reviewed_at",
        "estimated_departure_time",
        "express_checkout_notes",
        "express_checkout_at",
        "express_checkout_status",
    ):
        if _has_column("guest_reservations", col):
            op.drop_column("guest_reservations", col)
