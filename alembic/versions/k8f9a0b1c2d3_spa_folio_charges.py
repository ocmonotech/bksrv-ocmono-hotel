"""Spa folio charge posting — link completed bookings to guest folios."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "k8f9a0b1c2d3"
down_revision: Union[str, None] = "j7e8f9a0b1c2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("spa_bookings") as batch_op:
        batch_op.add_column(
            sa.Column("charge_to_folio", sa.Boolean(), server_default="1", nullable=False)
        )
        batch_op.add_column(sa.Column("folio_posted_at", sa.DateTime(), nullable=True))

    with op.batch_alter_table("folio_entries") as batch_op:
        batch_op.add_column(sa.Column("spa_booking_id", sa.Integer(), nullable=True))
        batch_op.create_foreign_key(
            "fk_folio_entries_spa_booking_id",
            "spa_bookings",
            ["spa_booking_id"],
            ["id"],
        )
        batch_op.create_index("ix_folio_entries_spa_booking_id", ["spa_booking_id"])


def downgrade() -> None:
    with op.batch_alter_table("folio_entries") as batch_op:
        batch_op.drop_index("ix_folio_entries_spa_booking_id")
        batch_op.drop_constraint("fk_folio_entries_spa_booking_id", type_="foreignkey")
        batch_op.drop_column("spa_booking_id")

    with op.batch_alter_table("spa_bookings") as batch_op:
        batch_op.drop_column("folio_posted_at")
        batch_op.drop_column("charge_to_folio")
