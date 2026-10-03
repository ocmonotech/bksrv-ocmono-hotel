"""Add housekeeping floor assignments and sweep schedules."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c1d2e3f4a5b6_hk_floor_schedules"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
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
        "housekeeping_floor_assignments",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("floor", sa.String(length=16), nullable=False),
        sa.Column("housekeeper_id", sa.Integer(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["housekeeper_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "floor", name="uq_hk_floor_assignment_outlet_floor"),
    )
    op.create_index(
        op.f("ix_housekeeping_floor_assignments_tenant_id"),
        "housekeeping_floor_assignments",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_housekeeping_floor_assignments_outlet_id"),
        "housekeeping_floor_assignments",
        ["outlet_id"],
        unique=False,
    )

    op.create_table(
        "housekeeping_sweep_schedules",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("sweep_type", sa.String(length=16), nullable=False),
        sa.Column("run_time", sa.String(length=5), nullable=False),
        sa.Column("enabled", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("distribute_by_floor", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("use_floor_assignments", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("last_run_date", sa.Date(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "sweep_type", name="uq_hk_sweep_schedule_outlet_type"),
    )
    op.create_index(
        op.f("ix_housekeeping_sweep_schedules_tenant_id"),
        "housekeeping_sweep_schedules",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_housekeeping_sweep_schedules_outlet_id"),
        "housekeeping_sweep_schedules",
        ["outlet_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("housekeeping_sweep_schedules")
    op.drop_table("housekeeping_floor_assignments")
