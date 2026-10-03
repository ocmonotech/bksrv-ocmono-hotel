"""Wastage day_part for prep board kitchen log.

Revision ID: r1f2a3b4c5d6
Revises: q0e1f2a3b4c5
Create Date: 2026-07-14 17:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "r1f2a3b4c5d6"
down_revision: Union[str, None] = "q0e1f2a3b4c5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_table("wastage"):
        return
    if not _has_column("wastage", "day_part"):
        op.add_column(
            "wastage",
            sa.Column("day_part", sa.String(16), nullable=True),
        )


def downgrade() -> None:
    if not _has_table("wastage"):
        return
    if _has_column("wastage", "day_part"):
        op.drop_column("wastage", "day_part")
