"""PMS group master folio — nullable reservation_id + group_id on guest_folios."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "x1y2z3a4b5c6"
down_revision: Union[str, None] = "w0x1y2z3a4b5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    # Allow master folios without a reservation
    try:
        op.alter_column(
            "guest_folios",
            "reservation_id",
            existing_type=sa.Integer(),
            nullable=True,
        )
    except Exception:
        pass

    if not _has_column("guest_folios", "group_id"):
        op.add_column(
            "guest_folios",
            sa.Column("group_id", sa.Integer(), nullable=True),
        )
        try:
            op.create_foreign_key(
                "fk_guest_folios_group_id",
                "guest_folios",
                "reservation_groups",
                ["group_id"],
                ["id"],
            )
        except Exception:
            pass
        try:
            op.create_index("ix_guest_folios_group_id", "guest_folios", ["group_id"], unique=True)
        except Exception:
            pass


def downgrade() -> None:
    bind = op.get_bind()
    indexes = {idx["name"] for idx in inspect(bind).get_indexes("guest_folios")}
    if "ix_guest_folios_group_id" in indexes:
        op.drop_index("ix_guest_folios_group_id", table_name="guest_folios")
    if _has_column("guest_folios", "group_id"):
        try:
            op.drop_constraint("fk_guest_folios_group_id", "guest_folios", type_="foreignkey")
        except Exception:
            pass
        op.drop_column("guest_folios", "group_id")
    # Do not force reservation_id back to NOT NULL — may contain master rows
