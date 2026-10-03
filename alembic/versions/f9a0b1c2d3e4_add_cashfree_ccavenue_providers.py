"""Add Cashfree and CCAvenue payment providers.

Revision ID: f9a0b1c2d3e4
Revises: e8f9a0b1c2d3
Create Date: 2026-07-13 11:10:00.000000
"""

from typing import Sequence, Union

from alembic import op


revision: str = "f9a0b1c2d3e4"
down_revision: Union[str, None] = "e8f9a0b1c2d3"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.execute(
        "ALTER TABLE outlet_payment_integrations MODIFY provider "
        "ENUM('PINELABS','RAZORPAY','PAYTM','PHONEPE','CASHFREE','CCAVENUE') NOT NULL"
    )


def downgrade() -> None:
    op.execute(
        "ALTER TABLE outlet_payment_integrations MODIFY provider "
        "ENUM('PINELABS','RAZORPAY','PAYTM','PHONEPE') NOT NULL"
    )
