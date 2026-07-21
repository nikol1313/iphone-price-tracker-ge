from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy import select
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.db.db_schemas import (
    PriceHistCreate,
    ProductCreate,
    ProductListingCreate,
    StoreCreate,
)
from app.db.models import CrawlRun, PriceHist, Product, ProductListing, Store


def _normalize_optional(value: str | None) -> str | None:
    if value is None:
        return None

    stripped_value = value.strip()
    return stripped_value or None


def _normalize_currency(currency: str) -> str:
    return currency.strip().upper()


async def get_store(session: AsyncSession, store_id: int) -> Store | None:
    return await session.get(Store, store_id)


async def get_store_by_title(session: AsyncSession, title: str) -> Store | None:
    statement = select(Store).where(Store.title == title.strip())
    return await session.scalar(statement)


async def create_store(session: AsyncSession, store_data: StoreCreate) -> Store:
    store = Store(title=store_data.title, web_url=store_data.web_url)
    session.add(store)
    await session.flush()
    return store


async def get_or_create_store(session: AsyncSession, store_data: StoreCreate) -> Store:
    statement = (
        insert(Store)
        .values(title=store_data.title, web_url=store_data.web_url)
        .on_conflict_do_nothing()
        .returning(Store)
    )
    store = await session.scalar(statement)

    if store is None:
        store = await get_store_by_title(session, store_data.title)

    if store is None:
        raise RuntimeError("Store upsert completed without returning a row")

    return store


async def get_product(session: AsyncSession, product_id: int) -> Product | None:
    return await session.get(Product, product_id)


async def get_product_by_details(
    session: AsyncSession,
    *,
    brand: str,
    model: str,
    storage: str | None = None,
    color: str | None = None,
) -> Product | None:
    normalized_storage = _normalize_optional(storage)
    normalized_color = _normalize_optional(color)
    statement = select(Product).where(
        Product.brand == brand.strip(),
        Product.model == model.strip(),
    )

    if normalized_storage is None:
        statement = statement.where(Product.storage.is_(None))
    else:
        statement = statement.where(Product.storage == normalized_storage)

    if normalized_color is None:
        statement = statement.where(Product.color.is_(None))
    else:
        statement = statement.where(Product.color == normalized_color)

    return await session.scalar(statement)


async def create_product(session: AsyncSession, product_data: ProductCreate) -> Product:
    product = Product(
        brand=product_data.brand,
        model=product_data.model,
        storage=_normalize_optional(product_data.storage),
        color=_normalize_optional(product_data.color),
    )
    session.add(product)
    await session.flush()
    return product


async def get_or_create_product(
    session: AsyncSession,
    product_data: ProductCreate,
) -> Product:
    statement = (
        insert(Product)
        .values(
            brand=product_data.brand,
            model=product_data.model,
            storage=_normalize_optional(product_data.storage),
            color=_normalize_optional(product_data.color),
        )
        .on_conflict_do_nothing()
        .returning(Product)
    )
    product = await session.scalar(statement)

    if product is None:
        product = await get_product_by_details(
            session,
            brand=product_data.brand,
            model=product_data.model,
            storage=product_data.storage,
            color=product_data.color,
        )

    if product is None:
        raise RuntimeError("Product upsert completed without returning a row")

    return product


async def get_crawl_run(
    session: AsyncSession,
    crawl_run_id: int,
) -> CrawlRun | None:
    return await session.get(CrawlRun, crawl_run_id)


async def create_crawl_run(session: AsyncSession, store_id: int) -> CrawlRun:
    crawl_run = CrawlRun(
        store_id=store_id,
        status="running",
        started_at=datetime.now(UTC),
        products_found=0,
        products_ingested=0,
    )
    session.add(crawl_run)
    await session.flush()
    return crawl_run


async def complete_crawl_run(
    session: AsyncSession,
    crawl_run_id: int,
    *,
    products_found: int,
    products_ingested: int,
) -> CrawlRun:
    crawl_run = await get_crawl_run(session, crawl_run_id)

    if crawl_run is None:
        raise LookupError(f"Crawl run {crawl_run_id} does not exist")

    crawl_run.status = "succeeded"
    crawl_run.finished_at = datetime.now(UTC)
    crawl_run.products_found = products_found
    crawl_run.products_ingested = products_ingested
    crawl_run.error_message = None
    await session.flush()
    return crawl_run


