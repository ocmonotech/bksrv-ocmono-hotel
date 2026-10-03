"""Add event pre-orders and POS order link."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "a2b3c4d5e6f7"
down_revision: Union[str, None] = "f3a8b2c91d4e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    inspector = sa.inspect(bind)
    event_columns = {column["name"] for column in inspector.get_columns("restaurant_events")}

    if "pos_order_id" not in event_columns:
        op.add_column("restaurant_events", sa.Column("pos_order_id", sa.Integer(), nullable=True))

    existing_indexes = {index["name"] for index in inspector.get_indexes("restaurant_events")}
    index_name = op.f("ix_restaurant_events_pos_order_id")
    if index_name not in existing_indexes:
        op.create_index(index_name, "restaurant_events", ["pos_order_id"], unique=False)

    existing_fks = {fk["name"] for fk in inspector.get_foreign_keys("restaurant_events")}
    if "fk_restaurant_events_pos_order_id" not in existing_fks:
        op.create_foreign_key(
            "fk_restaurant_events_pos_order_id",
            "restaurant_events",
            "pos_orders",
            ["pos_order_id"],
            ["id"],
        )

    if "event_preorder_items" not in inspector.get_table_names():
        op.create_table(
            "event_preorder_items",
            sa.Column("event_id", sa.Integer(), nullable=False),
            sa.Column("menu_item_id", sa.Integer(), nullable=False),
            sa.Column("item_name", sa.String(length=255), nullable=False),
            sa.Column("quantity", sa.Integer(), nullable=False),
            sa.Column("unit_price", sa.Numeric(precision=10, scale=2), nullable=False),
            sa.Column("notes", sa.String(length=255), nullable=True),
            sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
            sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.ForeignKeyConstraint(["event_id"], ["restaurant_events.id"]),
            sa.ForeignKeyConstraint(["menu_item_id"], ["menu_items.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(
            op.f("ix_event_preorder_items_event_id"),
            "event_preorder_items",
            ["event_id"],
            unique=False,
        )
        op.create_index(
            op.f("ix_event_preorder_items_menu_item_id"),
            "event_preorder_items",
            ["menu_item_id"],
            unique=False,
        )


def downgrade() -> None:
    op.drop_index(op.f("ix_event_preorder_items_menu_item_id"), table_name="event_preorder_items")
    op.drop_index(op.f("ix_event_preorder_items_event_id"), table_name="event_preorder_items")
    op.drop_table("event_preorder_items")
    op.drop_constraint("fk_restaurant_events_pos_order_id", "restaurant_events", type_="foreignkey")
    op.drop_index(op.f("ix_restaurant_events_pos_order_id"), table_name="restaurant_events")
    op.drop_column("restaurant_events", "pos_order_id")
