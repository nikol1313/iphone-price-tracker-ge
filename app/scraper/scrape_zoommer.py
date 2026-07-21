import asyncio
import json
import re
from urllib.parse import urljoin

import httpx
from bs4 import BeautifulSoup

BASE_URL = "https://zoommer.ge"
ZOOMMER_APPLE_PHONES_URL = f"{BASE_URL}/mobiluri-telefonebi-apple-c724"


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


async def scrape_zoommer(url: str = ZOOMMER_APPLE_PHONES_URL) -> list[dict[str, object]]:
    headers = {
        "User-Agent": (
            "Mozilla/5.0 (X11; Linux x86_64) "
            "AppleWebKit/537.36 "
            "Chrome/149.0.0.0 Safari/537.36"
        ),
        "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "ka-GE,ka;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    try:
        async with httpx.AsyncClient(
            headers=headers,
            timeout=httpx.Timeout(20, connect=10),
            follow_redirects=True,
        ) as client:
            response = await client.get(url)
            response.raise_for_status()
    except httpx.HTTPError as error:
        print(f"Failed to fetch Zoommer: {error}")
        return []

    soup = BeautifulSoup(response.text, "html.parser")
    return products_from_json_ld(soup) or products_from_html_cards(soup)


async def main() -> None:
    products = await scrape_zoommer()
    print(json.dumps(products, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    asyncio.run(main())
