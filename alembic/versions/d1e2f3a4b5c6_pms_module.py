"""PMS — guest reservations, folios, front desk."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d1e2f3a4b5c6_pms"
down_revision: Union[str, None] = "c1d2e3f4a5b6_hk_floor_schedules"
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
        "guest_reservations",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("confirmation_number", sa.String(length=32), nullable=False),
        sa.Column("guest_name", sa.String(length=255), nullable=False),
        sa.Column("guest_email", sa.String(length=255), nullable=True),
        sa.Column("guest_mobile", sa.String(length=32), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("room_type_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=True),
        sa.Column("check_in_date", sa.Date(), nullable=False),
        sa.Column("check_out_date", sa.Date(), nullable=False),
        sa.Column("adults", sa.Integer(), server_default="1", nullable=False),
        sa.Column("children", sa.Integer(), server_default="0", nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "checked_in",
                "checked_out",
                "cancelled",
                "no_show",
                name="reservationstatus",
            ),
            nullable=False,
        ),
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
            ),
            nullable=False,
        ),
        sa.Column("rate_per_night", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False),
        sa.Column("total_amount", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        sa.Column("deposit_amount", sa.Numeric(precision=10, scale=2), server_default="0", nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("checked_in_at", sa.DateTime(), nullable=True),
        sa.Column("checked_out_at", sa.DateTime(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["room_type_id"], ["room_types.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["hotel_rooms.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("tenant_id", "confirmation_number", name="uq_guest_res_tenant_confirmation"),
    )
    op.create_index("ix_guest_reservations_tenant_id", "guest_reservations", ["tenant_id"])
    op.create_index("ix_guest_reservations_outlet_id", "guest_reservations", ["outlet_id"])
    op.create_index("ix_guest_reservations_confirmation_number", "guest_reservations", ["confirmation_number"])
    op.create_index("ix_guest_reservations_check_in_date", "guest_reservations", ["check_in_date"])
    op.create_index("ix_guest_reservations_status", "guest_reservations", ["status"])

    op.create_table(
        "guest_folios",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("reservation_id", sa.Integer(), nullable=False),
        sa.Column("folio_number", sa.String(length=32), nullable=False),
        sa.Column("status", sa.Enum("open", "closed", name="foliostatus"), nullable=False),
        sa.Column("balance", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["reservation_id"], ["guest_reservations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("reservation_id"),
        sa.UniqueConstraint("tenant_id", "folio_number", name="uq_guest_folio_tenant_number"),
    )
    op.create_index("ix_guest_folios_tenant_id", "guest_folios", ["tenant_id"])
    op.create_index("ix_guest_folios_folio_number", "guest_folios", ["folio_number"])

    op.create_table(
        "folio_entries",
        sa.Column("folio_id", sa.Integer(), nullable=False),
        sa.Column(
            "entry_type",
            sa.Enum(
                "room_charge",
                "tax",
                "deposit",
                "payment",
                "pos_charge",
                "adjustment",
                "refund",
                name="folioentrytype",
            ),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("pos_order_id", sa.Integer(), nullable=True),
        sa.Column("posted_by", sa.Integer(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["folio_id"], ["guest_folios.id"]),
        sa.ForeignKeyConstraint(["pos_order_id"], ["pos_orders.id"]),
        sa.ForeignKeyConstraint(["posted_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_folio_entries_folio_id", "folio_entries", ["folio_id"])


def downgrade() -> None:
    op.drop_table("folio_entries")
    op.drop_table("guest_folios")
    op.drop_table("guest_reservations")
