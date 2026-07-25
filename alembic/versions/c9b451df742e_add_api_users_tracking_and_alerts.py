"""add API users, tracking, alerts, and product lifecycle

Revision ID: c9b451df742e
Revises: a0f3eecca880
Create Date: 2026-07-23 12:00:00
"""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op


revision: str = "c9b451df742e"
down_revision: str | Sequence[str] | None = "a0f3eecca880"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column("products", sa.Column("identity_key", sa.String(512), nullable=True))
    op.add_column(
        "products",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "products",
        sa.Column("deleted_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.execute(
        """
        UPDATE products
        SET identity_key =
            lower(regexp_replace(trim(brand), '\\s+', ' ', 'g')) || chr(31) ||
            lower(regexp_replace(trim(model), '\\s+', ' ', 'g')) || chr(31) ||
            lower(regexp_replace(COALESCE(storage, ''), '\\s+', '', 'g')) || chr(31) ||
            lower(regexp_replace(trim(COALESCE(color, '')), '\\s+', ' ', 'g'))
        """
    )
    op.alter_column("products", "identity_key", nullable=False)
    op.drop_index("uq_product_identity", table_name="products")
    op.create_unique_constraint(
        "uq_products_identity_key",
        "products",
        ["identity_key"],
    )

    op.alter_column(
        "product_listing",
        "current_price",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "price_history",
        "price",
        existing_type=sa.Numeric(10, 2),
        type_=sa.Numeric(12, 2),
        existing_nullable=False,
    )
    op.add_column(
        "product_listing",
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
    )
    op.add_column(
        "price_history",
        sa.Column(
            "is_available",
            sa.Boolean(),
            server_default=sa.true(),
            nullable=False,
        ),
    )

    op.create_table(
        "users",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("email", sa.String(320), nullable=False),
        sa.Column("password_hash", sa.String(512), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("is_admin", sa.Boolean(), server_default=sa.false(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email", name="uq_users_email"),
    )
    op.create_index("ix_users_email", "users", ["email"], unique=False)

    op.create_table(
        "tracked_products",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_tracked_product_user_product",
        ),
    )
    op.create_index(
        "ix_tracked_products_user_id",
        "tracked_products",
        ["user_id"],
    )
    op.create_index(
        "ix_tracked_products_product_id",
        "tracked_products",
        ["product_id"],
    )

    op.create_table(
        "price_alerts",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("product_id", sa.Integer(), nullable=False),
        sa.Column("target_price", sa.Numeric(12, 2), nullable=False),
        sa.Column("currency", sa.String(3), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.CheckConstraint(
            "target_price > 0",
            name="ck_price_alert_target_price_positive",
        ),
        sa.CheckConstraint(
            "currency ~ '^[A-Z]{3}$'",
            name="ck_price_alert_currency_format",
        ),
        sa.ForeignKeyConstraint(["product_id"], ["products.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "user_id",
            "product_id",
            name="uq_price_alert_user_product",
        ),
    )
    op.create_index("ix_price_alerts_user_id", "price_alerts", ["user_id"])
    op.create_index("ix_price_alerts_product_id", "price_alerts", ["product_id"])

    op.create_index(
        "uq_crawl_runs_store_running",
        "crawl_runs",
        ["store_id"],
        unique=True,
        postgresql_where=sa.text("status = 'running'"),
    )


def downgrade() -> None:
    op.drop_index("uq_crawl_runs_store_running", table_name="crawl_runs")
    op.drop_index("ix_price_alerts_product_id", table_name="price_alerts")
    op.drop_index("ix_price_alerts_user_id", table_name="price_alerts")
    op.drop_table("price_alerts")
    op.drop_index("ix_tracked_products_product_id", table_name="tracked_products")
    op.drop_index("ix_tracked_products_user_id", table_name="tracked_products")
    op.drop_table("tracked_products")
    op.drop_index("ix_users_email", table_name="users")
    op.drop_table("users")

    op.drop_column("price_history", "is_available")
    op.drop_column("product_listing", "is_active")
    op.alter_column(
        "price_history",
        "price",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.alter_column(
        "product_listing",
        "current_price",
        existing_type=sa.Numeric(12, 2),
        type_=sa.Numeric(10, 2),
        existing_nullable=False,
    )
    op.drop_constraint("uq_products_identity_key", "products", type_="unique")
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
    op.drop_column("products", "deleted_at")
    op.drop_column("products", "is_active")
    op.drop_column("products", "identity_key")
