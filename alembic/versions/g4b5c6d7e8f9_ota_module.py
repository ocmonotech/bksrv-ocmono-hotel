"""OTA channel manager — integrations, room mappings, reservation links."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "g4b5c6d7e8f9_ota_module"
down_revision: Union[str, None] = "f3a4b5c6d7e8_rate_plans"
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
        "outlet_ota_integrations",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("booking_com", "mmt", "expedia", name="otaplatform"),
            nullable=False,
        ),
        sa.Column("external_property_id", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "active",
                "inactive",
                "pending",
                "error",
                name="integrationstatus",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("auto_confirm_reservations", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("auto_push_availability", sa.Boolean(), server_default="0", nullable=False),
        sa.Column("webhook_token", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column("encrypted_webhook_secret", sa.Text(), nullable=True),
        sa.Column("last_sync_at", sa.DateTime(), nullable=True),
        sa.Column("last_error", sa.Text(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("outlet_id", "platform", name="uq_outlet_ota_platform"),
        sa.UniqueConstraint("webhook_token"),
    )
    op.create_index(op.f("ix_outlet_ota_integrations_outlet_id"), "outlet_ota_integrations", ["outlet_id"])

    op.create_table(
        "ota_room_type_mappings",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("external_room_type_id", sa.String(length=64), nullable=False),
        sa.Column("external_room_type_name", sa.String(length=128), nullable=True),
        sa.Column("room_type_id", sa.Integer(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_ota_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["room_type_id"], ["room_types.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_room_type_id", name="uq_ota_room_type_external"),
    )
    op.create_index(op.f("ix_ota_room_type_mappings_integration_id"), "ota_room_type_mappings", ["integration_id"])

    op.create_table(
        "ota_reservation_links",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("guest_reservation_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("booking_com", "mmt", "expedia", name="otaplatform", create_type=False),
            nullable=False,
        ),
        sa.Column("external_reservation_id", sa.String(length=128), nullable=False),
        sa.Column("external_status", sa.String(length=64), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_ota_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["guest_reservation_id"], ["guest_reservations.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_reservation_id", name="uq_ota_external_reservation"),
        sa.UniqueConstraint("guest_reservation_id"),
    )
    op.create_index(op.f("ix_ota_reservation_links_integration_id"), "ota_reservation_links", ["integration_id"])


def downgrade() -> None:
    op.drop_index(op.f("ix_ota_reservation_links_integration_id"), table_name="ota_reservation_links")
    op.drop_table("ota_reservation_links")
    op.drop_index(op.f("ix_ota_room_type_mappings_integration_id"), table_name="ota_room_type_mappings")
    op.drop_table("ota_room_type_mappings")
    op.drop_index(op.f("ix_outlet_ota_integrations_outlet_id"), table_name="outlet_ota_integrations")
    op.drop_table("outlet_ota_integrations")
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        sa.Enum(name="otaplatform").drop(bind, checkfirst=True)
