import httpx

from price_monitor.config import Settings
from price_monitor.scrapers.base import ScraperError


class HttpFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch(self, url: str) -> str:
        headers = {
            "User-Agent": self.settings.user_agent,
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "pt-BR,pt;q=0.9,en;q=0.7",
        }
        try:
            with httpx.Client(
                headers=headers,
                timeout=self.settings.request_timeout_seconds,
                follow_redirects=True,
            ) as client:
                response = client.get(url)
                response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            raise ScraperError(f"site respondeu HTTP {exc.response.status_code}") from exc
        except httpx.HTTPError as exc:
            raise ScraperError(f"falha de rede: {exc}") from exc
        return response.text


class BrowserFetcher:
    def __init__(self, settings: Settings):
        self.settings = settings

    def fetch(self, url: str, wait_ms: int = 1_500) -> str:
        try:
            from playwright.sync_api import Error, sync_playwright

            with sync_playwright() as playwright:
                browser = playwright.chromium.launch(headless=True)
                page = browser.new_page(user_agent=self.settings.user_agent, locale="pt-BR")
                page.goto(
                    url,
                    wait_until="domcontentloaded",
                    timeout=self.settings.browser_timeout_ms,
                )
                page.wait_for_timeout(wait_ms)
                html = page.content()
                browser.close()
                return html
        except ImportError as exc:
            raise ScraperError("Playwright não está instalado") from exc
        except Error as exc:
            message = str(exc).splitlines()[0]
            raise ScraperError(f"falha no navegador: {message}") from exc
