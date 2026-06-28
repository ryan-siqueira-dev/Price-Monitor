import os
from pathlib import Path

from price_monitor.config import Settings
from price_monitor.search.base import SearchError
from price_monitor.search.providers import browser_profiles


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
