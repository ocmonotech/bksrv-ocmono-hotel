"""Add banquet booking reminder_sent_at timestamp."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "p3e4f5a6b7c8"
down_revision: Union[str, None] = "o2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("banquet_bookings", sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("banquet_bookings", "reminder_sent_at")
