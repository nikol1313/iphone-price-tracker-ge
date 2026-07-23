from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db.db_schemas import Page, ProductSummary
from app.dependencies import SessionDep
from app.services.product_service import search_products

router = APIRouter(tags=["search"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get("/search", response_model=Page[ProductSummary])
async def search(
    session: SessionDep,
    q: Annotated[str, Query(min_length=2, max_length=100)],
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[ProductSummary]:
    if not q.strip():
        raise HTTPException(status_code=422, detail="Search query cannot be blank")
    return await search_products(
        session,
        query=q,
        limit=limit,
        offset=offset,
    )
