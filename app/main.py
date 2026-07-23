from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI


from app.api import (
    alerts,
    auth,
    listings,
    prices,
    products,
    refresh,
    search,
    tracked_products,
)
from app.conf import settings
from app.db.sess import engine


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    settings.jwt_secret()
    try:
        yield
    finally:
        await engine.dispose()


app = FastAPI(
    title="iPhone Price Monitor API",
    version="0.1.0",
    docs_url="/docs",
    redoc_url="/redoc",
    openapi_url="/openapi.json",
    lifespan=lifespan,
)

app.include_router(auth.router)
app.include_router(search.router)
app.include_router(products.router)
app.include_router(listings.router)
app.include_router(prices.router)
app.include_router(tracked_products.router)
app.include_router(alerts.router)
app.include_router(refresh.router)


