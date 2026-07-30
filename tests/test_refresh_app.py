from unittest.mock import AsyncMock
from types import SimpleNamespace

import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conf import settings
from app.main import app
from app.scraper.scrape_zoommer import ZoommerCrawlError
from app.services.errors import RefreshInProgressError
from app.services.zmr_inges import IngestionSummary
from tests.helpers import bearer
from tests.test_products import create_admin_product


@pytest.mark.asyncio
async def test_refresh_success_and_scope(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    token, product = await create_admin_product(client, session_factory)
    mocked = AsyncMock(
        return_value=IngestionSummary(
            scraped=120,
            ingested=120,
            crawl_run_id=42,
            listings_created=8,
            listings_updated=112,
            prices_recorded=120,
        )
    )
    monkeypatch.setattr("app.api.refresh.refresh_full_catalog", mocked)
    response = await client.post(
        f"/products/{product['id']}/refresh",
        headers=bearer(token),
    )
    assert response.status_code == 200, response.text
    assert response.json() == {
        "crawl_run_id": 42,
        "requested_product_id": product["id"],
        "scope": "full_catalog",
        "products_found": 120,
        "listings_created": 8,
        "listings_updated": 112,
        "prices_recorded": 120,
        "listings": [],
    }
    mocked.assert_awaited_once()


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("error", "status_code"),
    [
        (ZoommerCrawlError("upstream failed"), 502),
        (RefreshInProgressError("already running"), 409),
    ],
)
async def test_refresh_failure_mapping(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
    error: Exception,
    status_code: int,
) -> None:
    token, product = await create_admin_product(client, session_factory)
    monkeypatch.setattr(
        "app.api.refresh.refresh_full_catalog",
        AsyncMock(side_effect=error),
    )
    response = await client.post(
        f"/products/{product['id']}/refresh",
        headers=bearer(token),
    )
    assert response.status_code == status_code


@pytest.mark.asyncio
async def test_lifespan_disposes_engine(monkeypatch: pytest.MonkeyPatch) -> None:
    dispose = AsyncMock()
    monkeypatch.setattr("app.main.engine", SimpleNamespace(dispose=dispose))
    settings.jwt_secret()
    async with app.router.lifespan_context(app):
        pass
    dispose.assert_awaited_once()


def test_openapi_contains_all_requested_routes() -> None:
    expected = {
        "/auth/register",
        "/auth/login",
        "/search",
        "/products",
        "/products/{product_id}",
        "/products/{product_id}/listings",
        "/products/{product_id}/prices",
        "/tracked-products",
        "/tracked-products/{product_id}",
        "/products/{product_id}/alerts",
        "/alerts",
        "/alerts/{alert_id}",
        "/notification-settings/telegram",
        "/products/{product_id}/refresh",
    }
    assert set(app.openapi()["paths"]) == expected
