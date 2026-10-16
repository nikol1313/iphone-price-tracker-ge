import json

from bs4 import BeautifulSoup

from app.scraper.scrape_zoommer import products_from_next_data


def test_products_from_zoommer_next_data() -> None:
    payload = {
        "props": {
            "pageProps": {
                "initialFilteredProducts": {
                    "products": [
                        {
                            "id": 54834,
                            "name": "Apple iPhone 18 Pro | 256GB Burgundy",
                            "price": 4299,
                            "route": "mobiluri-telefonebi/apple-iphone-18-pro",
                            "imageUrl": "https://images.example/iphone.jpg",
                            "isInStock": True,
                        },
                        {
                            "id": 9,
                            "name": "Apple Watch",
                            "price": 999,
                            "route": "apple-watch",
                        },
                        {
                            "id": 10,
                            "name": "Apple iPhone without a price",
                            "price": None,
                            "route": "iphone-no-price",
                        },
                    ]
                }
            }
        }
    }
    soup = BeautifulSoup(
        f'<script id="__NEXT_DATA__">{json.dumps(payload)}</script>',
        "html.parser",
    )

    products = products_from_next_data(soup)

    assert products == [
        {
            "name": "Apple iPhone 18 Pro | 256GB Burgundy",
            "price": 4299.0,
            "currency": "GEL",
            "url": "https://zoommer.ge/mobiluri-telefonebi/apple-iphone-18-pro",
            "image_url": "https://images.example/iphone.jpg",
            "store": "Zoommer",
            "is_available": True,
            "external_product_id": "54834",
        }
    ]


def test_products_from_zoommer_next_data_handles_missing_payload() -> None:
    soup = BeautifulSoup("<html><body>No product data</body></html>", "html.parser")

    assert products_from_next_data(soup) == []
