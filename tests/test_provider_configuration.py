import pytest

from price_monitor.cli import _parser
from price_monitor.scrapers.stores import supported_stores
from price_monitor.search.providers import browser_profiles
from price_monitor.search.service import search_provider_names


def test_only_supported_search_providers_are_exposed():
    assert search_provider_names() == ["OLX", "Amazon", "KaBuM", "Carrefour"]
    assert [profile.name for profile in browser_profiles()] == ["OLX", "Amazon", "KaBuM"]
    assert "Mercado Livre" not in supported_stores()
    assert "Magazine Luiza" not in supported_stores()


def test_cli_auth_setup_only_accepts_active_browser_providers():
    parser = _parser()
    for provider in ("olx", "amazon", "kabum"):
        assert parser.parse_args(["auth", "setup", provider]).provider == provider

    with pytest.raises(SystemExit):
        parser.parse_args(["auth", "setup", "mercado-livre"])
    with pytest.raises(SystemExit):
        parser.parse_args(["auth", "setup", "magalu"])
