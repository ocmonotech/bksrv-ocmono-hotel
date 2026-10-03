"""Rate plans — seasonal and channel-specific room pricing."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a4b5c6d7e8_rate_plans"
down_revision: Union[str, None] = "e2f3a4b5c6d7_room_charge"
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
        "rate_plans",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("room_type_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("code", sa.String(length=32), nullable=False),
        sa.Column("rate_per_night", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("is_default", sa.Boolean(), server_default="0", nullable=False),
        sa.Column(
            "source",
            sa.Enum(
                "direct",
                "walk_in",
                "phone",
                "email",
                "corporate",
                "ota_booking_com",
                "ota_mmt",
                "ota_expedia",
                name="reservationsource",
                create_type=False,
            ),
            nullable=True,
        ),
        sa.Column("valid_from", sa.Date(), nullable=True),
        sa.Column("valid_to", sa.Date(), nullable=True),
        sa.Column("min_nights", sa.Integer(), server_default="1", nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["room_type_id"], ["room_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "code", name="uq_rate_plan_tenant_code"),
    )
    op.create_index(op.f("ix_rate_plans_room_type_id"), "rate_plans", ["room_type_id"], unique=False)
    op.create_index(op.f("ix_rate_plans_code"), "rate_plans", ["code"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_rate_plans_code"), table_name="rate_plans")
    op.drop_index(op.f("ix_rate_plans_room_type_id"), table_name="rate_plans")
    op.drop_table("rate_plans")
