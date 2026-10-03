"""PMS full room booking — blocks, groups, night audit, stay modifiers."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect


revision: str = "u8v9w0x1y2z3"
down_revision: Union[str, None] = "t7u8v9w0x1y2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _ts_cols():
    return [
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
    ]


def _has_table(name: str) -> bool:
    bind = op.get_bind()
    return name in inspect(bind).get_table_names()


def _has_column(table: str, column: str) -> bool:
    bind = op.get_bind()
    cols = {c["name"] for c in inspect(bind).get_columns(table)}
    return column in cols


TRIGGER_VALUES = (
    "NEW_CUSTOMER_ADDED",
    "CUSTOMER_BIRTHDAY",
    "NO_VISIT_30_DAYS",
    "NEW_WHATSAPP_MESSAGE",
    "CAMPAIGN_REPLY_RECEIVED",
    "NEGATIVE_FEEDBACK_RECEIVED",
    "RESERVATION_CREATED",
    "BILL_GENERATED",
    "SPA_BOOKING_CREATED",
    "SPA_BOOKING_CONFIRMED",
    "BANQUET_BOOKING_CREATED",
    "BANQUET_BOOKING_CONFIRMED",
    "GUEST_RESERVATION_CONFIRMED",
    "GUEST_RESERVATION_CHECKED_OUT",
    "EVENT_CONFIRMED",
)

TRIGGER_VALUES_DOWN = (
    "NEW_CUSTOMER_ADDED",
    "CUSTOMER_BIRTHDAY",
    "NO_VISIT_30_DAYS",
    "NEW_WHATSAPP_MESSAGE",
    "CAMPAIGN_REPLY_RECEIVED",
    "NEGATIVE_FEEDBACK_RECEIVED",
    "RESERVATION_CREATED",
    "BILL_GENERATED",
    "SPA_BOOKING_CREATED",
    "SPA_BOOKING_CONFIRMED",
    "BANQUET_BOOKING_CREATED",
    "BANQUET_BOOKING_CONFIRMED",
    "GUEST_RESERVATION_CONFIRMED",
    "EVENT_CONFIRMED",
)


def upgrade() -> None:
    if not _has_table("reservation_groups"):
        op.create_table(
            "reservation_groups",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("brand_id", sa.Integer(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), nullable=False),
            sa.Column("group_code", sa.String(length=32), nullable=False),
            sa.Column("name", sa.String(length=255), nullable=False),
            sa.Column("shared_deposit", sa.Numeric(precision=12, scale=2), server_default="0", nullable=False),
            sa.Column("notes", sa.Text(), nullable=True),
            sa.Column("customer_id", sa.Integer(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
            sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
            sa.ForeignKeyConstraint(["customer_id"], ["customers.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint("tenant_id", "group_code", name="uq_reservation_group_tenant_code"),
        )
        op.create_index("ix_reservation_groups_tenant_id", "reservation_groups", ["tenant_id"])
        op.create_index("ix_reservation_groups_outlet_id", "reservation_groups", ["outlet_id"])
        op.create_index("ix_reservation_groups_group_code", "reservation_groups", ["group_code"])
        op.create_index("ix_reservation_groups_customer_id", "reservation_groups", ["customer_id"])

    if not _has_table("room_blocks"):
        op.create_table(
            "room_blocks",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("brand_id", sa.Integer(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), nullable=False),
            sa.Column("room_id", sa.Integer(), nullable=False),
            sa.Column("start_date", sa.Date(), nullable=False),
            sa.Column("end_date", sa.Date(), nullable=False),
            sa.Column(
                "block_type",
                sa.Enum("MAINTENANCE", "HOLD", "VIP", "OTHER", name="roomblocktype"),
                nullable=False,
            ),
            sa.Column("reason", sa.Text(), nullable=True),
            sa.Column("created_by", sa.Integer(), nullable=True),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
            sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
            sa.ForeignKeyConstraint(["room_id"], ["hotel_rooms.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index("ix_room_blocks_tenant_id", "room_blocks", ["tenant_id"])
        op.create_index("ix_room_blocks_outlet_id", "room_blocks", ["outlet_id"])
        op.create_index("ix_room_blocks_room_id", "room_blocks", ["room_id"])
        op.create_index("ix_room_blocks_start_date", "room_blocks", ["start_date"])
        op.create_index("ix_room_blocks_end_date", "room_blocks", ["end_date"])

    if not _has_table("night_audit_logs"):
        op.create_table(
            "night_audit_logs",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("brand_id", sa.Integer(), nullable=True),
            sa.Column("outlet_id", sa.Integer(), nullable=False),
            sa.Column("business_date", sa.Date(), nullable=False),
            sa.Column("ran_at", sa.DateTime(), nullable=False),
            sa.Column("rooms_posted", sa.Integer(), server_default="0", nullable=False),
            sa.Column("no_shows_marked", sa.Integer(), server_default="0", nullable=False),
            sa.Column("arrivals_expected", sa.Integer(), server_default="0", nullable=False),
            sa.Column("summary_json", sa.Text(), nullable=False),
            sa.Column("created_by", sa.Integer(), nullable=True),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
            sa.ForeignKeyConstraint(["outlet_id"], ["outlets.id"]),
            sa.ForeignKeyConstraint(["created_by"], ["users.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "tenant_id",
                "outlet_id",
                "business_date",
                name="uq_night_audit_tenant_outlet_date",
            ),
        )
        op.create_index("ix_night_audit_logs_tenant_id", "night_audit_logs", ["tenant_id"])
        op.create_index("ix_night_audit_logs_outlet_id", "night_audit_logs", ["outlet_id"])
        op.create_index("ix_night_audit_logs_business_date", "night_audit_logs", ["business_date"])

    if not _has_table("ota_rate_plan_mappings"):
        op.create_table(
            "ota_rate_plan_mappings",
            sa.Column("tenant_id", sa.Integer(), nullable=False),
            sa.Column("brand_id", sa.Integer(), nullable=True),
            sa.Column("integration_id", sa.Integer(), nullable=False),
            sa.Column("rate_plan_id", sa.Integer(), nullable=False),
            sa.Column("external_rate_id", sa.String(length=64), nullable=False),
            sa.Column("external_rate_name", sa.String(length=128), nullable=True),
            *_ts_cols(),
            sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
            sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
            sa.ForeignKeyConstraint(
                ["integration_id"],
                ["outlet_ota_integrations.id"],
                ondelete="CASCADE",
            ),
            sa.ForeignKeyConstraint(["rate_plan_id"], ["rate_plans.id"]),
            sa.PrimaryKeyConstraint("id"),
            sa.UniqueConstraint(
                "integration_id",
                "external_rate_id",
                name="uq_ota_rate_plan_external",
            ),
        )
        op.create_index("ix_ota_rate_plan_mappings_tenant_id", "ota_rate_plan_mappings", ["tenant_id"])
        op.create_index(
            "ix_ota_rate_plan_mappings_integration_id",
            "ota_rate_plan_mappings",
            ["integration_id"],
        )
        op.create_index(
            "ix_ota_rate_plan_mappings_rate_plan_id",
            "ota_rate_plan_mappings",
            ["rate_plan_id"],
        )

    if not _has_column("rate_plans", "cancellation_fee_percent"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "cancellation_fee_percent",
                sa.Numeric(precision=5, scale=2),
                server_default="0",
                nullable=False,
            ),
        )
    if not _has_column("rate_plans", "no_show_fee_percent"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "no_show_fee_percent",
                sa.Numeric(precision=5, scale=2),
                server_default="0",
                nullable=False,
            ),
        )
    if not _has_column("rate_plans", "default_guarantee"):
        op.add_column(
            "rate_plans",
            sa.Column(
                "default_guarantee",
                sa.Enum("NONE", "DEPOSIT", "CARD_HOLD", name="guaranteetype"),
                server_default="NONE",
                nullable=False,
            ),
        )

    if not _has_column("guest_reservations", "group_id"):
        op.add_column("guest_reservations", sa.Column("group_id", sa.Integer(), nullable=True))
    if not _has_column("guest_reservations", "guest_id_document"):
        op.add_column(
            "guest_reservations",
            sa.Column("guest_id_document", sa.String(length=64), nullable=True),
        )
    if not _has_column("guest_reservations", "early_check_in"):
        op.add_column(
            "guest_reservations",
            sa.Column("early_check_in", sa.Boolean(), server_default="0", nullable=False),
        )
    if not _has_column("guest_reservations", "late_check_out"):
        op.add_column(
            "guest_reservations",
            sa.Column("late_check_out", sa.Boolean(), server_default="0", nullable=False),
        )
    if not _has_column("guest_reservations", "day_use"):
        op.add_column(
            "guest_reservations",
            sa.Column("day_use", sa.Boolean(), server_default="0", nullable=False),
        )
    if not _has_column("guest_reservations", "guarantee_type"):
        op.add_column(
            "guest_reservations",
            sa.Column(
                "guarantee_type",
                sa.Enum("NONE", "DEPOSIT", "CARD_HOLD", name="guaranteetype", create_type=False),
                server_default="NONE",
                nullable=False,
            ),
        )
    if not _has_column("guest_reservations", "deposit_status"):
        op.add_column(
            "guest_reservations",
            sa.Column(
                "deposit_status",
                sa.Enum(
                    "PENDING",
                    "CAPTURED",
                    "REFUNDED",
                    "FORFEITED",
                    "HELD",
                    name="depositstatus",
                ),
                server_default="PENDING",
                nullable=False,
            ),
        )
        try:
            op.create_foreign_key(
                "fk_guest_reservations_group_id",
                "guest_reservations",
                "reservation_groups",
                ["group_id"],
                ["id"],
            )
        except Exception:
            pass
        try:
            op.create_index("ix_guest_reservations_group_id", "guest_reservations", ["group_id"])
        except Exception:
            pass

    values = ", ".join(f"'{value}'" for value in TRIGGER_VALUES)
    op.execute(
        f"ALTER TABLE automation_rules MODIFY COLUMN trigger_type ENUM({values}) NOT NULL"
    )


def downgrade() -> None:
    values = ", ".join(f"'{value}'" for value in TRIGGER_VALUES_DOWN)
    op.execute(
        f"ALTER TABLE automation_rules MODIFY COLUMN trigger_type ENUM({values}) NOT NULL"
    )

    if _has_column("guest_reservations", "group_id"):
        try:
            op.drop_index("ix_guest_reservations_group_id", table_name="guest_reservations")
        except Exception:
            pass
        try:
            op.drop_constraint("fk_guest_reservations_group_id", "guest_reservations", type_="foreignkey")
        except Exception:
            pass
    for col in (
        "deposit_status",
        "guarantee_type",
        "day_use",
        "late_check_out",
        "early_check_in",
        "guest_id_document",
        "group_id",
    ):
        if _has_column("guest_reservations", col):
            op.drop_column("guest_reservations", col)

    for col in ("default_guarantee", "no_show_fee_percent", "cancellation_fee_percent"):
        if _has_column("rate_plans", col):
            op.drop_column("rate_plans", col)

    if _has_table("ota_rate_plan_mappings"):
        op.drop_table("ota_rate_plan_mappings")
    if _has_table("night_audit_logs"):
        op.drop_table("night_audit_logs")
    if _has_table("room_blocks"):
        op.drop_table("room_blocks")
    if _has_table("reservation_groups"):
        op.drop_table("reservation_groups")
