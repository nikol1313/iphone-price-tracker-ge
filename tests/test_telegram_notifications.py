import json
from decimal import Decimal

import httpx
import pytest
from pydantic import SecretStr
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from app.conf import settings
from app.db.models import PriceAlert, Product, ProductListing, Store, User
from app.services import alert_service
from app.services.alert_service import check_and_send_alert_notifications
from app.services.telegram_service import (
    TelegramNotificationError,
    send_price_alert_notification,
    send_telegram_message,
)
from tests.helpers import bearer, register_and_login


@pytest.mark.asyncio
async def test_price_alert_message_is_escaped_and_uses_decimal_amounts(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "TELEGRAM_BOT_TOKEN",
        SecretStr("test-bot-token"),
    )
    captured: dict = {}

    async def handler(request: httpx.Request) -> httpx.Response:
        captured.update(json.loads(request.content))
        return httpx.Response(200, json={"ok": True})

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        await send_price_alert_notification(
            chat_id="-123456",
            product_name="iPhone <Pro & Max>",
            product_variant="256GB & Blue",
            target_price=Decimal("2500.10"),
            current_price=Decimal("2399.99"),
            currency="gel",
            store_name='Shop "One"',
            product_url="https://shop.example/phone?a=1&b=2",
            client=client,
        )

    text = captured["text"]
    assert captured["chat_id"] == "-123456"
    assert captured["parse_mode"] == "HTML"
    assert "iPhone &lt;Pro &amp; Max&gt;" in text
    assert "256GB &amp; Blue" in text
    assert "GEL 2,500.10" in text
    assert "GEL 2,399.99" in text
    assert "Below target by:</b> GEL 100.11" in text
    assert "Shop &quot;One&quot;" in text
    assert 'href="https://shop.example/phone?a=1&amp;b=2"' in text


@pytest.mark.asyncio
async def test_telegram_errors_use_notification_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        settings,
        "TELEGRAM_BOT_TOKEN",
        SecretStr("test-bot-token"),
    )

    async def handler(_: httpx.Request) -> httpx.Response:
        return httpx.Response(
            400,
            json={"ok": False, "description": "chat not found"},
        )

    async with httpx.AsyncClient(
        transport=httpx.MockTransport(handler)
    ) as client:
        with pytest.raises(
            TelegramNotificationError,
            match="chat not found",
        ):
            await send_telegram_message(
                "hello",
                chat_id="123",
                client=client,
            )


@pytest.mark.asyncio
async def test_telegram_settings_are_authenticated_and_persisted(
    client: httpx.AsyncClient,
    session_factory: async_sessionmaker[AsyncSession],
) -> None:
    assert (
        await client.get("/notification-settings/telegram")
    ).status_code == 401

    token = await register_and_login(
        client,
        email="telegram@example.com",
        session_factory=session_factory,
    )
    headers = bearer(token)

    invalid = await client.put(
        "/notification-settings/telegram",
        headers=headers,
        json={"telegram_chat_id": "not-a-chat"},
    )
    assert invalid.status_code == 422

    saved = await client.put(
        "/notification-settings/telegram",
        headers=headers,
        json={"telegram_chat_id": " -100123456789 "},
    )
    assert saved.status_code == 200
    assert saved.json() == {"telegram_chat_id": "-100123456789"}
    assert (
        await client.get(
            "/notification-settings/telegram",
            headers=headers,
        )
    ).json() == {"telegram_chat_id": "-100123456789"}

    cleared = await client.put(
        "/notification-settings/telegram",
        headers=headers,
        json={"telegram_chat_id": None},
    )
    assert cleared.json() == {"telegram_chat_id": None}


@pytest.mark.asyncio
async def test_triggered_alert_routes_to_owner_once_with_correct_listing(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with session_factory() as session:
        gel_store = Store(title="GEL Store", web_url="https://gel.example")
        usd_store = Store(title="USD Store", web_url="https://usd.example")
        product = Product(
            brand="Apple",
            model="iPhone 17 Pro",
            storage="256GB",
            color="Blue",
            identity_key="iphone-17-pro-256-blue",
        )
        configured_user = User(
            email="configured@example.com",
            password_hash="unused",
            telegram_chat_id="111",
        )
        unconfigured_user = User(
            email="unconfigured@example.com",
            password_hash="unused",
        )
        session.add_all(
            [
                gel_store,
                usd_store,
                product,
                configured_user,
                unconfigured_user,
            ]
        )
        await session.flush()
        session.add_all(
            [
                ProductListing(
                    store_id=gel_store.id,
                    product_id=product.id,
                    product_url="https://gel.example/phone",
                    current_price=Decimal("2400.00"),
                    currency="GEL",
                ),
                ProductListing(
                    store_id=usd_store.id,
                    product_id=product.id,
                    product_url="https://usd.example/phone",
                    current_price=Decimal("10.00"),
                    currency="USD",
                ),
                PriceAlert(
                    user_id=configured_user.id,
                    product_id=product.id,
                    target_price=Decimal("2500.00"),
                    currency="GEL",
                ),
                PriceAlert(
                    user_id=unconfigured_user.id,
                    product_id=product.id,
                    target_price=Decimal("2500.00"),
                    currency="GEL",
                ),
            ]
        )
        await session.commit()

    deliveries: list[dict] = []

    async def capture_delivery(**message: object) -> None:
        deliveries.append(message)

    monkeypatch.setattr(
        alert_service,
        "send_price_alert_notification",
        capture_delivery,
    )

    async with session_factory() as session:
        async with session.begin():
            await check_and_send_alert_notifications(session)
        async with session.begin():
            await check_and_send_alert_notifications(session)

        alerts = (
            await session.scalars(
                select(PriceAlert).order_by(PriceAlert.user_id)
            )
        ).all()

    assert len(deliveries) == 1
    assert deliveries[0]["chat_id"] == "111"
    assert deliveries[0]["currency"] == "GEL"
    assert deliveries[0]["current_price"] == Decimal("2400.00")
    assert deliveries[0]["store_name"] == "GEL Store"
    assert alerts[0].notified_at is not None
    assert alerts[1].notified_at is None


@pytest.mark.asyncio
async def test_failed_delivery_is_left_pending_for_retry(
    session_factory: async_sessionmaker[AsyncSession],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async with session_factory() as session:
        store = Store(title="Store", web_url="https://store.example")
        product = Product(
            brand="Apple",
            model="iPhone 17",
            identity_key="iphone-17",
        )
        user = User(
            email="retry@example.com",
            password_hash="unused",
            telegram_chat_id="222",
        )
        session.add_all([store, product, user])
        await session.flush()
        session.add(
            ProductListing(
                store_id=store.id,
                product_id=product.id,
                product_url="https://store.example/phone",
                current_price=Decimal("900.00"),
                currency="GEL",
            )
        )
        session.add(
            PriceAlert(
                user_id=user.id,
                product_id=product.id,
                target_price=Decimal("1000.00"),
                currency="GEL",
            )
        )
        await session.commit()

    attempts = 0

    async def fail_delivery(**_: object) -> None:
        nonlocal attempts
        attempts += 1
        raise TelegramNotificationError("temporary failure")

    monkeypatch.setattr(
        alert_service,
        "send_price_alert_notification",
        fail_delivery,
    )

    async with session_factory() as session:
        async with session.begin():
            await check_and_send_alert_notifications(session)
        async with session.begin():
            await check_and_send_alert_notifications(session)
        alert = await session.scalar(select(PriceAlert))

    assert attempts == 2
    assert alert is not None
    assert alert.notified_at is None
