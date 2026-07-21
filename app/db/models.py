from datetime import datetime
from decimal import Decimal

from sqlalchemy import (
    CheckConstraint,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.sess import Base


class Store(Base):
    __tablename__ = "stores"
    __table_args__ = (UniqueConstraint("title", name="uq_store_title"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    title: Mapped[str] = mapped_column(String(100))
    web_url: Mapped[str] = mapped_column(String(500))

    listings: Mapped[list["ProductListing"]] = relationship(
        back_populates="store",
        cascade="all, delete-orphan",
    )
    crawl_runs: Mapped[list["CrawlRun"]] = relationship(
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

    __table_args__ = (
        Index(
            "uq_product_identity",
            brand,
            model,
            func.coalesce(storage, ""),
            func.coalesce(color, ""),
            unique=True,
        ),
    )

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


class CrawlRun(Base):
    __tablename__ = "crawl_runs"
    __table_args__ = (
        CheckConstraint(
            "status IN ('running', 'succeeded', 'failed')",
            name="ck_crawl_run_status",
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    store_id: Mapped[int] = mapped_column(
        ForeignKey("stores.id", ondelete="CASCADE"),
        index=True,
        nullable=False,
    )
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
    )
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    products_found: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    products_ingested: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(2000))

    store: Mapped["Store"] = relationship(back_populates="crawl_runs")
