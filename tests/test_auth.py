from datetime import UTC, datetime, timedelta

import httpx
import jwt
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conf import settings
from app.db.models import User
from tests.helpers import bearer, register_and_login


@pytest.mark.asyncio
async def test_registration_normalizes_email_and_hashes_password(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    response = await client.post(
        "/auth/register",
        json={"email": "  USER@Example.COM ", "password": "strong-password"},
    )
    assert response.status_code == 201
    assert response.json()["email"] == "user@example.com"
    assert "password_hash" not in response.json()

    async with session_factory() as session:
        user = await session.scalar(select(User))
        assert user is not None
        assert user.password_hash.startswith("$argon2id$")
        assert user.password_hash != "strong-password"


@pytest.mark.asyncio
async def test_registration_validation_and_duplicate_email(
    client: httpx.AsyncClient,
) -> None:
    assert (
        await client.post(
            "/auth/register",
            json={"email": "invalid", "password": "strong-password"},
        )
    ).status_code == 422
    assert (
        await client.post(
            "/auth/register",
            json={"email": "user@example.com", "password": "short"},
        )
    ).status_code == 422
    await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    duplicate = await client.post(
        "/auth/register",
        json={"email": "USER@example.com", "password": "strong-password"},
    )
    assert duplicate.status_code == 409


@pytest.mark.asyncio
async def test_login_uses_generic_failure_and_rejects_inactive_user(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    await client.post(
        "/auth/register",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    unknown = await client.post(
        "/auth/login",
        json={"email": "none@example.com", "password": "strong-password"},
    )
    wrong = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "wrong-password"},
    )
    assert unknown.status_code == wrong.status_code == 401
    assert unknown.json() == wrong.json()

    async with session_factory() as session:
        user = await session.scalar(select(User))
        assert user is not None
        user.is_active = False
        await session.commit()
    inactive = await client.post(
        "/auth/login",
        json={"email": "user@example.com", "password": "strong-password"},
    )
    assert inactive.status_code == 401


@pytest.mark.asyncio
async def test_protected_routes_reject_missing_malformed_and_expired_tokens(
    client: httpx.AsyncClient,
) -> None:
    assert (await client.get("/tracked-products")).status_code == 401
    assert (
        await client.get("/tracked-products", headers=bearer("not-a-jwt"))
    ).status_code == 401

    now = datetime.now(UTC)
    expired = jwt.encode(
        {
            "sub": "1",
            "iat": now - timedelta(hours=2),
            "exp": now - timedelta(hours=1),
            "type": "access",
        },
        settings.jwt_secret(),
        algorithm="HS256",
    )
    wrong_type = jwt.encode(
        {
            "sub": "1",
            "iat": now,
            "exp": now + timedelta(hours=1),
            "type": "refresh",
        },
        settings.jwt_secret(),
        algorithm="HS256",
    )
    assert (
        await client.get("/tracked-products", headers=bearer(expired))
    ).status_code == 401
    assert (
        await client.get("/tracked-products", headers=bearer(wrong_type))
    ).status_code == 401


@pytest.mark.asyncio
async def test_regular_user_cannot_mutate_catalog(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    token = await register_and_login(
        client,
        email="user@example.com",
        session_factory=session_factory,
    )
    response = await client.post(
        "/products",
        headers=bearer(token),
        json={"brand": "Apple", "model": "iPhone 17"},
    )
    assert response.status_code == 403
