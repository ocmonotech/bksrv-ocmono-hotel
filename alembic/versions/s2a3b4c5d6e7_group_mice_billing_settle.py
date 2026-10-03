"""Group MICE billing instructions + city ledger group_id.

Revision ID: s2a3b4c5d6e7
Revises: r1f2a3b4c5d6
Create Date: 2026-07-14 17:15:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "s2a3b4c5d6e7"
down_revision: Union[str, None] = "r1f2a3b4c5d6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if _has_table("reservation_groups"):
        if not _has_column("reservation_groups", "company_name"):
            op.add_column(
                "reservation_groups",
                sa.Column("company_name", sa.String(255), nullable=True),
            )
        if not _has_column("reservation_groups", "billing_instructions_json"):
            op.add_column(
                "reservation_groups",
                sa.Column("billing_instructions_json", sa.Text(), nullable=True),
            )
    if _has_table("city_ledger_entries") and not _has_column("city_ledger_entries", "group_id"):
        op.add_column(
            "city_ledger_entries",
            sa.Column("group_id", sa.Integer(), nullable=True),
        )
        op.create_index(
            "ix_city_ledger_entries_group_id",
            "city_ledger_entries",
            ["group_id"],
        )
        try:
            op.create_foreign_key(
                "fk_city_ledger_entries_group_id",
                "city_ledger_entries",
                "reservation_groups",
                ["group_id"],
                ["id"],
            )
        except Exception:
            pass


def downgrade() -> None:
    if _has_table("city_ledger_entries") and _has_column("city_ledger_entries", "group_id"):
        try:
            op.drop_constraint("fk_city_ledger_entries_group_id", "city_ledger_entries", type_="foreignkey")
        except Exception:
            pass
        op.drop_index("ix_city_ledger_entries_group_id", table_name="city_ledger_entries")
        op.drop_column("city_ledger_entries", "group_id")
    if _has_table("reservation_groups"):
        if _has_column("reservation_groups", "billing_instructions_json"):
            op.drop_column("reservation_groups", "billing_instructions_json")
        if _has_column("reservation_groups", "company_name"):
            op.drop_column("reservation_groups", "company_name")
