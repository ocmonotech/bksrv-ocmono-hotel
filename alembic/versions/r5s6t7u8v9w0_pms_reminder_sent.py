"""Add guest reservation reminder_sent_at timestamp."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "r5s6t7u8v9w0"
down_revision: Union[str, None] = "q4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("guest_reservations", sa.Column("reminder_sent_at", sa.DateTime(), nullable=True))


def downgrade() -> None:
    op.drop_column("guest_reservations", "reminder_sent_at")
