"""Add room_charge payment mode for post-to-room billing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e2f3a4b5c6d7_room_charge"
down_revision: Union[str, None] = "d1e2f3a4b5c6_pms"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE pos_payments MODIFY payment_mode "
                "ENUM('cash','upi','card','online','split','room_charge') NOT NULL"
            )
        )


def downgrade() -> None:
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(
            sa.text(
                "ALTER TABLE pos_payments MODIFY payment_mode "
                "ENUM('cash','upi','card','online','split') NOT NULL"
            )
        )
