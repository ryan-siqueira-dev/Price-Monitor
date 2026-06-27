from decimal import Decimal

import pytest

from price_monitor.scrapers.parser import parse_price, parse_product_page
from price_monitor.scrapers.stores import profile_for_url


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("R$ 2.499,90", Decimal("2499.90")),
        ("2499.90", Decimal("2499.90")),
        ("2.499", Decimal("2499.00")),
        ("2499", Decimal("2499.00")),
        ("R$ 0,00", None),
        ("sem preço", None),
    ],
)
def test_parse_price(raw, expected):
    assert parse_price(raw) == expected


def test_parse_json_ld_product():
    html = """
    <html><head>
      <script type="application/ld+json">
        {
          "@context": "https://schema.org",
          "@type": "Product",
          "name": "Notebook Exemplo",
          "offers": {
            "@type": "Offer",
            "price": "3499.90",
            "priceCurrency": "BRL",
            "availability": "https://schema.org/InStock"
          }
        }
      </script>
    </head></html>
    """
    result = parse_product_page(html)
    assert result is not None
    assert result.price == Decimal("3499.90")
    assert result.currency == "BRL"
    assert result.title == "Notebook Exemplo"
    assert result.available is True


def test_parse_store_selector():
    profile = profile_for_url("https://www.amazon.com.br/dp/example")
    html = """
    <html><h1>Notebook</h1><div class="priceToPay">
      <span class="a-offscreen">R$ 4.299,00</span>
    </div></html>
    """
    result = parse_product_page(html, profile)
    assert result is not None
    assert result.price == Decimal("4299.00")
    assert result.source == "Amazon Brasil"


def test_detect_unavailable_product():
    result = parse_product_page("<html><h1>Notebook</h1><p>Produto indisponível</p></html>")
    assert result is not None
    assert result.available is False
    assert result.price is None
