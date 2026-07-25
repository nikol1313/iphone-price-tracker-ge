import httpx
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.db.models import User


async def register_and_login(
    client: httpx.AsyncClient,
    *,
    email: str,
    admin: bool = False,
    session_factory: async_sessionmaker[AsyncSession] | None = None,
) -> str:
    password = "strong-password"
    response = await client.post(
        "/auth/register",
        json={"email": email, "password": password},
    )
    assert response.status_code == 201, response.text

    if admin:
        assert session_factory is not None
        async with session_factory() as session:
            user = await session.scalar(select(User).where(User.email == email.lower()))
            assert user is not None
            user.is_admin = True
            await session.commit()

    response = await client.post(
        "/auth/login",
        json={"email": email, "password": password},
    )
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


def bearer(token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {token}"}
