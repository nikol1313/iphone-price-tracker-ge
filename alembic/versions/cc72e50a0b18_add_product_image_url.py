"""add product image URLs

Revision ID: cc72e50a0b18
Revises: e6c43a9d107b
Create Date: 2026-10-16 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "cc72e50a0b18"
down_revision: str | Sequence[str] | None = "e6c43a9d107b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("image_url", sa.String(length=1000), nullable=True))


def downgrade() -> None:
    op.drop_column("products", "image_url")
