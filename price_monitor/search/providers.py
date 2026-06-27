import hashlib
import os
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Any
from urllib.parse import quote, quote_plus, urljoin

import httpx
from bs4 import BeautifulSoup, Tag

from price_monitor.config import Settings
from price_monitor.scrapers.parser import parse_price
from price_monitor.search.auth import MercadoLivreAuth
from price_monitor.search.base import SearchError, SearchLocation, SearchOffer

BLOCK_MARKERS = (
    "attention required",
    "acesso negado",
    "captcha",
    "desafio abaixo",
    "página indisponível",
    "pagina indisponivel",
    "tráfego incomum",
    "verificação de segurança",
    "verify/traffic",
    "you have been blocked",
)


def _positive_price(value: Any) -> Decimal | None:
    price = parse_price(value)
    return price if price is not None and price > 0 else None


def _external_id(url: str) -> str:
    return hashlib.sha256(url.encode()).hexdigest()[:32]


def infer_condition(title: str, raw: str | None = None) -> str:
    value = f"{title} {raw or ''}".lower()
    if any(term in value for term in ("recondicionado", "refurbished", "renewed")):
        return "recondicionado"
    if any(term in value for term in ("usado", "seminovo", "usada")):
        return "usado"
    if raw and raw.lower() in {"new", "novo"}:
        return "novo"
    return "desconhecido"


def parse_vtex_products(data: Any, store: str) -> list[SearchOffer]:
    if not isinstance(data, list):
        raise SearchError(f"{store} retornou um catálogo inválido")

    offers: list[SearchOffer] = []
    for product in data:
        if not isinstance(product, dict):
            continue
        title = str(product.get("productName") or product.get("productTitle") or "").strip()
        url = str(product.get("link") or "").strip()
        categories = tuple(str(value) for value in product.get("categories") or ())
        if not title or not url:
            continue

        best_price: Decimal | None = None
        for item in product.get("items") or ():
            if not isinstance(item, dict):
                continue
            for seller in item.get("sellers") or ():
                if not isinstance(seller, dict):
                    continue
                commercial = seller.get("commertialOffer") or {}
                if not isinstance(commercial, dict):
                    continue
                try:
                    quantity = int(commercial.get("AvailableQuantity") or 0)
                except (TypeError, ValueError):
                    quantity = 0
                if quantity <= 0:
                    continue
                price = _positive_price(commercial.get("spotPrice")) or _positive_price(
                    commercial.get("Price")
                )
                if price is not None and (best_price is None or price < best_price):
                    best_price = price

        if best_price is not None:
            offers.append(
                SearchOffer(
                    _external_id(url),
                    title,
                    best_price,
                    "BRL",
                    url,
                    store,
                    infer_condition(title),
                    categories=categories,
                )
            )
    return offers


class VtexSearchProvider:
    def __init__(
        self,
        name: str,
        base_url: str,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
    ):
        self.name = name
        self.base_url = base_url.rstrip("/")
        self.settings = settings
        self.transport = transport

    def search(self, query: str, location: SearchLocation | None = None) -> list[SearchOffer]:
        del location
        endpoint = (
            f"{self.base_url}/api/catalog_system/pub/products/search/"
            f"{quote(query.strip(), safe='')}"
        )
        headers = {"User-Agent": self.settings.user_agent, "Accept": "application/json"}
        try:
            with httpx.Client(
                headers=headers,
                timeout=self.settings.request_timeout_seconds,
                follow_redirects=True,
                transport=self.transport,
            ) as client:
                response = client.get(
                    endpoint,
                    params={"_from": 0, "_to": self.settings.search_max_results_per_store - 1},
                )
                response.raise_for_status()
                return parse_vtex_products(response.json(), self.name)
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"{self.name}: falha no catálogo ({exc})") from exc


class MercadoLivreSearchProvider:
    name = "Mercado Livre"
    endpoint = "https://api.mercadolibre.com/sites/MLB/search"

    def __init__(
        self,
        settings: Settings,
        transport: httpx.BaseTransport | None = None,
        auth: MercadoLivreAuth | None = None,
    ):
        self.settings = settings
        self.transport = transport
        self.auth = auth or MercadoLivreAuth(settings, transport)

    def search(self, query: str, location: SearchLocation | None = None) -> list[SearchOffer]:
        token = self.auth.access_token()
        try:
            with httpx.Client(
                timeout=self.settings.request_timeout_seconds, transport=self.transport
            ) as client:
                response = client.get(
                    self.endpoint,
                    headers={"Authorization": f"Bearer {token}"},
                    params={"q": query, "limit": self.settings.search_max_results_per_store},
                )
                response.raise_for_status()
                payload = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"Mercado Livre: falha na API ({exc})") from exc

        offers: list[SearchOffer] = []
        for item in payload.get("results") or ():
            if not isinstance(item, dict):
                continue
            title = str(item.get("title") or "").strip()
            url = str(item.get("permalink") or "").strip()
            price = _positive_price(item.get("price"))
            item_id = str(item.get("id") or _external_id(url))
            address = item.get("address") or {}
            city = str(address.get("city_name") or "").strip() or None
            state = str(address.get("state_id") or "").removeprefix("BR-") or None
            if not title or not url or price is None:
                continue
            offers.append(
                SearchOffer(
                    item_id,
                    title,
                    price,
                    str(item.get("currency_id") or "BRL")[:3],
                    url,
                    self.name,
                    infer_condition(title, str(item.get("condition") or "")),
                    city,
                    state,
                )
            )
        return offers


