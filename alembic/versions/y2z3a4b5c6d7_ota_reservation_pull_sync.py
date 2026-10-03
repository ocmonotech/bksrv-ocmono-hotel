"""Add RESERVATION_PULL to ota_sync_logs.sync_type enum."""

from typing import Sequence, Union

from alembic import op

revision: str = "y2z3a4b5c6d7"
down_revision: Union[str, None] = "x1y2z3a4b5c6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # SQLAlchemy Enum stores member names (uppercase) for native MySQL enums.
    op.execute(
        "ALTER TABLE ota_sync_logs MODIFY sync_type "
        "ENUM('ARI_PUSH', 'RESERVATION_PULL') NOT NULL"
    )


def downgrade() -> None:
    op.execute("DELETE FROM ota_sync_logs WHERE sync_type = 'RESERVATION_PULL'")
    op.execute(
        "ALTER TABLE ota_sync_logs MODIFY sync_type ENUM('ARI_PUSH') NOT NULL"
    )
