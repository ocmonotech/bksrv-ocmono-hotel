"""OTA sync logs — ARI push history."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "h5c6d7e8f9a0_ota_sync_logs"
down_revision: Union[str, None] = "g4b5c6d7e8f9_ota_module"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_cols():
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
    ]


def upgrade() -> None:
    op.create_table(
        "ota_sync_logs",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column(
            "sync_type",
            sa.Enum("ari_push", name="otasynctype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("success", "failed", name="otasyncstatus"),
            nullable=False,
        ),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("room_types_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("days_count", sa.Integer(), server_default="0", nullable=False),
        sa.Column("external_reference", sa.String(length=128), nullable=True),
        sa.Column("message", sa.String(length=512), nullable=False),
        sa.Column("summary_json", sa.Text(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_ota_integrations.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ota_sync_logs_integration_id", "ota_sync_logs", ["integration_id"])


def downgrade() -> None:
    op.drop_index("ix_ota_sync_logs_integration_id", table_name="ota_sync_logs")
    op.drop_table("ota_sync_logs")