@dataclass(frozen=True, slots=True)
class BrowserSearchProfile:
    name: str
    home_url: str
    search_url: str
    card_selector: str
    title_selector: str
    price_selector: str | None
    link_selector: str | None = None
    location_selector: str | None = None


class BrowserSearchProvider:
    def __init__(self, profile: BrowserSearchProfile, settings: Settings):
        self.profile = profile
        self.settings = settings
        self.name = profile.name

    @property
    def profile_dir(self) -> Path:
        slug = re.sub(r"[^a-z0-9]+", "-", self.name.lower()).strip("-")
        return Path(self.settings.auth_dir) / "browser" / slug

    def _fetch(self, url: str) -> str:
        try:
            from playwright.sync_api import Error, sync_playwright

            self.profile_dir.mkdir(parents=True, exist_ok=True)
            os.chmod(self.profile_dir, 0o700)
            with sync_playwright() as playwright:
                context = playwright.chromium.launch_persistent_context(
                    str(self.profile_dir),
                    headless=self.settings.browser_headless,
                    locale="pt-BR",
                    user_agent=self.settings.user_agent,
                )
                page = context.pages[0] if context.pages else context.new_page()
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.browser_timeout_ms,
                )
                page.wait_for_timeout(5_000)
                html = page.content()
                context.close()
        except (Error, OSError) as exc:
            raise SearchError(f"{self.name}: falha no navegador ({exc})") from exc
        lowered = BeautifulSoup(html, "html.parser").get_text(" ", strip=True).lower()
        if any(marker in lowered for marker in BLOCK_MARKERS):
            raise SearchError(f"{self.name}: sessão bloqueada; execute auth setup")
        return html

    @staticmethod
    def _element_text(element: Tag | None) -> str:
        if element is None:
            return ""
        return str(element.get("alt") or element.get_text(" ", strip=True)).strip()

    def search(self, query: str, location: SearchLocation | None = None) -> list[SearchOffer]:
        location_query = (
            f" {location.city} {location.state}" if location and self.name == "OLX" else ""
        )
        encoded_query = quote_plus(query + location_query)
        if self.name in {"Magalu", "KaBuM"}:
            encoded_query = quote("-".join(query.split()), safe="-")
        url = self.profile.search_url.format(query=encoded_query)
        soup = BeautifulSoup(self._fetch(url), "html.parser")
        offers: list[SearchOffer] = []
        seen: set[str] = set()
        for card in soup.select(self.profile.card_selector):
            title = self._element_text(card.select_one(self.profile.title_selector))
            if self.profile.price_selector:
                price_text = self._element_text(card.select_one(self.profile.price_selector))
            else:
                card_text = self._element_text(card)
                marker = card_text.find("R$")
                price_text = card_text[marker:] if marker >= 0 else card_text
            price = parse_price(price_text)
            link = card if card.name == "a" and card.get("href") else None
            if link is None and self.profile.link_selector:
                link = card.select_one(self.profile.link_selector)
            href = str(link.get("href") or "").strip() if link else ""
            offer_url = urljoin(self.profile.home_url, href)
            location_text = self._element_text(
                card.select_one(self.profile.location_selector)
                if self.profile.location_selector
                else None
            )
            if not title or price is None or not href or offer_url in seen:
                continue
            if (
                location
                and location_text
                and location.city.casefold() not in location_text.casefold()
            ):
                continue
            seen.add(offer_url)
            offers.append(
                SearchOffer(
                    _external_id(offer_url),
                    title,
                    price,
                    "BRL",
                    offer_url,
                    self.name,
                    infer_condition(title),
                    location.city if location and self.name == "OLX" else None,
                    location.state if location and self.name == "OLX" else None,
                )
            )
            if len(offers) >= self.settings.search_max_results_per_store:
                break
        return offers


def browser_profiles() -> list[BrowserSearchProfile]:
    return [
        BrowserSearchProfile(
            "OLX",
            "https://www.olx.com.br",
            "https://www.olx.com.br/brasil?q={query}",
            '[data-testid="adcard-main-content"], li a[href*="/item/"]',
            '[data-testid="adcard-title"], h2',
            '[data-testid="ad-price"], h3',
            'a[href], [data-testid="adcard-link"]',
            '[data-testid="location-date"]',
        ),
        BrowserSearchProfile(
            "Amazon",
            "https://www.amazon.com.br",
            "https://www.amazon.com.br/s?k={query}",
            '[data-component-type="s-search-result"]',
            "h2 span",
            ".a-price .a-offscreen",
            "h2 a",
        ),
        BrowserSearchProfile(
            "Magalu",
            "https://www.magazineluiza.com.br",
            "https://www.magazineluiza.com.br/busca/{query}/",
            '[data-testid="product-card-content"], a[data-testid="product-card-container"]',
            '[data-testid="product-title"], h2',
            '[data-testid="price-value"]',
            "a[href]",
        ),
        BrowserSearchProfile(
            "KaBuM",
            "https://www.kabum.com.br",
            "https://www.kabum.com.br/busca/{query}",
            'a[href*="/produto/"]',
            "h2, h3, img[alt]",
            None,
        ),
    ]
