import json
from decimal import Decimal

from price_monitor.config import Settings
from price_monitor.search.base import SearchError, SearchLocation, SearchOffer
from price_monitor.search.matching import is_relevant_offer
from price_monitor.search.providers import (
    BrowserSearchProvider,
    browser_profiles,
    parse_vtex_products,
)
from price_monitor.search.service import ProductSearch


class FakeProvider:
    def __init__(self, name, offers=None, error=None):
        self.name = name
        self.offers = offers or []
        self.error = error

    def search(self, _query, _location=None):
        if self.error:
            raise self.error
        return self.offers


def offer(title, price="100.00", url="https://example.com/product", store="Teste"):
    return SearchOffer("external-id", title, Decimal(price), "BRL", url, store)


def test_matching_rejects_accessory_for_main_product_query():
    assert is_relevant_offer("ThinkPad T14", offer("Notebook Lenovo ThinkPad T14"))
    assert is_relevant_offer(
        "ThinkPad T14", offer("Notebook Lenovo ThinkPad T14 com SSD e tela touch")
    )
    assert not is_relevant_offer("ThinkPad T14", offer("Cooler para ThinkPad T14"))
    assert not is_relevant_offer("ThinkPad T14", offer("Teclado para notebook ThinkPad T14"))
    assert not is_relevant_offer("ThinkPad T14", offer("Placa mãe Lenovo ThinkPad T14"))
    assert not is_relevant_offer("ThinkPad T14", offer("Tampa com LCD ThinkPad T14"))
    assert is_relevant_offer("cooler ThinkPad T14", offer("Cooler para ThinkPad T14"))
    assert is_relevant_offer("teclado ThinkPad T14", offer("Teclado para ThinkPad T14"))


def test_product_search_combines_filters_and_sorts_providers():
    providers = [
        FakeProvider(
            "A",
            [
                offer("ThinkPad T14", "3200.00", "https://a.example/t14", "A"),
                offer("Capa ThinkPad T14", "50.00", "https://a.example/capa", "A"),
            ],
        ),
        FakeProvider(
            "B", [offer("Notebook ThinkPad T14", "2800.00", "https://b.example/t14", "B")]
        ),
    ]
    summary = ProductSearch(Settings(_env_file=None), providers).search("ThinkPad T14")

    assert [item.price for item in summary.offers] == [Decimal("2800.00"), Decimal("3200.00")]
    assert summary.successful_providers == ("A", "B")


def test_product_search_fails_only_when_every_provider_fails():
    providers = [FakeProvider("A", error=SearchError("A indisponível"))]

    summary = ProductSearch(Settings(_env_file=None), providers).search("ThinkPad T14")

    assert summary.providers_succeeded == 0
    assert summary.errors[0].provider == "A"


def test_parse_vtex_products_uses_lowest_available_price():
    data = [
        {
            "productName": "Notebook ThinkPad T14",
            "link": "https://example.com/t14",
            "categories": ["/Informática/Notebooks/"],
            "items": [
                {
                    "sellers": [
                        {
                            "commertialOffer": {
                                "AvailableQuantity": 1,
                                "Price": 3100.0,
                                "spotPrice": 2900.0,
                            }
                        },
                        {
                            "commertialOffer": {
                                "AvailableQuantity": 0,
                                "Price": 1000.0,
                            }
                        },
                    ]
                }
            ],
        }
    ]

    offers = parse_vtex_products(data, "Loja")

    assert len(offers) == 1
    assert offers[0].price == Decimal("2900.00")
    assert offers[0].store == "Loja"


def test_browser_provider_parses_kabum_cards(monkeypatch):
    html = """
    <a href="/produto/123/notebook-thinkpad-t14">
      <img alt="">
      <span class="text-ellipsis">Notebook Lenovo ThinkPad T14 usado</span>
      <span>R$ 2.999,90 no PIX</span>
    </a>
    """
    profile = next(item for item in browser_profiles() if item.name == "KaBuM")
    provider = BrowserSearchProvider(
        profile, Settings(_env_file=None, search_max_results_per_store=5)
    )
    captured = {}

    def fetch(url):
        captured["url"] = url
        return html

    monkeypatch.setattr(provider, "_fetch", fetch)

    offers = provider.search("ThinkPad T14")

    assert len(offers) == 1
    assert captured["url"] == "https://www.kabum.com.br/busca/ThinkPad-T14"
    assert offers[0].price == Decimal("2999.90")
    assert offers[0].condition == "usado"
    assert offers[0].url == "https://www.kabum.com.br/produto/123/notebook-thinkpad-t14"


def test_browser_provider_parses_amazon_link_and_removes_tracking_query(monkeypatch):
    html = """
    <div data-component-type="s-search-result">
      <a class="a-link-normal s-no-outline"
         href="/Lenovo-ThinkPad/dp/B0123/ref=sr_1?tag=tracking"></a>
      <h2><span>Notebook Lenovo ThinkPad T14</span></h2>
      <span class="a-price"><span class="a-offscreen">R$ 4.999,00</span></span>
    </div>
    """
    profile = next(item for item in browser_profiles() if item.name == "Amazon")
    provider = BrowserSearchProvider(profile, Settings(_env_file=None))
    monkeypatch.setattr(provider, "_fetch", lambda _url: html)

    offers = provider.search("ThinkPad T14")

    assert len(offers) == 1
    assert offers[0].price == Decimal("4999.00")
    assert offers[0].external_id == "B0123"
    assert offers[0].url == "https://www.amazon.com.br/dp/B0123"


def test_browser_provider_parses_and_filters_olx_next_data(monkeypatch):
    ads = [
        {
            "subject": "Lenovo ThinkPad T14 usado",
            "priceValue": "R$ 2.550",
            "listId": 123,
            "url": "https://sc.olx.com.br/thinkpad-t14-123?lis=search",
            "category": "Notebooks",
            "locationDetails": {"municipality": "Itajaí", "uf": "SC"},
        },
        {
            "subject": "Lenovo ThinkPad T14",
            "priceValue": "R$ 2.400",
            "listId": 456,
            "url": "https://sc.olx.com.br/thinkpad-t14-456",
            "locationDetails": {"municipality": "Florianópolis", "uf": "SC"},
        },
    ]
    payload = {"props": {"pageProps": {"ads": ads}}}
    html = f'<script id="__NEXT_DATA__" type="application/json">{json.dumps(payload)}</script>'
    profile = next(item for item in browser_profiles() if item.name == "OLX")
    provider = BrowserSearchProvider(profile, Settings(_env_file=None))
    monkeypatch.setattr(provider, "_fetch", lambda _url: html)

    offers = provider.search("ThinkPad T14", SearchLocation("Itajai", "sc"))

    assert len(offers) == 1
    assert offers[0].external_id == "123"
    assert offers[0].price == Decimal("2550.00")
    assert offers[0].city == "Itajaí"
    assert offers[0].state == "SC"
    assert offers[0].url == "https://sc.olx.com.br/thinkpad-t14-123"
