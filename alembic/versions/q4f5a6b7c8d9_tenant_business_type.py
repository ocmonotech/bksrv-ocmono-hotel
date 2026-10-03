"""Add tenant business_type for navigation and module visibility."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "q4f5a6b7c8d9"
down_revision: Union[str, None] = "p3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "tenants",
        sa.Column(
            "business_type",
            sa.Enum("resort", "multichain", "cafe", "restaurant", name="businesstype"),
            nullable=False,
            server_default="resort",
        ),
    )


def downgrade() -> None:
    op.drop_column("tenants", "business_type")
    op.execute("DROP TYPE IF EXISTS businesstype")
