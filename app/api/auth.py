from fastapi import APIRouter, HTTPException, status

from app.db.db_schemas import TokenResponse, UserCredentials, UserResponse
from app.dependencies import SessionDep
from app.services.auth_service import (
    authenticate_user,
    create_access_token,
    register_user,
)
from app.services.errors import ConflictError

router = APIRouter(prefix="/auth", tags=["authentication"])


@router.post(
    "/register",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
)
async def register(
    credentials: UserCredentials,
    session: SessionDep,
) -> UserResponse:
    try:
        user = await register_user(session, credentials)
    except ConflictError as error:
        raise HTTPException(status_code=409, detail=str(error)) from error
    return UserResponse.model_validate(user)


@router.post("/login", response_model=TokenResponse)
async def login(
    credentials: UserCredentials,
    session: SessionDep,
) -> TokenResponse:
    user = await authenticate_user(session, credentials)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return create_access_token(user)
