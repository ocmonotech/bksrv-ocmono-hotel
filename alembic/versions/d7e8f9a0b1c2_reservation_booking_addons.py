"""Store selected guest-portal add-ons on reservations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "d7e8f9a0b1c2"
down_revision: Union[str, None] = "c6d7e8f9a0b1"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in inspect(bind).get_columns(table)}


def upgrade() -> None:
    cols = _columns("guest_reservations")
    if "addons_json" not in cols:
        op.add_column("guest_reservations", sa.Column("addons_json", sa.Text(), nullable=True))


def downgrade() -> None:
    cols = _columns("guest_reservations")
    if "addons_json" in cols:
        op.drop_column("guest_reservations", "addons_json")
