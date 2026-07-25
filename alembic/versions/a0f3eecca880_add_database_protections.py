"""add_database_protections

Revision ID: a0f3eecca880
Revises: f2c104a01b2e
Create Date: 2026-07-22 22:50:48.292577

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a0f3eecca880'
down_revision: Union[str, Sequence[str], None] = 'f2c104a01b2e'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Add CHECK constraints for price fields
    op.create_check_constraint(
        "ck_product_listing_current_price_positive",
        "product_listing",
        "current_price > 0"
    )
    op.create_check_constraint(
        "ck_price_history_price_positive",
        "price_history",
        "price > 0"
    )
    
    # Add index on price_history(listing_id, recorded_at)
    op.create_index(
        "ix_price_history_listing_id_recorded_at",
        "price_history",
        ["listing_id", "recorded_at"]
    )
    
    # Add availability fields to product_listing
    op.add_column(
        "product_listing",
        sa.Column("is_available", sa.Boolean(), nullable=False, server_default="true")
    )
    op.add_column(
        "product_listing",
        sa.Column("last_seen_at", sa.DateTime(timezone=True), nullable=True)
    )
    
    # Add variant and external ID columns to product_listing
    op.add_column(
        "product_listing",
        sa.Column("variant_name", sa.String(length=100), nullable=True)
    )
    op.add_column(
        "product_listing",
        sa.Column("external_product_id", sa.String(length=100), nullable=True)
    )
    
    # Add unique index for external_product_id per store (only when not null)
    op.create_index(
        "uq_store_external_product_id",
        "product_listing",
        ["store_id", "external_product_id"],
        unique=True,
        postgresql_where=sa.text("external_product_id IS NOT NULL")
    )


def downgrade() -> None:
    """Downgrade schema."""
    # Drop unique index for external_product_id per store
    op.drop_index("uq_store_external_product_id", table_name="product_listing")
    
    # Drop variant and external ID columns
    op.drop_column("product_listing", "external_product_id")
    op.drop_column("product_listing", "variant_name")
    
    # Drop availability fields
    op.drop_column("product_listing", "last_seen_at")
    op.drop_column("product_listing", "is_available")
    
    # Drop index on price_history
    op.drop_index("ix_price_history_listing_id_recorded_at", table_name="price_history")
    
    # Drop CHECK constraints
    op.drop_constraint("ck_price_history_price_positive", "price_history", type_="check")
    op.drop_constraint("ck_product_listing_current_price_positive", "product_listing", type_="check")
