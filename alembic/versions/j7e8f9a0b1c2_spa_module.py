"""Add spa and activities booking module."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "j7e8f9a0b1c2"
down_revision: Union[str, None] = "i6d7e8f9a0b1_rate_plan_inclusions"
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
        "spa_services",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column("category", sa.Enum("spa", "activity", name="spaservicecategory"), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("max_capacity", sa.Integer(), nullable=False),
        sa.Column("slot_interval_minutes", sa.Integer(), nullable=False),
        sa.Column("operating_start", sa.String(length=8), nullable=False),
        sa.Column("operating_end", sa.String(length=8), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spa_services_tenant_id"), "spa_services", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_spa_services_outlet_id"), "spa_services", ["outlet_id"], unique=False)

    op.create_table(
        "spa_bookings",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("service_id", sa.Integer(), nullable=False),
        sa.Column("booking_number", sa.String(length=32), nullable=False),
        sa.Column(
            "status",
            sa.Enum(
                "pending",
                "confirmed",
                "in_progress",
                "completed",
                "cancelled",
                "no_show",
                name="spabookingstatus",
            ),
            nullable=False,
        ),
        sa.Column("booked_at", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("party_size", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("guest_name", sa.String(length=255), nullable=False),
        sa.Column("guest_phone", sa.String(length=32), nullable=True),
        sa.Column("guest_email", sa.String(length=255), nullable=True),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("guest_reservation_id", sa.Integer(), nullable=True),
        sa.Column("assigned_staff_id", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("confirmed_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("cancelled_at", sa.DateTime(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["service_id"], ["spa_services.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["guest_reservation_id"], ["guest_reservations.id"]),
        sa.ForeignKeyConstraint(["assigned_staff_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_spa_bookings_tenant_id"), "spa_bookings", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_spa_bookings_outlet_id"), "spa_bookings", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_spa_bookings_service_id"), "spa_bookings", ["service_id"], unique=False)
    op.create_index(op.f("ix_spa_bookings_booking_number"), "spa_bookings", ["booking_number"], unique=True)
    op.create_index(op.f("ix_spa_bookings_booked_at"), "spa_bookings", ["booked_at"], unique=False)
    op.create_index(op.f("ix_spa_bookings_customer_id"), "spa_bookings", ["customer_id"], unique=False)
    op.create_index(op.f("ix_spa_bookings_guest_reservation_id"), "spa_bookings", ["guest_reservation_id"], unique=False)
    op.create_index(op.f("ix_spa_bookings_assigned_staff_id"), "spa_bookings", ["assigned_staff_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_spa_bookings_assigned_staff_id"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_guest_reservation_id"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_customer_id"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_booked_at"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_booking_number"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_service_id"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_outlet_id"), table_name="spa_bookings")
    op.drop_index(op.f("ix_spa_bookings_tenant_id"), table_name="spa_bookings")
    op.drop_table("spa_bookings")
    op.drop_index(op.f("ix_spa_services_outlet_id"), table_name="spa_services")
    op.drop_index(op.f("ix_spa_services_tenant_id"), table_name="spa_services")
    op.drop_table("spa_services")
