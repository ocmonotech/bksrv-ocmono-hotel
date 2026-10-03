"""Add delivery integrations and order source on POS orders."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f4e2a91b3d"
down_revision: Union[str, None] = "42a1bd96c8bb"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "pos_orders",
        sa.Column(
            "order_source",
            sa.Enum(
                "IN_HOUSE",
                "ZOMATO",
                "SWIGGY",
                "ONDC",
                "DUNZO",
                "MAGICPIN",
                name="ordersource",
            ),
            nullable=False,
            server_default="IN_HOUSE",
        ),
    )
    op.add_column("pos_orders", sa.Column("source_reference", sa.String(length=128), nullable=True))
    op.create_index(op.f("ix_pos_orders_source_reference"), "pos_orders", ["source_reference"], unique=False)

    op.create_table(
        "outlet_delivery_integrations",
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("ZOMATO", "SWIGGY", "ONDC", "DUNZO", "MAGICPIN", name="deliveryplatform"),
            nullable=False,
        ),
        sa.Column("external_store_id", sa.String(length=128), nullable=True),
        sa.Column(
            "status",
            sa.Enum("ACTIVE", "INACTIVE", "PENDING", "ERROR", name="integrationstatus"),
            nullable=False,
        ),
        sa.Column("is_enabled", sa.Boolean(), nullable=False),
        sa.Column("auto_accept_orders", sa.Boolean(), nullable=False),
        sa.Column("auto_send_kot", sa.Boolean(), nullable=False),
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
        sa.UniqueConstraint("outlet_id", "platform", name="uq_outlet_delivery_platform"),
    )
    op.create_index(
        op.f("ix_outlet_delivery_integrations_brand_id"),
        "outlet_delivery_integrations",
        ["brand_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_delivery_integrations_outlet_id"),
        "outlet_delivery_integrations",
        ["outlet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_delivery_integrations_tenant_id"),
        "outlet_delivery_integrations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_delivery_integrations_webhook_token"),
        "outlet_delivery_integrations",
        ["webhook_token"],
        unique=True,
    )

    op.create_table(
        "delivery_menu_mappings",
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("external_item_id", sa.String(length=128), nullable=False),
        sa.Column("external_item_name", sa.String(length=255), nullable=False),
        sa.Column("menu_item_id", sa.Integer(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_delivery_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_item_id", name="uq_delivery_menu_external_item"),
    )
    op.create_index(
        op.f("ix_delivery_menu_mappings_integration_id"),
        "delivery_menu_mappings",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_menu_mappings_menu_item_id"),
        "delivery_menu_mappings",
        ["menu_item_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_menu_mappings_tenant_id"),
        "delivery_menu_mappings",
        ["tenant_id"],
        unique=False,
    )

    op.create_table(
        "delivery_order_links",
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("pos_order_id", sa.Integer(), nullable=False),
        sa.Column(
            "platform",
            sa.Enum("ZOMATO", "SWIGGY", "ONDC", "DUNZO", "MAGICPIN", name="deliveryplatform"),
            nullable=False,
        ),
        sa.Column("external_order_id", sa.String(length=128), nullable=False),
        sa.Column(
            "external_status",
            sa.Enum(
                "RECEIVED",
                "ACCEPTED",
                "PREPARING",
                "READY",
                "PICKED_UP",
                "DELIVERED",
                "CANCELLED",
                "REJECTED",
                name="externalorderstatus",
            ),
            nullable=False,
        ),
        sa.Column("customer_name", sa.String(length=255), nullable=True),
        sa.Column("customer_phone", sa.String(length=32), nullable=True),
        sa.Column("delivery_address", sa.Text(), nullable=True),
        sa.Column("rider_name", sa.String(length=255), nullable=True),
        sa.Column("rider_phone", sa.String(length=32), nullable=True),
        sa.Column("raw_payload_json", sa.Text(), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_delivery_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pos_order_id"], ["pos_orders.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("integration_id", "external_order_id", name="uq_delivery_external_order"),
    )
    op.create_index(
        op.f("ix_delivery_order_links_integration_id"),
        "delivery_order_links",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_order_links_pos_order_id"),
        "delivery_order_links",
        ["pos_order_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_delivery_order_links_tenant_id"),
        "delivery_order_links",
        ["tenant_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_delivery_order_links_tenant_id"), table_name="delivery_order_links")
    op.drop_index(op.f("ix_delivery_order_links_pos_order_id"), table_name="delivery_order_links")
    op.drop_index(op.f("ix_delivery_order_links_integration_id"), table_name="delivery_order_links")
    op.drop_table("delivery_order_links")

    op.drop_index(op.f("ix_delivery_menu_mappings_tenant_id"), table_name="delivery_menu_mappings")
    op.drop_index(op.f("ix_delivery_menu_mappings_menu_item_id"), table_name="delivery_menu_mappings")
    op.drop_index(op.f("ix_delivery_menu_mappings_integration_id"), table_name="delivery_menu_mappings")
    op.drop_table("delivery_menu_mappings")

    op.drop_index(
        op.f("ix_outlet_delivery_integrations_webhook_token"),
        table_name="outlet_delivery_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_delivery_integrations_tenant_id"),
        table_name="outlet_delivery_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_delivery_integrations_outlet_id"),
        table_name="outlet_delivery_integrations",
    )
    op.drop_index(
        op.f("ix_outlet_delivery_integrations_brand_id"),
        table_name="outlet_delivery_integrations",
    )
    op.drop_table("outlet_delivery_integrations")

    op.drop_index(op.f("ix_pos_orders_source_reference"), table_name="pos_orders")
    op.drop_column("pos_orders", "source_reference")
    op.drop_column("pos_orders", "order_source")

    sa.Enum(name="externalorderstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="integrationstatus").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="deliveryplatform").drop(op.get_bind(), checkfirst=True)
    sa.Enum(name="ordersource").drop(op.get_bind(), checkfirst=True)
