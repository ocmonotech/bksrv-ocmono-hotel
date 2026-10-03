"""Add restaurant events for party and celebration management."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "f3a8b2c91d4e"
down_revision: Union[str, None] = "c8f2a91d4e10"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "restaurant_events",
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("customer_id", sa.Integer(), nullable=True),
        sa.Column("lead_id", sa.Integer(), nullable=True),
        sa.Column("booking_id", sa.Integer(), nullable=True),
        sa.Column("offer_id", sa.Integer(), nullable=True),
        sa.Column(
            "event_type",
            sa.Enum(
                "BIRTHDAY",
                "ANNIVERSARY",
                "CORPORATE",
                "PRIVATE_DINING",
                "KIDS_PARTY",
                "CELEBRATION",
                "CUSTOM",
                name="eventtype",
            ),
            nullable=False,
        ),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("guest_of_honor", sa.String(length=255), nullable=True),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("event_date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.String(length=8), nullable=False),
        sa.Column("end_time", sa.String(length=8), nullable=True),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("expected_guests", sa.Integer(), nullable=False),
        sa.Column("confirmed_guests", sa.Integer(), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "INQUIRY",
                "QUOTED",
                "CONFIRMED",
                "IN_PROGRESS",
                "COMPLETED",
                "CANCELLED",
                name="eventstatus",
            ),
            nullable=False,
        ),
        sa.Column(
            "source",
            sa.Enum(
                "WALK_IN",
                "PHONE",
                "WHATSAPP",
                "WEBSITE",
                "LEAD",
                "OTHER",
                name="eventsource",
            ),
            nullable=False,
        ),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("decoration_notes", sa.Text(), nullable=True),
        sa.Column("dietary_notes", sa.Text(), nullable=True),
        sa.Column("estimated_amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("advance_paid", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["booking_id"], ["table_bookings.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
        sa.ForeignKeyConstraint(["lead_id"], ["leads.id"]),
        sa.ForeignKeyConstraint(["offer_id"], ["offers.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_restaurant_events_assigned_to"), "restaurant_events", ["assigned_to"], unique=False)
    op.create_index(op.f("ix_restaurant_events_booking_id"), "restaurant_events", ["booking_id"], unique=False)
    op.create_index(op.f("ix_restaurant_events_brand_id"), "restaurant_events", ["brand_id"], unique=False)
    op.create_index(op.f("ix_restaurant_events_customer_id"), "restaurant_events", ["customer_id"], unique=False)
    op.create_index(op.f("ix_restaurant_events_event_date"), "restaurant_events", ["event_date"], unique=False)
    op.create_index(op.f("ix_restaurant_events_lead_id"), "restaurant_events", ["lead_id"], unique=False)
    op.create_index(op.f("ix_restaurant_events_outlet_id"), "restaurant_events", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_restaurant_events_tenant_id"), "restaurant_events", ["tenant_id"], unique=False)

    op.create_table(
        "event_table_assignments",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=False),
        sa.Column("reserved_from", sa.DateTime(), nullable=False),
        sa.Column("reserved_until", sa.DateTime(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.ForeignKeyConstraint(["event_id"], ["restaurant_events.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["restaurant_tables.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_event_table_assignments_event_id"),
        "event_table_assignments",
        ["event_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_event_table_assignments_table_id"),
        "event_table_assignments",
        ["table_id"],
        unique=False,
    )

    op.create_table(
        "event_activities",
        sa.Column("event_id", sa.Integer(), nullable=False),
        sa.Column(
            "activity_type",
            sa.Enum(
                "NOTE",
                "CALL",
                "WHATSAPP",
                "STATUS_CHANGE",
                "PAYMENT",
                name="eventactivitytype",
            ),
            nullable=False,
        ),
        sa.Column("note", sa.Text(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["event_id"], ["restaurant_events.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_event_activities_brand_id"), "event_activities", ["brand_id"], unique=False)
    op.create_index(op.f("ix_event_activities_event_id"), "event_activities", ["event_id"], unique=False)
    op.create_index(op.f("ix_event_activities_tenant_id"), "event_activities", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_event_activities_tenant_id"), table_name="event_activities")
    op.drop_index(op.f("ix_event_activities_event_id"), table_name="event_activities")
    op.drop_index(op.f("ix_event_activities_brand_id"), table_name="event_activities")
    op.drop_table("event_activities")

    op.drop_index(op.f("ix_event_table_assignments_table_id"), table_name="event_table_assignments")
    op.drop_index(op.f("ix_event_table_assignments_event_id"), table_name="event_table_assignments")
    op.drop_table("event_table_assignments")

    op.drop_index(op.f("ix_restaurant_events_tenant_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_outlet_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_lead_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_event_date"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_customer_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_brand_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_booking_id"), table_name="restaurant_events")
    op.drop_index(op.f("ix_restaurant_events_assigned_to"), table_name="restaurant_events")
    op.drop_table("restaurant_events")

    op.execute("DROP TYPE IF EXISTS eventactivitytype")
    op.execute("DROP TYPE IF EXISTS eventsource")
    op.execute("DROP TYPE IF EXISTS eventstatus")
    op.execute("DROP TYPE IF EXISTS eventtype")
