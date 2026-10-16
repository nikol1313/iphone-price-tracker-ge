"""add Telegram notification settings and delivery state

Revision ID: e6c43a9d107b
Revises: c9b451df742e
Create Date: 2026-07-30 00:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "e6c43a9d107b"
down_revision: str | Sequence[str] | None = "c9b451df742e"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "users",
        sa.Column("telegram_chat_id", sa.String(length=32), nullable=True),
    )
    op.add_column(
        "price_alerts",
        sa.Column("notified_at", sa.DateTime(timezone=True), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("price_alerts", "notified_at")
    op.drop_column("users", "telegram_chat_id")
