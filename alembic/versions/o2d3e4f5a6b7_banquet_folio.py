"""Banquet folio deposit and charge posting."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "o2d3e4f5a6b7"
down_revision: Union[str, None] = "n1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("banquet_bookings") as batch_op:
        batch_op.add_column(
            sa.Column("charge_to_folio", sa.Boolean(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("folio_posted_at", sa.DateTime(), nullable=True))
        batch_op.add_column(sa.Column("deposit_folio_posted_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("folio_entries") as batch_op:
        batch_op.add_column(sa.Column("banquet_booking_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_folio_entries_banquet_booking_id",
            "banquet_bookings",
            ["banquet_booking_id"],
            ["id"],
        )
        batch_op.create_index("ix_folio_entries_banquet_booking_id", ["banquet_booking_id"])


def downgrade() -> None:
    with op.batch_alter_table("folio_entries") as batch_op:
        batch_op.drop_index("ix_folio_entries_banquet_booking_id")
        batch_op.drop_constraint("fk_folio_entries_banquet_booking_id", type_="foreignkey")
        batch_op.drop_column("banquet_booking_id")

    with op.batch_alter_table("banquet_bookings") as batch_op:
        batch_op.drop_column("deposit_folio_posted_at")
        batch_op.drop_column("folio_posted_at")
        batch_op.drop_column("charge_to_folio")
