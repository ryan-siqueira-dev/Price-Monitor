from dataclasses import dataclass
from urllib.parse import urlparse


@dataclass(frozen=True, slots=True)
class StoreProfile:
    name: str
    domains: tuple[str, ...]
    price_selectors: tuple[str, ...] = ()


STORE_PROFILES = (
    StoreProfile(
        "Mercado Livre",
        ("mercadolivre.com.br",),
        (".ui-pdp-price__second-line .andes-money-amount__fraction",),
    ),
    StoreProfile(
        "Amazon Brasil",
        ("amazon.com.br",),
        ("#corePrice_feature_div .a-offscreen", ".priceToPay .a-offscreen"),
    ),
    StoreProfile(
        "KaBuM",
        ("kabum.com.br",),
        ('[data-testid="price-value"]', ".finalPrice"),
    ),
    StoreProfile(
        "Pichau",
        ("pichau.com.br",),
        ('[itemprop="price"]', '[data-cy="price-value"]'),
    ),
    StoreProfile(
        "TerabyteShop",
        ("terabyteshop.com.br",),
        (".valVista", ".prod-new-price"),
    ),
    StoreProfile(
        "Magazine Luiza",
        ("magazineluiza.com.br",),
        ('[data-testid="price-value"]', '[data-testid="price"]'),
    ),
    StoreProfile("Shopee", ("shopee.com.br",)),
    StoreProfile("AliExpress", ("aliexpress.com",)),
    StoreProfile(
        "OLX",
        ("olx.com.br",),
        ('[data-testid="ad-price"]', '[data-testid="price"]'),
    ),
    StoreProfile(
        "Trocafone",
        ("trocafone.com.br",),
        (".vtex-product-price-1-x-sellingPriceValue", '[data-testid="price"]'),
    ),
    StoreProfile(
        "Fast Shop",
        ("fastshop.com.br",),
        (".vtex-product-price-1-x-sellingPriceValue",),
    ),
)


def profile_for_url(url: str) -> StoreProfile | None:
    host = (urlparse(url).hostname or "").lower()
    if host.startswith("www."):
        host = host[4:]
    for profile in STORE_PROFILES:
        if any(host == domain or host.endswith(f".{domain}") for domain in profile.domains):
            return profile
    return None


def supported_stores() -> list[str]:
    return [profile.name for profile in STORE_PROFILES]
