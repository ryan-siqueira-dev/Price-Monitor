from price_monitor.config import Settings, get_settings
from price_monitor.scrapers.base import PriceNotFoundError, ScraperError, ScrapeResult
from price_monitor.scrapers.fetchers import BrowserFetcher, HttpFetcher
from price_monitor.scrapers.parser import parse_product_page
from price_monitor.scrapers.stores import profile_for_url


class PriceScraper:
    def __init__(self, settings: Settings | None = None):
        self.settings = settings or get_settings()
        self.http = HttpFetcher(self.settings)
        self.browser = BrowserFetcher(self.settings)

    def scrape(self, url: str) -> ScrapeResult:
        profile = profile_for_url(url)
        http_error: ScraperError | None = None

        try:
            html = self.http.fetch(url)
            result = parse_product_page(html, profile)
            if result is not None:
                return result
        except ScraperError as exc:
            http_error = exc

        if self.settings.use_browser:
            html = self.browser.fetch(url)
            result = parse_product_page(html, profile)
            if result is not None:
                return result

        if http_error:
            raise http_error
        source = profile.name if profile else "o extrator genérico"
        suffix = (
            "; habilite PRICE_MONITOR_USE_BROWSER=true" if not self.settings.use_browser else ""
        )
        raise PriceNotFoundError(f"preço não encontrado por {source}{suffix}")
