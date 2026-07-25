"""add crawl runs and unique identities

Revision ID: f2c104a01b2e
Revises: d6afffe3e842
Create Date: 2026-07-21 21:10:00

"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "f2c104a01b2e"
down_revision: str | Sequence[str] | None = "d6afffe3e842"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_unique_constraint("uq_store_title", "stores", ["title"])
    op.create_index(
        "uq_product_identity",
        "products",
        [
            "brand",
            "model",
            sa.text("COALESCE(storage, '')"),
            sa.text("COALESCE(color, '')"),
        ],
        unique=True,
    )
    op.create_table(
        "crawl_runs",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("store_id", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(length=20), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("finished_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("products_found", sa.Integer(), nullable=False),
        sa.Column("products_ingested", sa.Integer(), nullable=False),
        sa.Column("error_message", sa.String(length=2000), nullable=True),
        sa.CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_crawl_run_status",
        ),
        sa.ForeignKeyConstraint(
            ["store_id"],
            ["stores.id"],
            ondelete="CASCADE",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_crawl_runs_store_id"),
        "crawl_runs",
        ["store_id"],
        unique=False,
    )


def downgrade() -> None:
    op.drop_index(op.f("ix_crawl_runs_store_id"), table_name="crawl_runs")
    op.drop_table("crawl_runs")
    op.drop_index("uq_product_identity", table_name="products")
    op.drop_constraint("uq_store_title", "stores", type_="unique")
