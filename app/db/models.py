from datetime import datetime
from decimal import Decimal

from sqlalchemy import DateTime, ForeignKey, Numeric, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sess import Base


class Store(Base):
    __tablename__ = "stores"

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    web_url: Mapped[str] = mapped_column(String(500))

    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
    )


class Product(Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand: Mapped[str] = mapped_column(String(50), nullable=False)
    model: Mapped[str] = mapped_column(String(200), nullable=False)
    storage: Mapped[str | None] = mapped_column(String(20))
    color: Mapped[str | None] = mapped_column(String(50))

    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="product",
        cascade="all, delete-orphan",
    )


class ProductListing(Base):
    __tablename__ = "product_listing"
    __table_args__ = (
        UniqueConstraint(
            "store_id",
            "product_id",
            name="uq_store_product_listing",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)

    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        nullable=False,
    )
    product_id: Mapped[int] = mapped_column(
        ForeignKey("products.id", ondelete="CASCADE"),
        nullable=False,
    )

    product_url: Mapped[str] = mapped_column(String(500), nullable=False)
    current_price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GEL", nullable=False)
    last_checked_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    store: Mapped["Store"] = relationship(back_populates="listings")
    product: Mapped["Product"] = relationship(back_populates="listings")
    price_history: Mapped[list["PriceHist"]] = relationship(
        back_populates="listing",
        cascade="all, delete-orphan",
    )


class PriceHist(Base):
    __tablename__ = "price_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    listing_id: Mapped[int] = mapped_column(
        ForeignKey("product_listing.id", ondelete="CASCADE"),
        nullable=False,
    )
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2))
    currency: Mapped[str] = mapped_column(String(3), default="GEL", nullable=False)
    recorded_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
        nullable=False,
    )

    listing: Mapped["ProductListing"] = relationship(back_populates="price_history")