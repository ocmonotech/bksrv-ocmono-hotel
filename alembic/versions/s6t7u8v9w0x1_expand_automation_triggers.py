"""Expand automation trigger_type enum for spa, banquet, and PMS."""

from typing import Sequence, Union

from alembic import op


revision: str = "s6t7u8v9w0x1"
down_revision: Union[str, None] = "r5s6t7u8v9w0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


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
    "EVENT_CONFIRMED",
)


def upgrade() -> None:
    values = ", ".join(f"'{value}'" for value in TRIGGER_VALUES)
    op.execute(
        f"ALTER TABLE automation_rules MODIFY COLUMN trigger_type ENUM({values}) NOT NULL"
    )


def downgrade() -> None:
    legacy = (
        "NEW_CUSTOMER_ADDED",
        "CUSTOMER_BIRTHDAY",
        "NO_VISIT_30_DAYS",
        "NEW_WHATSAPP_MESSAGE",
        "CAMPAIGN_REPLY_RECEIVED",
        "NEGATIVE_FEEDBACK_RECEIVED",
        "RESERVATION_CREATED",
        "BILL_GENERATED",
    )
    values = ", ".join(f"'{value}'" for value in legacy)
    op.execute(
        f"ALTER TABLE automation_rules MODIFY COLUMN trigger_type ENUM({values}) NOT NULL"
    )
