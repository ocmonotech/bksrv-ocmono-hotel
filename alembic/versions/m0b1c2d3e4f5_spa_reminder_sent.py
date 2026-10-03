"""Add spa booking reminder_sent_at timestamp."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "m0b1c2d3e4f5"
down_revision: Union[str, None] = "l9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("spa_bookings", sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("spa_bookings", "reminder_sent_at")
