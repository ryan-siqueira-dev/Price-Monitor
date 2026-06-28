import logging

from price_monitor.config import Settings
from price_monitor.search.base import (
    ProviderFailure,
    SearchLocation,
    SearchOffer,
    SearchProvider,
    SearchSummary,
)
from price_monitor.search.matching import is_relevant_offer
from price_monitor.search.providers import (
    BrowserSearchProvider,
    VtexSearchProvider,
    browser_profiles,
)

logger = logging.getLogger(__name__)


def default_search_providers(settings: Settings) -> list[SearchProvider]:
    providers: list[SearchProvider] = [
        VtexSearchProvider("Carrefour", "https://www.carrefour.com.br", settings),
    ]
    if settings.use_browser:
        providers.extend(BrowserSearchProvider(profile, settings) for profile in browser_profiles())
    return providers


def search_provider_names() -> list[str]:
    return ["OLX", "Amazon", "KaBuM", "Carrefour"]


class ProductSearch:
    def __init__(self, settings: Settings, providers: list[SearchProvider] | None = None):
        self.providers = providers if providers is not None else default_search_providers(settings)

    def search(self, query: str, location: SearchLocation | None = None) -> SearchSummary:
        offers: list[SearchOffer] = []
        failures: list[ProviderFailure] = []
        successful: list[str] = []
        for provider in self.providers:
            try:
                provider_offers = provider.search(query, location)
            except Exception as exc:
                message = str(exc)
                failures.append(ProviderFailure(provider.name, message))
                logger.warning("falha na busca %s: %s", provider.name, message)
                continue
            successful.append(provider.name)
            offers.extend(offer for offer in provider_offers if is_relevant_offer(query, offer))

        by_identity: dict[tuple[str, str], SearchOffer] = {}
        for offer in offers:
            key = (offer.store, offer.external_id)
            current = by_identity.get(key)
            if current is None or offer.price < current.price:
                by_identity[key] = offer
        ordered = tuple(sorted(by_identity.values(), key=lambda offer: offer.price))
        return SearchSummary(ordered, len(successful), tuple(successful), tuple(failures))
