from typing import Annotated

from fastapi import APIRouter, HTTPException, Query

from app.db.db_schemas import Page, ProductListingResponse
from app.dependencies import SessionDep
from app.services.errors import NotFoundError
from app.services.product_service import list_product_listings

router = APIRouter(tags=["listings"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.get(
    "/products/{product_id}/listings",
    response_model=Page[ProductListingResponse],
)
async def product_listings(
    product_id: int,
    session: SessionDep,
    include_inactive: bool = False,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[ProductListingResponse]:
    try:
        return await list_product_listings(
            session,
            product_id=product_id,
            include_inactive=include_inactive,
            limit=limit,
            offset=offset,
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
