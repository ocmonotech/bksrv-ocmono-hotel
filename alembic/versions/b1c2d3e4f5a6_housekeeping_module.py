"""Add housekeeping module — rooms, checklists, tasks, maintenance tickets."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a2b3c4d5e6f7"
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
        "room_types",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=100), nullable=False),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("base_rate", sa.Numeric(precision=10, scale=2), nullable=False),
        sa.Column("max_occupancy", sa.Integer(), nullable=False),
        sa.Column("amenities", sa.Text(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_room_types_tenant_id"), "room_types", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_room_types_brand_id"), "room_types", ["brand_id"], unique=False)

    op.create_table(
        "hotel_rooms",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("room_type_id", sa.Integer(), nullable=True),
        sa.Column("room_number", sa.String(length=32), nullable=False),
        sa.Column("floor", sa.String(length=16), nullable=False),
        sa.Column("wing", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "vacant_clean", "vacant_dirty", "occupied", "checkout_pending",
                "inspecting", "out_of_order", "maintenance",
                name="roomstatus",
            ),
            nullable=False,
        ),
        sa.Column("guest_name", sa.String(length=255), nullable=True),
        sa.Column("checkout_date", sa.Date(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("last_cleaned_at", sa.DateTime(), nullable=True),
        sa.Column("assigned_housekeeper_id", sa.Integer(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["room_type_id"], ["room_types.id"]),
        sa.ForeignKeyConstraint(["assigned_housekeeper_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hotel_rooms_tenant_id"), "hotel_rooms", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_hotel_rooms_outlet_id"), "hotel_rooms", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_hotel_rooms_room_number"), "hotel_rooms", ["room_number"], unique=False)
    op.create_index(op.f("ix_hotel_rooms_room_type_id"), "hotel_rooms", ["room_type_id"], unique=False)
    op.create_index(op.f("ix_hotel_rooms_assigned_housekeeper_id"), "hotel_rooms", ["assigned_housekeeper_id"], unique=False)

    op.create_table(
        "checklist_templates",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("name", sa.String(length=128), nullable=False),
        sa.Column(
            "task_type",
            sa.Enum("checkout", "daily", "deep_clean", "turndown", "inspection", name="housekeepingtasktype"),
            nullable=False,
        ),
        sa.Column("description", sa.String(length=255), nullable=True),
        sa.Column("is_default", sa.Boolean(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checklist_templates_tenant_id"), "checklist_templates", ["tenant_id"], unique=False)

    op.create_table(
        "checklist_template_items",
        sa.Column("template_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_checklist_template_items_template_id"), "checklist_template_items", ["template_id"], unique=False)

    op.create_table(
        "housekeeping_tasks",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("template_id", sa.Integer(), nullable=True),
        sa.Column(
            "task_type",
            sa.Enum("checkout", "daily", "deep_clean", "turndown", "inspection", name="housekeepingtasktype", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("pending", "in_progress", "completed", "verified", "skipped", name="housekeepingtaskstatus"),
            nullable=False,
        ),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "urgent", name="maintenancepriority"),
            nullable=False,
        ),
        sa.Column("due_at", sa.DateTime(), nullable=True),
        sa.Column("started_at", sa.DateTime(), nullable=True),
        sa.Column("completed_at", sa.DateTime(), nullable=True),
        sa.Column("verified_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["hotel_rooms.id"]),
        sa.ForeignKeyConstraint(["template_id"], ["checklist_templates.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.ForeignKeyConstraint(["verified_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_housekeeping_tasks_tenant_id"), "housekeeping_tasks", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_housekeeping_tasks_outlet_id"), "housekeeping_tasks", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_housekeeping_tasks_room_id"), "housekeeping_tasks", ["room_id"], unique=False)
    op.create_index(op.f("ix_housekeeping_tasks_assigned_to"), "housekeeping_tasks", ["assigned_to"], unique=False)

    op.create_table(
        "task_checklist_items",
        sa.Column("task_id", sa.Integer(), nullable=False),
        sa.Column("label", sa.String(length=255), nullable=False),
        sa.Column("sort_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False),
        sa.Column("is_checked", sa.Boolean(), nullable=False),
        sa.Column("checked_at", sa.DateTime(), nullable=True),
        sa.Column("checked_by", sa.Integer(), nullable=True),
        sa.Column("notes", sa.String(length=255), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["task_id"], ["housekeeping_tasks.id"]),
        sa.ForeignKeyConstraint(["checked_by"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_task_checklist_items_task_id"), "task_checklist_items", ["task_id"], unique=False)

    op.create_table(
        "maintenance_tickets",
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column("room_id", sa.Integer(), nullable=False),
        sa.Column("ticket_number", sa.String(length=32), nullable=False),
        sa.Column("title", sa.String(length=255), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column(
            "category",
            sa.Enum("plumbing", "electrical", "hvac", "furniture", "appliance", "cleaning", "other", name="maintenancecategory"),
            nullable=False,
        ),
        sa.Column(
            "priority",
            sa.Enum("low", "medium", "high", "urgent", name="maintenancepriority", create_type=False),
            nullable=False,
        ),
        sa.Column(
            "status",
            sa.Enum("open", "assigned", "in_progress", "on_hold", "resolved", "closed", name="maintenanceticketstatus"),
            nullable=False,
        ),
        sa.Column("reported_by", sa.Integer(), nullable=False),
        sa.Column("assigned_to", sa.Integer(), nullable=True),
        sa.Column("due_date", sa.Date(), nullable=True),
        sa.Column("resolved_at", sa.DateTime(), nullable=True),
        sa.Column("resolution_notes", sa.Text(), nullable=True),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
        sa.ForeignKeyConstraint(["room_id"], ["hotel_rooms.id"]),
        sa.ForeignKeyConstraint(["reported_by"], ["users.id"]),
        sa.ForeignKeyConstraint(["assigned_to"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticket_number"),
    )
    op.create_index(op.f("ix_maintenance_tickets_tenant_id"), "maintenance_tickets", ["tenant_id"], unique=False)
    op.create_index(op.f("ix_maintenance_tickets_outlet_id"), "maintenance_tickets", ["outlet_id"], unique=False)
    op.create_index(op.f("ix_maintenance_tickets_room_id"), "maintenance_tickets", ["room_id"], unique=False)
    op.create_index(op.f("ix_maintenance_tickets_ticket_number"), "maintenance_tickets", ["ticket_number"], unique=False)
    op.create_index(op.f("ix_maintenance_tickets_assigned_to"), "maintenance_tickets", ["assigned_to"], unique=False)

    op.create_table(
        "ticket_comments",
        sa.Column("ticket_id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("comment", sa.Text(), nullable=False),
        *_ts_cols(),
        sa.ForeignKeyConstraint(["ticket_id"], ["maintenance_tickets.id"]),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_ticket_comments_ticket_id"), "ticket_comments", ["ticket_id"], unique=False)


def downgrade() -> None:
    op.drop_table("ticket_comments")
    op.drop_table("maintenance_tickets")
    op.drop_table("task_checklist_items")
    op.drop_table("housekeeping_tasks")
    op.drop_table("checklist_template_items")
    op.drop_table("checklist_templates")
    op.drop_table("hotel_rooms")
    op.drop_table("room_types")
    op.execute("DROP TYPE IF EXISTS maintenanceticketstatus")
    op.execute("DROP TYPE IF EXISTS maintenancecategory")
    op.execute("DROP TYPE IF EXISTS maintenancepriority")
    op.execute("DROP TYPE IF EXISTS housekeepingtaskstatus")
    op.execute("DROP TYPE IF EXISTS housekeepingtasktype")
    op.execute("DROP TYPE IF EXISTS roomstatus")
