"""Recipe costing — material unit costs and menu food cost %.

Revision ID: l5f6a7b8c9d0
Revises: k4e5f6a7b8c9
Create Date: 2026-07-14 15:00:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "l5f6a7b8c9d0"
down_revision: Union[str, None] = "k4e5f6a7b8c9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def _has_column(table: str, column: str) -> bool:
    cols = {c["name"] for c in inspect(op.get_bind()).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if _has_table("raw_materials") and not _has_column("raw_materials", "average_unit_cost"):
        op.add_column(
            "raw_materials",
            sa.Column("average_unit_cost", sa.Numeric(12, 4), server_default="0", nullable=False),
        )
        op.add_column(
            "raw_materials",
            sa.Column("last_purchase_rate", sa.Numeric(12, 4), nullable=True),
        )

    if _has_table("menu_items") and not _has_column("menu_items", "recipe_cost"):
        op.add_column(
            "menu_items",
            sa.Column("recipe_cost", sa.Numeric(12, 2), server_default="0", nullable=False),
        )
        op.add_column(
            "menu_items",
            sa.Column("food_cost_percent", sa.Numeric(5, 2), server_default="0", nullable=False),
        )

    if _has_table("stock_ledger") and not _has_column("stock_ledger", "unit_cost"):
        op.add_column(
            "stock_ledger",
            sa.Column("unit_cost", sa.Numeric(12, 4), nullable=True),
        )
        op.add_column(
            "stock_ledger",
            sa.Column("line_cost", sa.Numeric(12, 2), nullable=True),
        )


def downgrade() -> None:
    if _has_table("stock_ledger") and _has_column("stock_ledger", "line_cost"):
        op.drop_column("stock_ledger", "line_cost")
    if _has_table("stock_ledger") and _has_column("stock_ledger", "unit_cost"):
        op.drop_column("stock_ledger", "unit_cost")
    if _has_table("menu_items") and _has_column("menu_items", "food_cost_percent"):
        op.drop_column("menu_items", "food_cost_percent")
    if _has_table("menu_items") and _has_column("menu_items", "recipe_cost"):
        op.drop_column("menu_items", "recipe_cost")
    if _has_table("raw_materials") and _has_column("raw_materials", "last_purchase_rate"):
        op.drop_column("raw_materials", "last_purchase_rate")
    if _has_table("raw_materials") and _has_column("raw_materials", "average_unit_cost"):
        op.drop_column("raw_materials", "average_unit_cost")
