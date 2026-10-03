"""PMS city ledger (accounts receivable) entries."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "b5c6d7e8f9a0"
down_revision: Union[str, None] = "a4b5c6d7e8f9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    bind = op.get_bind()
    return table in inspect(bind).get_table_names()


def upgrade() -> None:
    if _has_table("city_ledger_entries"):
        return
    op.create_table(
        "city_ledger_entries",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
        sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
        sa.Column("reservation_id", sa.Integer(), sa.ForeignKey("guest_reservations.id"), nullable=True),
        sa.Column("folio_id", sa.Integer(), sa.ForeignKey("guest_folios.id"), nullable=True),
        sa.Column("reference", sa.String(32), nullable=False),
        sa.Column("company_name", sa.String(255), nullable=False),
        sa.Column("guest_name", sa.String(255), nullable=True),
        sa.Column("original_amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("balance", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(16), nullable=False, server_default="open"),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.Column("settled_at", sa.DateTime(), nullable=True),
        sa.Column("settled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        sa.UniqueConstraint("tenant_id", "reference", name="uq_city_ledger_tenant_reference"),
    )
    op.create_index("ix_city_ledger_entries_reference", "city_ledger_entries", ["reference"])
    op.create_index("ix_city_ledger_entries_status", "city_ledger_entries", ["status"])
    op.create_index("ix_city_ledger_entries_reservation_id", "city_ledger_entries", ["reservation_id"])


def downgrade() -> None:
    if _has_table("city_ledger_entries"):
        op.drop_table("city_ledger_entries")
