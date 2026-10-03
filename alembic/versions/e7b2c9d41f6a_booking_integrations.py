"""Add table booking integrations and reservations."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "e7b2c9d41f6a"
down_revision: Union[str, None] = "c8f4e2a91b3d"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlet_booking_integrations",
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum(
                "ZOMATO",
                "SWIGGY_DINEOUT",
                "EAZYDINER",
                "DINEOUT",
                "GOOGLE",
                "DIRECT",
                name="bookingplatform",
            ),
            nullable=False,
        ),
        sa.Column("external_store_id", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "ACTIVE",
                "INACTIVE",
                "PENDING",
                "ERROR",
                name="integrationstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_confirm_bookings", sa.Boolean(), nullable=False),
        sa.Column("auto_reserve_table", sa.Boolean(), nullable=False),
        sa.Column("webhook_token", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "platform", name="uq_outlet_booking_platform"),
    )
    op.create_index(
        op.f("ix_outlet_booking_integrations_brand_id"),
        "outlet_booking_integrations",
        ["brand_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_booking_integrations_outlet_id"),
        "outlet_booking_integrations",
        ["outlet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_booking_integrations_tenant_id"),
        "outlet_booking_integrations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_booking_integrations_webhook_token"),
        "outlet_booking_integrations",
        ["webhook_token"],
        unique=True,
    )

    op.create_table(
        "table_bookings",
        sa.Column("integration_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum(
                "ZOMATO",
                "SWIGGY_DINEOUT",
                "EAZYDINER",
                "DINEOUT",
                "GOOGLE",
                "DIRECT",
                name="bookingplatform",
            ),
            nullable=False,
        ),
        sa.Column("external_booking_id", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "PENDING",
                "CONFIRMED",
                "SEATED",
                "COMPLETED",
                "CANCELLED",
                "NO_SHOW",
                "REJECTED",
                name="bookingstatus",
            ),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(length=255), nullable=False),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("customer_email", sa.String(length=255), nullable=True),
        sa.Column("guest_count", sa.Integer(), nullable=False),
        sa.Column("booked_for", sa.DateTime(), nullable=False),
        sa.Column("duration_minutes", sa.Integer(), nullable=False),
        sa.Column("table_id", sa.Integer(), nullable=True),
        sa.Column("special_requests", sa.Text(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_booking_integrations.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["table_id"], ["restaurant_tables.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_booking_id", name="uq_booking_external_id"),
    )
    op.create_index(op.f("ix_table_bookings_integration_id"), "table_bookings", ["integration_id"], unique=False)
    op.create_index(op.f("ix_table_bookings_outlet_id"), "table_bookings", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_table_bookings_table_id"), "table_bookings", ["table_id"], unique=False)
    op.create_index(op.f("ix_table_bookings_tenant_id"), "table_bookings", ["tenant_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_table_bookings_tenant_id"), table_name="table_bookings")
    op.drop_index(op.f("ix_table_bookings_table_id"), table_name="table_bookings")
    op.drop_index(op.f("ix_table_bookings_outlet_id"), table_name="table_bookings")
    op.drop_index(op.f("ix_table_bookings_integration_id"), table_name="table_bookings")
    op.drop_table("table_bookings")

    op.drop_index(
        op.f("ix_outlet_booking_integrations_webhook_token"),
        table_name="outlet_booking_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_booking_integrations_tenant_id"),
        table_name="outlet_booking_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_booking_integrations_outlet_id"),
        table_name="outlet_booking_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_booking_integrations_brand_id"),
        table_name="outlet_booking_integrations",
    )
    op.drop_table("outlet_booking_integrations")

    sa.Enum(name="bookingstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="bookingplatform").drop(op.get_bind(), checkfirst=True)
