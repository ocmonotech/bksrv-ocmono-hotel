"""Add room type catalog fields for guest portal (images, bed, size)."""

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy import inspect, text


revision: str = "c6d7e8f9a0b1"
down_revision: Union[str, None] = "b5c6d7e8f9a0"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _columns(table: str) -> set[str]:
    bind = op.get_bind()
    return {col["name"] for col in inspect(bind).get_columns(table)}


def upgrade() -> None:
    cols = _columns("room_types")
    if "image_url" not in cols:
        op.add_column("room_types", sa.Column("image_url", sa.String(512), nullable=True))
    if "gallery_urls" not in cols:
        op.add_column("room_types", sa.Column("gallery_urls", sa.Text(), nullable=True))
    if "bed_type" not in cols:
        op.add_column("room_types", sa.Column("bed_type", sa.String(64), nullable=True))
    if "room_size_sqft" not in cols:
        op.add_column("room_types", sa.Column("room_size_sqft", sa.Integer(), nullable=True))

    # Widen description for marketing copy on guest portal.
    bind = op.get_bind()
    if bind.dialect.name == "mysql":
        op.execute(text("ALTER TABLE room_types MODIFY COLUMN description TEXT NULL"))
    else:
        op.alter_column(
            "room_types",
            "description",
            existing_type=sa.String(255),
            type_=sa.Text(),
            existing_nullable=True,
        )


def downgrade() -> None:
    cols = _columns("room_types")
    for name in ("room_size_sqft", "bed_type", "gallery_urls", "image_url"):
        if name in cols:
            op.drop_column("room_types", name)
