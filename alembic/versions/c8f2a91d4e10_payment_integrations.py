"""payment integrations

Revision ID: c8f2a91d4e10
Revises: 42a1bd96c8bb
Create Date: 2026-06-18 18:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c8f2a91d4e10"
down_revision: Union[str, None] = "e7b2c9d41f6a"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "outlet_payment_integrations",
        sa.Column("outlet_id", sa.Integer(), nullable=False),
        sa.Column(
            "provider",
            sa.Enum("PINELABS", "RAZORPAY", "PAYTM", "PHONEPE", name="paymentprovider"),
            nullable=False,
        ),
        sa.Column("merchant_id", sa.String(length=64), nullable=True),
        sa.Column("store_id", sa.String(length=64), nullable=True),
        sa.Column("client_id", sa.String(length=64), nullable=True),
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
        sa.Column("auto_settle_on_success", sa.Boolean(), nullable=False),
        sa.Column("webhook_token", sa.String(length=64), nullable=False),
        sa.Column("config_json", sa.Text(), nullable=False),
        sa.Column("encrypted_security_token", sa.Text(), nullable=True),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
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
        sa.UniqueConstraint("outlet_id", "provider", name="uq_outlet_payment_provider"),
    )
    op.create_index(
        op.f("ix_outlet_payment_integrations_brand_id"),
        "outlet_payment_integrations",
        ["brand_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_payment_integrations_outlet_id"),
        "outlet_payment_integrations",
        ["outlet_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_payment_integrations_tenant_id"),
        "outlet_payment_integrations",
        ["tenant_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_outlet_payment_integrations_webhook_token"),
        "outlet_payment_integrations",
        ["webhook_token"],
        unique=True,
    )

    op.create_table(
        "terminal_payments",
        sa.Column("integration_id", sa.Integer(), nullable=False),
        sa.Column("bill_id", sa.Integer(), nullable=False),
        sa.Column("pos_payment_id", sa.Integer(), nullable=True),
        sa.Column("transaction_number", sa.String(length=64), nullable=False),
        sa.Column("sequence_number", sa.Integer(), nullable=False),
        sa.Column("amount", sa.Numeric(precision=12, scale=2), nullable=False),
        sa.Column(
            "payment_mode",
            sa.Enum(
                "CASH",
                "UPI",
                "CARD",
                "ONLINE",
                "SPLIT",
                name="paymentmode",
                create_type=False,
            ),
            nullable=False,
        ),
        sa.Column("allowed_payment_mode", sa.String(length=32), nullable=True),
        sa.Column(
            "status",
            sa.Enum(
                "INITIATED",
                "PENDING_TERMINAL",
                "SUCCESS",
                "FAILED",
                "CANCELLED",
                name="terminalpaymentstatus",
            ),
            nullable=False,
        ),
        sa.Column("provider_reference_id", sa.String(length=64), nullable=True),
        sa.Column("auth_code", sa.String(length=64), nullable=True),
        sa.Column("reference_number", sa.String(length=128), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("raw_request_json", sa.Text(), nullable=False),
        sa.Column("raw_response_json", sa.Text(), nullable=False),
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("updated_at", sa.DateTime(), server_default=sa.text("(CURRENT_TIMESTAMP)"), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default="1", nullable=False),
        sa.Column("tenant_id", sa.Integer(), nullable=False),
        sa.Column("brand_id", sa.Integer(), nullable=True),
        sa.ForeignKeyConstraint(["bill_id"], ["pos_bills.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["brand_id"], ["brands.id"]),
        sa.ForeignKeyConstraint(["integration_id"], ["outlet_payment_integrations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["pos_payment_id"], ["pos_payments.id"], ondelete="SET NULL"),
        sa.ForeignKeyConstraint(["tenant_id"], ["tenants.id"]),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "integration_id",
            "transaction_number",
            "sequence_number",
            name="uq_terminal_payment_sequence",
        ),
    )
    op.create_index(op.f("ix_terminal_payments_bill_id"), "terminal_payments", ["bill_id"], unique=False)
    op.create_index(
        op.f("ix_terminal_payments_brand_id"), "terminal_payments", ["brand_id"], unique=False
    )
    op.create_index(
        op.f("ix_terminal_payments_integration_id"),
        "terminal_payments",
        ["integration_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_terminal_payments_provider_reference_id"),
        "terminal_payments",
        ["provider_reference_id"],
        unique=False,
    )
    op.create_index(
        op.f("ix_terminal_payments_tenant_id"), "terminal_payments", ["tenant_id"], unique=False
    )
    op.create_index(
        op.f("ix_terminal_payments_transaction_number"),
        "terminal_payments",
        ["transaction_number"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_table("terminal_payments")
    op.drop_table("outlet_payment_integrations")
    op.execute("DROP TYPE IF EXISTS terminalpaymentstatus")
    op.execute("DROP TYPE IF EXISTS paymentprovider")
