"""Web pre-check-in fields on guest reservations.

Revision ID: n7b8c9d0e1f2
Revises: m6a7b8c9d0e1
Create Date: 2026-07-14 16:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "n7b8c9d0e1f2"
down_revision: Union[str, None] = "m6a7b8c9d0e1"
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
    if not _has_column("guest_reservations", "pre_check_in_status"):
        op.add_column(
            "guest_reservations",
            sa.Column(
                "pre_check_in_status",
                sa.String(16),
                nullable=False,
                server_default="none",
            ),
        )
    if not _has_column("guest_reservations", "pre_check_in_at"):
        op.add_column(
            "guest_reservations",
            sa.Column("pre_check_in_at", sa.DateTime(), nullable=True),
        )
    if not _has_column("guest_reservations", "guest_id_document_type"):
        op.add_column(
            "guest_reservations",
            sa.Column("guest_id_document_type", sa.String(32), nullable=True),
        )
    if not _has_column("guest_reservations", "estimated_arrival_time"):
        op.add_column(
            "guest_reservations",
            sa.Column("estimated_arrival_time", sa.String(16), nullable=True),
        )
    if not _has_column("guest_reservations", "pre_check_in_notes"):
        op.add_column(
            "guest_reservations",
            sa.Column("pre_check_in_notes", sa.Text(), nullable=True),
        )
    if not _has_column("guest_reservations", "pre_check_in_reviewed_at"):
        op.add_column(
            "guest_reservations",
            sa.Column("pre_check_in_reviewed_at", sa.DateTime(), nullable=True),
        )


def downgrade() -> None:
    if not _has_table("guest_reservations"):
        return
    for col in (
        "pre_check_in_reviewed_at",
        "pre_check_in_notes",
        "estimated_arrival_time",
        "guest_id_document_type",
        "pre_check_in_at",
        "pre_check_in_status",
    ):
        if _has_column("guest_reservations", col):
            op.drop_column("guest_reservations", col)
