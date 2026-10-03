"""PMS rate plan extra-person occupancy pricing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "z3a4b5c6d7e8"
down_revision: Union[str, None] = "y2z3a4b5c6d7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("rate_plans", "included_adults"):
        op.add_column(
            "rate_plans",
            sa.Column("included_adults", sa.Integer(), server_default="2", nullable=False),
        )
    if not _has_column("rate_plans", "included_children"):
        op.add_column(
            "rate_plans",
            sa.Column("included_children", sa.Integer(), server_default="0", nullable=False),
        )
    if not _has_column("rate_plans", "extra_adult_rate"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "extra_adult_rate",
                sa.Numeric(10, 2),
                server_default="0",
                nullable=False,
            ),
        )
    if not _has_column("rate_plans", "extra_child_rate"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "extra_child_rate",
                sa.Numeric(10, 2),
                server_default="0",
                nullable=False,
            ),
        )


def downgrade() -> None:
    for col in ("extra_child_rate", "extra_adult_rate", "included_children", "included_adults"):
        if _has_column("rate_plans", col):
            op.drop_column("rate_plans", col)
