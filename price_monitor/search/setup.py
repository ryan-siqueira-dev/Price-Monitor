import os
import webbrowser
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlparse

from price_monitor.config import Settings
from price_monitor.search.auth import MercadoLivreAuth
from price_monitor.search.base import SearchError
from price_monitor.search.providers import browser_profiles


def setup_mercado_livre(settings: Settings) -> None:
    if not settings.mercado_livre_client_secret:
        raise SearchError("configure PRICE_MONITOR_MERCADO_LIVRE_CLIENT_SECRET")
    auth = MercadoLivreAuth(settings)
    redirect = urlparse(settings.mercado_livre_redirect_uri)
    if redirect.hostname not in {"127.0.0.1", "localhost"} or not redirect.port:
        raise SearchError("o redirect OAuth guiado deve apontar para localhost com uma porta")

    class CallbackHandler(BaseHTTPRequestHandler):
        code: str | None = None
        error: str | None = None

        def do_GET(self) -> None:  # noqa: N802
            params = parse_qs(urlparse(self.path).query)
            type(self).code = (params.get("code") or [None])[0]
            type(self).error = (params.get("error") or [None])[0]
            message = "Autorização concluída. Você pode fechar esta janela."
            self.send_response(200)
            self.send_header("Content-Type", "text/plain; charset=utf-8")
            self.end_headers()
            self.wfile.write(message.encode())

        def log_message(self, _format: str, *_args) -> None:
            return

    server = HTTPServer((redirect.hostname, redirect.port), CallbackHandler)
    server.timeout = 180
    url = auth.authorization_url()
    print(f"Abra esta URL para autorizar o Mercado Livre:\n{url}")
    webbrowser.open(url)
    server.handle_request()
    server.server_close()
    if CallbackHandler.error:
        raise SearchError(f"autorização recusada: {CallbackHandler.error}")
    if not CallbackHandler.code:
        raise SearchError("tempo de autorização esgotado")
    auth.exchange_code(CallbackHandler.code)
    print("Mercado Livre autenticado")


def setup_browser_provider(settings: Settings, provider_name: str) -> None:
    profile = next(
        (item for item in browser_profiles() if item.name.casefold() == provider_name.casefold()),
        None,
    )
    if profile is None:
        raise SearchError(f"provedor de navegador desconhecido: {provider_name}")
    try:
        from playwright.sync_api import sync_playwright

        slug = provider_name.lower().replace(" ", "-")
        profile_dir = Path(settings.auth_dir) / "browser" / slug
        profile_dir.mkdir(parents=True, exist_ok=True)
        os.chmod(profile_dir, 0o700)
        with sync_playwright() as playwright:
            context = playwright.chromium.launch_persistent_context(
                str(profile_dir), headless=False, locale="pt-BR"
            )
            page = context.pages[0] if context.pages else context.new_page()
            page.goto(profile.home_url, wait_until="domcontentloaded")
            input(
                f"Faça login e conclua verificações em {profile.name}. "
                "Depois pressione Enter aqui..."
            )
            context.close()
    except Exception as exc:
        if isinstance(exc, SearchError):
            raise
        raise SearchError(f"não foi possível preparar {provider_name}: {exc}") from exc
    print(f"Sessão de {profile.name} salva em {profile_dir}")
