"""Rate plan package inclusions and reservation plan snapshot."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "i6d7e8f9a0b1_rate_plan_inclusions"
down_revision: Union[str, None] = "h5c6d7e8f9a0_ota_sync_logs"
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
        "rate_plan_inclusions",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("rate_plan_id", sa.Integer(), nullable=False),
        sa.Column(
            "inclusion_type",
            sa.Enum("breakfast", "spa", "parking", "other", name="inclusiontype"),
            nullable=False,
        ),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("price_per_night", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False),
        sa.Column("is_included", sa.Boolean(), server_default="1", nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["rate_plan_id"], ["rate_plans.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_rate_plan_inclusions_rate_plan_id", "rate_plan_inclusions", ["rate_plan_id"])

    op.add_column("guest_reservations", sa.Column("rate_plan_id", sa.Integer(), nullable=True))
    op.create_index("ix_guest_reservations_rate_plan_id", "guest_reservations", ["rate_plan_id"])
    op.create_foreign_key(
        "fk_guest_reservations_rate_plan_id",
        "guest_reservations",
        "rate_plans",
        ["rate_plan_id"],
        ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_guest_reservations_rate_plan_id", "guest_reservations", type_="foreignkey")
    op.drop_index("ix_guest_reservations_rate_plan_id", table_name="guest_reservations")
    op.drop_column("guest_reservations", "rate_plan_id")
    op.drop_index("ix_rate_plan_inclusions_rate_plan_id", table_name="rate_plan_inclusions")
    op.drop_table("rate_plan_inclusions")
