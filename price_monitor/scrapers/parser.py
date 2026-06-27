import json
import re
from decimal import Decimal, InvalidOperation
from typing import Any

from bs4 import BeautifulSoup

from price_monitor.scrapers.base import ScrapeResult
from price_monitor.scrapers.stores import StoreProfile

UNAVAILABLE_MARKERS = (
    "produto indisponível",
    "produto indisponivel",
    "anúncio finalizado",
    "anuncio finalizado",
    "este anúncio foi finalizado",
    "item indisponível",
    "item indisponivel",
    "produto esgotado",
    "fora de estoque",
    "out of stock",
)


def parse_price(value: str | int | float | Decimal | None) -> Decimal | None:
    if value is None:
        return None
    if isinstance(value, Decimal):
        return value.quantize(Decimal("0.01"))
    if isinstance(value, (int, float)):
        return Decimal(str(value)).quantize(Decimal("0.01"))

    text = str(value).replace("\xa0", " ").strip()
    match = re.search(r"\d[\d\s.,]*", text)
    if not match:
        return None
    number = re.sub(r"\s+", "", match.group(0)).rstrip(".,")

    if "," in number and "." in number:
        decimal_separator = "," if number.rfind(",") > number.rfind(".") else "."
        thousands_separator = "." if decimal_separator == "," else ","
        number = number.replace(thousands_separator, "").replace(decimal_separator, ".")
    elif "," in number:
        parts = number.split(",")
        number = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) == 2 else "".join(parts)
    elif "." in number:
        parts = number.split(".")
        number = "".join(parts[:-1]) + "." + parts[-1] if len(parts[-1]) == 2 else "".join(parts)

    try:
        parsed = Decimal(number).quantize(Decimal("0.01"))
    except InvalidOperation:
        return None
    return parsed if parsed > 0 else None


def _types(data: dict[str, Any]) -> set[str]:
    raw = data.get("@type", "")
    values = raw if isinstance(raw, list) else [raw]
    return {str(value).lower() for value in values}


def _walk_json(value: Any):
    if isinstance(value, dict):
        yield value
        for child in value.values():
            yield from _walk_json(child)
    elif isinstance(value, list):
        for child in value:
            yield from _walk_json(child)


def _offer_values(offer: dict[str, Any]) -> tuple[Decimal | None, str, bool]:
    raw_price = offer.get("price") or offer.get("lowPrice")
    if raw_price is None and isinstance(offer.get("priceSpecification"), dict):
        raw_price = offer["priceSpecification"].get("price")
    price = parse_price(raw_price)
    currency = str(offer.get("priceCurrency") or "BRL").upper()[:3]
    availability = str(offer.get("availability") or "").lower()
    unavailable_values = ("outofstock", "soldout", "discontinued")
    available = not any(marker in availability for marker in unavailable_values)
    return price, currency, available


def _from_json_ld(soup: BeautifulSoup, source: str) -> ScrapeResult | None:
    for script in soup.select('script[type="application/ld+json"]'):
        try:
            data = json.loads(script.string or script.get_text())
        except (json.JSONDecodeError, TypeError):
            continue
        for item in _walk_json(data):
            if "product" not in _types(item):
                continue
            offers = item.get("offers")
            offer_items = offers if isinstance(offers, list) else [offers]
            for offer in offer_items:
                if not isinstance(offer, dict):
                    continue
                price, currency, available = _offer_values(offer)
                if price is not None or not available:
                    return ScrapeResult(
                        price=price,
                        currency=currency,
                        title=str(item.get("name")) if item.get("name") else None,
                        available=available,
                        source=source,
                    )
    return None


def _title(soup: BeautifulSoup) -> str | None:
    meta = soup.select_one('meta[property="og:title"]')
    if meta and meta.get("content"):
        return str(meta["content"]).strip()[:500]
    heading = soup.select_one("h1")
    if heading:
        return heading.get_text(" ", strip=True)[:500]
    return soup.title.get_text(" ", strip=True)[:500] if soup.title else None


def _attribute_or_text(element) -> str:
    for attribute in ("content", "value", "data-price"):
        if element.get(attribute):
            return str(element[attribute])
    return element.get_text(" ", strip=True)


def parse_product_page(html: str, profile: StoreProfile | None = None) -> ScrapeResult | None:
    soup = BeautifulSoup(html, "html.parser")
    source = profile.name if profile else "Generic"

    structured = _from_json_ld(soup, source)
    if structured:
        return structured

    selectors = (
        'meta[property="product:price:amount"]',
        'meta[property="og:price:amount"]',
        'meta[itemprop="price"]',
        '[itemprop="price"][content]',
    )
    if profile:
        selectors += profile.price_selectors

    for selector in selectors:
        element = soup.select_one(selector)
        if not element:
            continue
        price = parse_price(_attribute_or_text(element))
        if price is not None:
            currency_element = soup.select_one(
                'meta[property="product:price:currency"], meta[itemprop="priceCurrency"]'
            )
            currency = (
                _attribute_or_text(currency_element).upper()[:3] if currency_element else "BRL"
            )
            return ScrapeResult(price, currency, _title(soup), True, source)

    page_text = soup.get_text(" ", strip=True).lower()
    if any(marker in page_text for marker in UNAVAILABLE_MARKERS):
        return ScrapeResult(None, "BRL", _title(soup), False, source)
    return None
