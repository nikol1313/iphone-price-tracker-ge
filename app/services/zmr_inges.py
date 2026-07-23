import asyncio
from collections.abc import Iterable, Mapping
from dataclasses import asdict, dataclass
from decimal import Decimal, InvalidOperation

from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.exc import IntegrityError

from app.db.crud import (
    complete_crawl_run,
    create_crawl_run,
    fail_crawl_run,
    get_or_create_product,
    get_or_create_store,
    upsert_product_listing,
)
from app.db.db_schemas import ProductCreate, ProductListingCreate, StoreCreate
from app.db.sess import SESSION
from app.scraper.scrape_zoommer import BASE_URL, scrape_zoommer
from app.services.errors import RefreshInProgressError


@dataclass(frozen=True, slots=True)
class IngestionSummary:
    scraped: int
    ingested: int
    crawl_run_id: int | None = None
    listings_created: int = 0
    listings_updated: int = 0
    prices_recorded: int = 0


def _required_text(item: Mapping[str, object], key: str) -> str:
    value = item.get(key)

    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"Scraped product has no valid {key!r}: {item!r}")

    return value.strip()


def _optional_text(item: Mapping[str, object], key: str) -> str | None:
    value = item.get(key)

    if value is None:
        return None
    if not isinstance(value, str):
        raise ValueError(f"Scraped product has an invalid {key!r}: {item!r}")

    return value.strip() or None


def _price(item: Mapping[str, object]) -> Decimal:
    value = item.get("price")

    try:
        price = Decimal(str(value))
    except (InvalidOperation, ValueError):
        raise ValueError(f"Scraped product has an invalid price: {item!r}") from None

    if not price.is_finite() or price <= 0:
        raise ValueError(f"Scraped product has an invalid price: {item!r}")

    return price


def _product_create(item: Mapping[str, object]) -> ProductCreate:
    brand = _optional_text(item, "brand") or "Apple"
    model = _optional_text(item, "model") or _required_text(item, "name")

    return ProductCreate(
        brand=brand,
        model=model,
        storage=_optional_text(item, "storage"),
        color=_optional_text(item, "color"),
    )


async def ingest_zoommer(
    session: AsyncSession,
    scraped_products: Iterable[Mapping[str, object]] | None = None,
) -> IngestionSummary:
    products = (
        list(scraped_products)
        if scraped_products is not None
        else await scrape_zoommer()
    )

    if not products:
        return IngestionSummary(scraped=0, ingested=0)

    store = await get_or_create_store(
        session,
        StoreCreate(title="Zoommer", web_url=BASE_URL),
    )

    listings_created = 0
    listings_updated = 0
    prices_recorded = 0

    for item in products:
        product = await get_or_create_product(session, _product_create(item))
        result = await upsert_product_listing(
            session,
            ProductListingCreate(
                store_id=store.id,
                product_id=product.id,
                product_url=_required_text(item, "url"),
                current_price=_price(item),
                currency=_optional_text(item, "currency") or "GEL",
            ),
        )
        listings_created += int(result.created)
        listings_updated += int(not result.created)
        prices_recorded += int(result.price_recorded)

    return IngestionSummary(
        scraped=len(products),
        ingested=len(products),
        listings_created=listings_created,
        listings_updated=listings_updated,
        prices_recorded=prices_recorded,
    )


async def run_zoommer_ingestion() -> IngestionSummary:
    async with SESSION() as session:
        try:
            async with session.begin():
                store = await get_or_create_store(
                    session,
                    StoreCreate(title="Zoommer", web_url=BASE_URL),
                )
                crawl_run = await create_crawl_run(session, store.id)
                crawl_run_id = crawl_run.id
        except IntegrityError as error:
            raise RefreshInProgressError(
                "A Zoommer refresh is already running"
            ) from error

        products_found = 0

        try:
            scraped_products = await scrape_zoommer()
            products_found = len(scraped_products)

            async with session.begin():
                summary = await ingest_zoommer(session, scraped_products)
                await complete_crawl_run(
                    session,
                    crawl_run_id,
                    products_found=summary.scraped,
                    products_ingested=summary.ingested,
                )

            return IngestionSummary(
                scraped=summary.scraped,
                ingested=summary.ingested,
                crawl_run_id=crawl_run_id,
                listings_created=summary.listings_created,
                listings_updated=summary.listings_updated,
                prices_recorded=summary.prices_recorded,
            )
        except Exception as error:
            if session.in_transaction():
                await session.rollback()

            async with session.begin():
                await fail_crawl_run(
                    session,
                    crawl_run_id,
                    error,
                    products_found=products_found,
                )

            raise


async def main() -> None:
    summary = await run_zoommer_ingestion()
    print(asdict(summary))


if __name__ == "__main__":
    asyncio.run(main())
