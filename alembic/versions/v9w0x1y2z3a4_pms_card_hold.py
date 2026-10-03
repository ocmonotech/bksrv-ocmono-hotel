"""PMS mock card-hold fields on guest_reservations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "v9w0x1y2z3a4"
down_revision: Union[str, None] = "u8v9w0x1y2z3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    cols = [
        ("payment_provider", sa.Column("payment_provider", sa.String(length=32), nullable=True)),
        ("payment_hold_ref", sa.Column("payment_hold_ref", sa.String(length=64), nullable=True)),
        ("payment_auth_code", sa.Column("payment_auth_code", sa.String(length=32), nullable=True)),
        ("card_last4", sa.Column("card_last4", sa.String(length=4), nullable=True)),
        ("hold_expires_at", sa.Column("hold_expires_at", sa.DateTime(), nullable=True)),
    ]
    for name, column in cols:
        if not _has_column("guest_reservations", name):
            op.add_column("guest_reservations", column)

    bind = op.get_bind()
    indexes = {idx["name"] for idx in inspect(bind).get_indexes("guest_reservations")}
    if "ix_guest_reservations_payment_hold_ref" not in indexes:
        op.create_index(
            "ix_guest_reservations_payment_hold_ref",
            "guest_reservations",
            ["payment_hold_ref"],
        )


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {idx["name"] for idx in inspect(bind).get_indexes("guest_reservations")}
    if "ix_guest_reservations_payment_hold_ref" in indexes:
        op.drop_index("ix_guest_reservations_payment_hold_ref", table_name="guest_reservations")
    for col in (
        "hold_expires_at",
        "card_last4",
        "payment_auth_code",
        "payment_hold_ref",
        "payment_provider",
    ):
        if _has_column("guest_reservations", col):
            op.drop_column("guest_reservations", col)
