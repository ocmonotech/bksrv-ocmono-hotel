"""Guest service requests and room-hub support.

Revision ID: g0a1b2c3d4e5
Revises: f9a0b1c2d3e4
Create Date: 2026-07-13 11:30:00.000000
"""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "g0a1b2c3d4e5"
down_revision: Union[str, None] = "f9a0b1c2d3e4"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _has_table(table: str) -> bool:
    return table in inspect(op.get_bind()).get_table_names()


def upgrade() -> None:
    bind = op.get_bind()
    dialect = bind.dialect.name

    if dialect == "mysql":
        op.execute(
            "ALTER TABLE checklist_templates MODIFY task_type "
            "ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION','GUEST_REQUEST') NOT NULL"
        )
        op.execute(
            "ALTER TABLE housekeeping_tasks MODIFY task_type "
            "ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION','GUEST_REQUEST') NOT NULL"
        )
        op.execute("ALTER TABLE maintenance_tickets MODIFY reported_by INT NULL")
    else:
        with op.batch_alter_table("maintenance_tickets") as batch:
            batch.alter_column("reported_by", existing_type=sa.Integer(), nullable=True)

    if not _has_table("guest_service_requests"):
        op.create_table(
            "guest_service_requests",
            sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
            sa.Column("tenant_id", sa.Integer(), sa.ForeignKey("tenants.id"), nullable=False, index=True),
            sa.Column("brand_id", sa.Integer(), sa.ForeignKey("brands.id"), nullable=True, index=True),
            sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=True),
            sa.Column("updated_at", sa.DateTime(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), sa.ForeignKey("outlets.id"), nullable=False, index=True),
            sa.Column("room_id", sa.Integer(), sa.ForeignKey("hotel_rooms.id"), nullable=False, index=True),
            sa.Column("room_number", sa.String(32), nullable=False, index=True),
            sa.Column(
                "reservation_id",
                sa.Integer(),
                sa.ForeignKey("guest_reservations.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("category", sa.String(32), nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("guest_mobile", sa.String(32), nullable=True),
            sa.Column("status", sa.String(16), nullable=False, server_default="open"),
            sa.Column(
                "linked_task_id",
                sa.Integer(),
                sa.ForeignKey("housekeeping_tasks.id"),
                nullable=True,
                index=True,
            ),
            sa.Column(
                "linked_ticket_id",
                sa.Integer(),
                sa.ForeignKey("maintenance_tickets.id"),
                nullable=True,
                index=True,
            ),
            sa.Column("fulfilled_at", sa.DateTime(), nullable=True),
            sa.Column("fulfilled_by", sa.Integer(), sa.ForeignKey("users.id"), nullable=True),
        )


def downgrade() -> None:
    if _has_table("guest_service_requests"):
        op.drop_table("guest_service_requests")

    bind = op.get_bind()
    dialect = bind.dialect.name
    if dialect == "mysql":
        op.execute(
            "ALTER TABLE checklist_templates MODIFY task_type "
            "ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION') NOT NULL"
        )
        op.execute(
            "ALTER TABLE housekeeping_tasks MODIFY task_type "
            "ENUM('CHECKOUT','DAILY','DEEP_CLEAN','TURNDOWN','INSPECTION') NOT NULL"
        )
        op.execute("ALTER TABLE maintenance_tickets MODIFY reported_by INT NOT NULL")
    else:
        with op.batch_alter_table("maintenance_tickets") as batch:
            batch.alter_column("reported_by", existing_type=sa.Integer(), nullable=False)
