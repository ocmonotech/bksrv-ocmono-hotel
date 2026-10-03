"""PMS rate plan day-use pricing fields."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "w0x1y2z3a4b5"
down_revision: Union[str, None] = "v9w0x1y2z3a4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    if not _has_column("rate_plans", "allows_day_use"):
        op.add_column(
            "rate_plans",
            sa.Column("allows_day_use", sa.Boolean(), server_default="1", nullable=False),
        )
    if not _has_column("rate_plans", "day_use_rate_percent"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "day_use_rate_percent",
                sa.Numeric(5, 2),
                server_default="50",
                nullable=False,
            ),
        )


def downgrade() -> None:
    if _has_column("rate_plans", "day_use_rate_percent"):
        op.drop_column("rate_plans", "day_use_rate_percent")
    if _has_column("rate_plans", "allows_day_use"):
        op.drop_column("rate_plans", "allows_day_use")
