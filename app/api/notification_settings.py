from fastapi import APIRouter

from app.db.db_schemas import TelegramSettingsResponse, TelegramSettingsUpdate
from app.dependencies import CurrentUser, SessionDep

router = APIRouter(
    prefix="/notification-settings",
    tags=["notification settings"],
)


@router.get("/telegram", response_model=TelegramSettingsResponse)
async def get_telegram_settings(user: CurrentUser) -> TelegramSettingsResponse:
    return TelegramSettingsResponse.model_validate(user)


@router.put("/telegram", response_model=TelegramSettingsResponse)
async def update_telegram_settings(
    data: TelegramSettingsUpdate,
    session: SessionDep,
    user: CurrentUser,
) -> TelegramSettingsResponse:
    user.telegram_chat_id = data.telegram_chat_id
    await session.flush()
    return TelegramSettingsResponse.model_validate(user)
