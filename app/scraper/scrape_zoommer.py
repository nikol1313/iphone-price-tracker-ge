import asyncio
import json
import logging
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://zoommer.ge"
ZOOMMER_APPLE_PHONES_URL = f"{BASE_URL}/mobiluri-telefonebi-apple-c724"
LOGGER = logging.getLogger(__name__)


class ZoommerCrawlError(RuntimeError):
    """Raised when Zoommer cannot be fetched after the retry policy."""


def _is_retryable(error: httpx.HTTPError) -> bool:
    if isinstance(error, httpx.RequestError):
        return True
    if isinstance(error, httpx.HTTPStatusError):
        return error.response.status_code in {408, 429} or (
            error.response.status_code >= 500
        )
    return False


def parse_price(price_text: str) -> float | None:
    cleaned_price = re.sub(r"[^\d.]", "", str(price_text))

    if not cleaned_price:
        return None

    try:
        return float(cleaned_price)
    except ValueError:
        return None


def product_from_json_ld_item(item: dict) -> dict[str, object] | None:
    product = item.get("item", item)

    if not isinstance(product, dict) or product.get("@type") != "Product":
        return None

    name = product.get("name")
    offers = product.get("offers")

    if not isinstance(name, str) or not isinstance(offers, dict):
        return None

    price = parse_price(str(offers.get("price", "")))

    if price is None:
        return None

    product_url = urljoin(f"{BASE_URL}/", str(product.get("url", "")))
    image_url = product.get("image")

    return {
        "name": name.strip(),
        "price": price,
        "currency": offers.get("priceCurrency") or "GEL",
        "url": product_url,
        "image_url": image_url if isinstance(image_url, str) else None,
        "store": "Zoommer",
    }


def products_from_json_ld(soup: BeautifulSoup) -> list[dict[str, object]]:
    products: list[dict[str, object]] = []

    for script in soup.select("script[type='application/ld+json']"):
        script_text = script.string or script.get_text(strip=True)

        if not script_text:
            continue

        try:
            data = json.loads(script_text)
        except json.JSONDecodeError:
            continue

        item_lists = data if isinstance(data, list) else [data]

        for item_list in item_lists:
            if not isinstance(item_list, dict):
                continue

            if item_list.get("@type") == "ItemList":
                elements = item_list.get("itemListElement", [])
            else:
                elements = [item_list]

            if not isinstance(elements, list):
                continue

            for element in elements:
                if not isinstance(element, dict):
                    continue

                product = product_from_json_ld_item(element)

                if product:
                    products.append(product)

    return products


def products_from_html_cards(soup: BeautifulSoup) -> list[dict[str, object]]:
    products: list[dict[str, object]] = []

    product_cards = soup.select(
        ".product-card, "
        ".product-item, "
        ".products-list-item, "
        "[class*='product-card'], "
        "[class*='product-item']"
    )

    for card in product_cards:
        name_element = card.select_one(
            ".product-name, "
            ".product-title, "
            "[class*='product-name'], "
            "[class*='product-title'], "
            "h2, h3, h4"
        )
        price_element = card.select_one(
            ".product-price, "
            ".price, "
            "[class*='price']"
        )
        link_element = card.select_one("a[href]")
        image_element = card.select_one("img")

        if not name_element or not price_element or not link_element:
            continue

        name = name_element.get_text(" ", strip=True)
        price = parse_price(price_element.get_text(" ", strip=True))

        if price is None:
            continue

        product_url = urljoin(BASE_URL, link_element.get("href", ""))
        image_url = None

        if image_element:
            image_path = (
                image_element.get("src")
                or image_element.get("data-src")
                or image_element.get("data-lazy-src")
            )

            if image_path:
                image_url = urljoin(BASE_URL, image_path)

        products.append(
            {
                "name": name,
                "price": price,
                "currency": "GEL",
                "url": product_url,
                "image_url": image_url,
                "store": "Zoommer",
            }
        )

    return products


async def _fetch_with_retries(
    client: httpx.AsyncClient,
    url: str,
    *,
    max_attempts: int,
    backoff_seconds: float,
    request_delay_seconds: float,
) -> httpx.Response:
    last_error: httpx.HTTPError | None = None
    attempts_made = 0

    for attempt in range(1, max_attempts + 1):
        attempts_made = attempt
        if request_delay_seconds:
            await asyncio.sleep(request_delay_seconds)

        try:
            response = await client.get(url)
            response.raise_for_status()
            return response
        except httpx.HTTPError as error:
            last_error = error

            if attempt == max_attempts or not _is_retryable(error):
                break

            retry_delay = backoff_seconds * (2 ** (attempt - 1))
            LOGGER.warning(
                "Zoommer request failed; retrying in %.1f seconds "
                "(attempt %d/%d): %s",
                retry_delay,
                attempt,
                max_attempts,
                error,
            )
            if retry_delay:
                await asyncio.sleep(retry_delay)

    raise ZoommerCrawlError(
        f"Failed to fetch {url} after {attempts_made} attempt(s): {last_error}"
    ) from last_error


async def scrape_zoommer(
    url: str = ZOOMMER_APPLE_PHONES_URL,
    *,
    max_attempts: int = 3,
    backoff_seconds: float = 1.0,
    request_delay_seconds: float = 0.5,
    client: httpx.AsyncClient | None = None,
) -> list[dict[str, object]]:
    if max_attempts < 1:
        raise ValueError("max_attempts must be at least 1")
    if backoff_seconds < 0 or request_delay_seconds < 0:
        raise ValueError("retry and request delays cannot be negative")

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ka-GE,ka;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    if client is None:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(20, connect=10),
            follow_redirects=True,
        ) as owned_client:
            response = await _fetch_with_retries(
                owned_client,
                url,
                max_attempts=max_attempts,
                backoff_seconds=backoff_seconds,
                request_delay_seconds=request_delay_seconds,
            )
    else:
        response = await _fetch_with_retries(
            client,
            url,
            max_attempts=max_attempts,
            backoff_seconds=backoff_seconds,
            request_delay_seconds=request_delay_seconds,
        )

    soup = BeautifulSoup(response.text, "html.parser")
    return products_from_json_ld(soup) or products_from_html_cards(soup)


async def main() -> None:
    products = await scrape_zoommer()
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
