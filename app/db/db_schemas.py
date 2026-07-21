from datetime import datetime
from decimal import Decimal
from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict, field_validator

#stores
class StoreBase(BaseModel):
    title: str
    web_url: str


class StoreCreate(StoreBase):
    @field_validator("title")
    @classmethod
    def title_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("title cannot be empty")
        return v.strip()

    @field_validator("web_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("url cannot be empty")
        return v.strip()


class StoreResponse(StoreBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


class CrawlRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    status: Literal["running", "succeeded", "failed"]
    started_at: datetime
    finished_at: datetime | None
    products_found: int
    products_ingested: int
    error_message: str | None


#products
class ProductBase(BaseModel):
    brand: str
    model: str
    storage: Optional[str] = None
    color: Optional[str] = None


class ProductCreate(ProductBase):
    @field_validator("brand", "model")
    @classmethod
    def field_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("This field cannot be empty")
        return v.strip()


class ProductResponse(ProductBase):
    model_config = ConfigDict(from_attributes=True)

    id: int


#productlisting
class ProductListingBase(BaseModel):
    product_url: str
    current_price: Decimal
    currency: str = "GEL"


class ProductListingCreate(ProductListingBase):
    store_id: int
    product_id: int

    @field_validator("current_price")
    @classmethod
    def price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()

    @field_validator("product_url")
    @classmethod
    def url_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("url cannot be empty")
        return v.strip()


class ProductListingResponse(ProductListingBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    store_id: int
    product_id: int
    last_checked_at: datetime


class ProductListingWithRelations(ProductListingResponse):
    model_config = ConfigDict(from_attributes=True)

    store: StoreResponse
    product: ProductResponse


#pricehist
class PriceHistBase(BaseModel):
    price: Decimal
    currency: str = "GEL"


class PriceHistCreate(PriceHistBase):
    listing_id: int

    @field_validator("price")
    @classmethod
    def price_positive(cls, v: Decimal) -> Decimal:
        if v <= 0:
            raise ValueError("Price must be positive")
        return v

    @field_validator("currency")
    @classmethod
    def currency_uppercase(cls, v: str) -> str:
        return v.upper()


class PriceHistResponse(PriceHistBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    listing_id: int
    recorded_at: datetime
