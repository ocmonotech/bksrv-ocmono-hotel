"""Add spa therapist roster for staff calendar."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "l9a0b1c2d3e4"
down_revision: Union[str, None] = "k8f9a0b1c2d3"
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
        "spa_therapists",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("title", sa.String(length=64), nullable=True),
        sa.Column("specialties", sa.String(length=255), nullable=True),
        sa.Column("shift_start", sa.String(length=8), nullable=False),
        sa.Column("shift_end", sa.String(length=8), nullable=False),
        sa.Column("calendar_color", sa.String(length=7), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "outlet_id", "user_id", name="uq_spa_therapist_tenant_outlet_user"),
    )
    op.create_index(op.f("ix_spa_therapists_tenant_id"), "spa_therapists", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_spa_therapists_outlet_id"), "spa_therapists", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_spa_therapists_user_id"), "spa_therapists", ["user_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_spa_therapists_user_id"), table_name="spa_therapists")
    op.drop_index(op.f("ix_spa_therapists_outlet_id"), table_name="spa_therapists")
    op.drop_index(op.f("ix_spa_therapists_tenant_id"), table_name="spa_therapists")
    op.drop_table("spa_therapists")
