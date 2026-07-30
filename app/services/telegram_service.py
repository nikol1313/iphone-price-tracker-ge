from decimal import Decimal
from html import escape
from urllib.parse import urlsplit

import httpx

from app.conf import settings

TELEGRAM_API_BASE_URL = "https://api.telegram.org"
TELEGRAM_REQUEST_TIMEOUT_SECONDS = 10.0


class TelegramNotificationError(Exception):
    """Raised when Telegram rejects a notification or cannot be reached."""


def _price(value: Decimal) -> str:
    return f"{value:,.2f}"


def _safe_link(url: str | None) -> str | None:
    if not url:
        return None
    parsed = urlsplit(url)
    if parsed.scheme not in {"http", "https"} or not parsed.netloc:
        return None
    return escape(url, quote=True)


def _price_alert_message(
    *,
    product_name: str,
    product_variant: str,
    target_price: Decimal,
    current_price: Decimal,
    currency: str,
    store_name: str | None,
    product_url: str | None,
) -> str:
    safe_currency = escape(currency.upper())
    difference = target_price - current_price
    difference_label = "Below target by" if difference >= 0 else "Above target by"
    safe_url = _safe_link(product_url)

    lines = [
        "🎉 <b>Price Alert Triggered!</b>",
        "",
        f"📱 <b>Product:</b> {escape(product_name)}",
        f"🔧 <b>Variant:</b> {escape(product_variant)}",
        f"💰 <b>Target Price:</b> {safe_currency} {_price(target_price)}",
        f"📉 <b>Current Price:</b> {safe_currency} {_price(current_price)}",
        f"✅ <b>{difference_label}:</b> {safe_currency} {_price(abs(difference))}",
    ]
    if store_name:
        lines.append(f"🏪 <b>Store:</b> {escape(store_name)}")
    if safe_url:
        lines.append(f'🔗 <a href="{safe_url}">View Product</a>')
    return "\n".join(lines)


async def send_telegram_message(
    message: str,
    *,
    chat_id: str,
    parse_mode: str = "HTML",
    client: httpx.AsyncClient | None = None,
) -> None:
    """Send one message through the application Telegram bot."""
    if settings.TELEGRAM_BOT_TOKEN is None:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")

    bot_token = settings.TELEGRAM_BOT_TOKEN.get_secret_value().strip()
    if not bot_token:
        raise RuntimeError("TELEGRAM_BOT_TOKEN is not configured")
    if not chat_id.strip():
        raise ValueError("chat_id cannot be empty")

    url = f"{TELEGRAM_API_BASE_URL}/bot{bot_token}/sendMessage"
    payload = {
        "chat_id": chat_id,
        "text": message,
        "parse_mode": parse_mode,
    }

    owns_client = client is None
    http_client = client or httpx.AsyncClient(
        timeout=TELEGRAM_REQUEST_TIMEOUT_SECONDS,
    )
    try:
        try:
            response = await http_client.post(url, json=payload)
        except httpx.HTTPError:
            raise TelegramNotificationError(
                "Telegram could not be reached"
            ) from None

        try:
            result = response.json()
        except ValueError:
            raise TelegramNotificationError(
                f"Telegram returned an invalid response (HTTP {response.status_code})"
            ) from None

        if not isinstance(result, dict) or response.is_error or not result.get("ok"):
            description = (
                result.get("description", "Unknown error")
                if isinstance(result, dict)
                else "Unknown error"
            )
            raise TelegramNotificationError(
                f"Telegram rejected the message: {description}"
            )
    finally:
        if owns_client:
            await http_client.aclose()


async def send_price_alert_notification(
    *,
    chat_id: str,
    product_name: str,
    product_variant: str,
    target_price: Decimal,
    current_price: Decimal,
    currency: str,
    store_name: str | None = None,
    product_url: str | None = None,
    client: httpx.AsyncClient | None = None,
) -> None:
    """Format and send a price alert to one configured Telegram chat."""
    message = _price_alert_message(
        product_name=product_name,
        product_variant=product_variant,
        target_price=target_price,
        current_price=current_price,
        currency=currency,
        store_name=store_name,
        product_url=product_url,
    )
    await send_telegram_message(
        message,
        chat_id=chat_id,
        client=client,
    )
