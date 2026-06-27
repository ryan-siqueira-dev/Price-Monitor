from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, HttpUrl


class ProductCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    search_query: str | None = Field(default=None, min_length=1, max_length=300)
    url: HttpUrl | None = None
    target_price: Decimal = Field(gt=0, max_digits=12, decimal_places=2)
    currency: str = Field(default="BRL", min_length=3, max_length=3)
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)


class ProductUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=200)
    search_query: str | None = Field(default=None, min_length=1, max_length=300)
    url: HttpUrl | None = None
    target_price: Decimal | None = Field(default=None, gt=0, max_digits=12, decimal_places=2)
    active: bool | None = None
    city: str | None = Field(default=None, min_length=2, max_length=120)
    state: str | None = Field(default=None, min_length=2, max_length=2)


class ProductRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    name: str
    search_query: str | None
    url: str | None
    target_price: Decimal
    currency: str
    active: bool
    created_at: datetime
    updated_at: datetime
    last_checked_at: datetime | None
    last_price: Decimal | None
    last_status: str | None
    last_error: str | None
    last_offer_url: str | None
    last_store: str | None
    city: str | None
    state: str | None


class PriceCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    checked_at: datetime
    price: Decimal | None
    currency: str
    available: bool
    status: str
    scraper: str
    title: str | None
    error: str | None
    offer_url: str | None
    offers_found: int


class RunSummary(BaseModel):
    checked: int
    successful: int
    failed: int
    alerts_sent: int


class OfferRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    product_id: int
    store: str
    external_id: str
    title: str
    url: str
    condition: str
    city: str | None
    state: str | None
    currency: str
    current_price: Decimal
    active: bool
    first_seen_at: datetime
    last_seen_at: datetime
    last_alerted_price: Decimal | None
    last_alerted_at: datetime | None


class OfferCheckRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    offer_id: int
    checked_at: datetime
    price: Decimal
    available: bool


class LocationRead(BaseModel):
    city: str
    state: str


class LocationUpdate(BaseModel):
    city: str = Field(min_length=2, max_length=120)
    state: str = Field(min_length=2, max_length=2)


class ProviderStatusRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    provider: str
    last_success_at: datetime | None
    last_error_at: datetime | None
    last_error: str | None
