"""Banquet halls and venue bookings."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "n1c2d3e4f5a6"
down_revision: Union[str, None] = "m0b1c2d3e4f5"
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
        "banquet_venues",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "venue_type",
            sa.Enum("indoor", "outdoor", "lawn", "conference", "pool_deck", name="banquetvenuetype"),
            nullable=False,
        ),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("capacity_min", sa.Integer(), nullable=False),
        sa.Column("capacity_max", sa.Integer(), nullable=False),
        sa.Column("half_day_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("full_day_rate", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("amenities", sa.String(length=512), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_banquet_venues_outlet_id", "banquet_venues", ["outlet_id"])
    op.create_index("ix_banquet_venues_tenant_id", "banquet_venues", ["tenant_id"])

    op.create_table(
        "banquet_bookings",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("venue_id", sa.Integer(), nullable=False),
        sa.Column("booking_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column(
            "event_type",
            sa.Enum("wedding", "conference", "reception", "corporate", "social", "other", name="banqueteventtype"),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("inquiry", "tentative", "confirmed", "completed", "cancelled", name="banquetbookingstatus"),
            nullable=False,
        ),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(length=8), nullable=False),
        sa.Column("end_time", sa.String(length=8), nullable=False),
        sa.Column("guest_count", sa.Integer(), nullable=False),
        sa.Column("contact_name", sa.String(length=255), nullable=False),
        sa.Column("contact_phone", sa.String(length=32), nullable=True),
        sa.Column("contact_email", sa.String(length=255), nullable=True),
        sa.Column("guest_reservation_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("estimated_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("advance_paid", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["guest_reservation_id"], ["guest_reservations.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["venue_id"], ["banquet_venues.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("booking_number"),
    )
    op.create_index("ix_banquet_bookings_booking_number", "banquet_bookings", ["booking_number"])
    op.create_index("ix_banquet_bookings_event_date", "banquet_bookings", ["event_date"])
    op.create_index("ix_banquet_bookings_outlet_id", "banquet_bookings", ["outlet_id"])
    op.create_index("ix_banquet_bookings_venue_id", "banquet_bookings", ["venue_id"])


def downgrade() -> None:
    op.drop_table("banquet_bookings")
    op.drop_table("banquet_venues")