async def fail_crawl_run(
    session: AsyncSession,
    crawl_run_id: int,
    error: Exception,
    *,
    products_found: int = 0,
) -> CrawlRun:
    crawl_run = await get_crawl_run(session, crawl_run_id)

    if crawl_run is None:
        raise LookupError(f"Crawl run {crawl_run_id} does not exist")

    crawl_run.status = "failed"
    crawl_run.finished_at = datetime.now(UTC)
    crawl_run.products_found = products_found
    crawl_run.products_ingested = 0
    crawl_run.error_message = f"{type(error).__name__}: {error}"[:2000]
    await session.flush()
    return crawl_run


async def get_product_listing(
    session: AsyncSession,
    listing_id: int,
) -> ProductListing | None:
    return await session.get(ProductListing, listing_id)


async def get_listing_by_store_product(
    session: AsyncSession,
    *,
    store_id: int,
    product_id: int,
) -> ProductListing | None:
    statement = select(ProductListing).where(
        ProductListing.store_id == store_id,
        ProductListing.product_id == product_id,
    )
    return await session.scalar(statement)


async def create_product_listing(
    session: AsyncSession,
    listing_data: ProductListingCreate,
) -> ProductListing:
    listing = ProductListing(
        store_id=listing_data.store_id,
        product_id=listing_data.product_id,
        product_url=listing_data.product_url,
        current_price=listing_data.current_price,
        currency=_normalize_currency(listing_data.currency),
        last_checked_at=datetime.now(UTC),
    )
    session.add(listing)
    await session.flush()
    return listing


async def create_price_history(
    session: AsyncSession,
    price_history_data: PriceHistCreate,
) -> PriceHist:
    price_history = PriceHist(
        listing_id=price_history_data.listing_id,
        price=price_history_data.price,
        currency=_normalize_currency(price_history_data.currency),
        recorded_at=datetime.now(UTC),
    )
    session.add(price_history)
    await session.flush()
    return price_history


async def upsert_product_listing(
    session: AsyncSession,
    listing_data: ProductListingCreate,
    *,
    record_unchanged_price: bool = False,
) -> ProductListing:
    listing = await get_listing_by_store_product(
        session,
        store_id=listing_data.store_id,
        product_id=listing_data.product_id,
    )
    price = Decimal(listing_data.current_price)
    currency = _normalize_currency(listing_data.currency)

    if listing is None:
        listing = await create_product_listing(session, listing_data)
        await create_price_history(
            session,
            PriceHistCreate(
                listing_id=listing.id,
                price=price,
                currency=currency,
            ),
        )
        return listing

    price_changed = listing.current_price != price or listing.currency != currency
    listing.product_url = listing_data.product_url
    listing.current_price = price
    listing.currency = currency
    listing.last_checked_at = datetime.now(UTC)

    if price_changed or record_unchanged_price:
        await create_price_history(
            session,
            PriceHistCreate(
                listing_id=listing.id,
                price=price,
                currency=currency,
            ),
        )

    await session.flush()
    return listing


async def list_product_listings(
    session: AsyncSession,
    *,
    store_id: int | None = None,
    product_id: int | None = None,
) -> list[ProductListing]:
    statement = select(ProductListing).options(
        selectinload(ProductListing.store),
        selectinload(ProductListing.product),
    )

    if store_id is not None:
        statement = statement.where(ProductListing.store_id == store_id)

    if product_id is not None:
        statement = statement.where(ProductListing.product_id == product_id)

    return list(await session.scalars(statement))


async def list_price_history(
    session: AsyncSession,
    listing_id: int,
) -> list[PriceHist]:
    statement = (
        select(PriceHist)
        .where(PriceHist.listing_id == listing_id)
        .order_by(PriceHist.recorded_at.desc())
    )
    return list(await session.scalars(statement))
