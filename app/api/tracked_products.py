from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, Response, status

from app.db.db_schemas import (
    Page,
    TrackedProductCreate,
    TrackedProductCreated,
    TrackedProductResponse,
)
from app.dependencies import CurrentUser, SessionDep
from app.services.alert_service import (
    list_tracked_products,
    track_product,
    untrack_product,
)
from app.services.errors import ConflictError, NotFoundError

router = APIRouter(prefix="/tracked-products", tags=["tracked products"])
Limit = Annotated[int, Query(ge=1, le=100)]
Offset = Annotated[int, Query(ge=0)]


@router.post(
    "",
    response_model=TrackedProductCreated,
    status_code=status.HTTP_201_CREATED,
)
async def create_tracked_product(
    data: TrackedProductCreate,
    session: SessionDep,
    user: CurrentUser,
) -> TrackedProductCreated:
    try:
        tracked = await track_product(
            session,
            user_id=user.id,
            product_id=data.product_id,
        )
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return TrackedProductCreated(
        product_id=tracked.product_id,
        created_at=tracked.created_at,
    )


@router.get("", response_model=Page[TrackedProductResponse])
async def get_tracked_products(
    session: SessionDep,
    user: CurrentUser,
    limit: Limit = 50,
    offset: Offset = 0,
) -> Page[TrackedProductResponse]:
    return await list_tracked_products(
        session,
        user_id=user.id,
        limit=limit,
        offset=offset,
    )


@router.delete("/{product_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_tracked_product(
    product_id: int,
    session: SessionDep,
    user: CurrentUser,
) -> Response:
    try:
        await untrack_product(session, user_id=user.id, product_id=product_id)
    except NotFoundError as error:
        raise HTTPException(status_code=404, detail=str(error)) from error
    return Response(status_code=status.HTTP_204_NO_CONTENT)
