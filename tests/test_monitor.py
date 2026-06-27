from decimal import Decimal

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from price_monitor.db import Base
from price_monitor.models import Offer, OfferCheck, PriceCheck, Product
from price_monitor.scrapers.base import ScraperError, ScrapeResult
from price_monitor.search.base import SearchOffer, SearchSummary
from price_monitor.services.monitor import MonitorService


class FakeScraper:
    def __init__(self, result=None, error=None):
        self.result = result
        self.error = error

    def scrape(self, _url):
        if self.error:
            raise self.error
        return self.result


class FakeNotifier:
    def __init__(self):
        self.messages = []

    def send_price_alert(self, **payload):
        self.messages.append(payload)
        return True


class FakeSearcher:
    def __init__(self, offers):
        self.offers = tuple(offers)

    def search(self, _query, _location=None):
        return SearchSummary(
            self.offers,
            providers_succeeded=3,
            successful_providers=("Loja A", "Loja B", "Loja C"),
        )


def session_with_product(target_price=Decimal("3000.00")):
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    product = Product(
        name="Notebook de teste",
        url="https://example.com/notebook",
        target_price=target_price,
    )
    session.add(product)
    session.commit()
    return session, product


def test_check_records_price_and_sends_only_one_alert():
    session, product = session_with_product()
    scraper = FakeScraper(ScrapeResult(Decimal("2500.00"), "BRL", "Notebook", True, "Test"))
    notifier = FakeNotifier()
    service = MonitorService(session, scraper, notifier)

    first = service.check_product(product.id)
    second = service.check_product(product.id)

    assert first.alert_sent is True
    assert second.alert_sent is False
    assert product.last_price == Decimal("2500.00")
    assert product.last_status == "available"
    assert len(notifier.messages) == 1
    assert len(list(session.scalars(select(PriceCheck)))) == 2


def test_check_records_expected_scraper_error():
    session, product = session_with_product()
    service = MonitorService(session, FakeScraper(error=ScraperError("bloqueado")), FakeNotifier())

    outcome = service.check_product(product.id)

    assert outcome.successful is False
    assert outcome.check.error == "bloqueado"
    assert product.last_status == "error"


def test_run_all_ignores_inactive_products():
    session, product = session_with_product(target_price=Decimal("1000.00"))
    session.add(
        Product(
            name="Inativo",
            url="https://example.com/inativo",
            target_price=Decimal("1000.00"),
            active=False,
        )
    )
    session.commit()
    scraper = FakeScraper(ScrapeResult(Decimal("2000.00"), "BRL", None, True, "Test"))

    stats = MonitorService(session, scraper, FakeNotifier()).run_all()

    assert stats.checked == 1
    assert stats.successful == 1
    assert product.last_price == Decimal("2000.00")


def test_search_product_uses_lowest_offer_and_alerts_with_offer_url():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    product = Product(
        name="ThinkPad T14",
        search_query="ThinkPad T14",
        target_price=Decimal("3000.00"),
    )
    session.add(product)
    session.commit()
    offers = [
        SearchOffer(
            "a-1",
            "Lenovo ThinkPad T14",
            Decimal("3200.00"),
            "BRL",
            "https://loja-a.example/t14",
            "Loja A",
        ),
        SearchOffer(
            "b-1",
            "Notebook Lenovo ThinkPad T14",
            Decimal("2800.00"),
            "BRL",
            "https://loja-b.example/t14",
            "Loja B",
        ),
    ]
    notifier = FakeNotifier()
    service = MonitorService(session, FakeScraper(), notifier, FakeSearcher(offers))

    outcome = service.check_product(product.id)

    assert outcome.alert_sent is True
    assert outcome.check.price == Decimal("2800.00")
    assert outcome.check.offers_found == 2
    assert outcome.check.offer_url == "https://loja-b.example/t14"
    assert product.last_store == "Loja B"
    assert notifier.messages[0]["url"] == "https://loja-b.example/t14"


def test_search_alerts_every_offer_once_and_realerts_only_after_price_drop():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    session = Session(engine, expire_on_commit=False)
    product = Product(
        name="ThinkPad T14",
        search_query="ThinkPad T14",
        target_price=Decimal("3000.00"),
    )
    session.add(product)
    session.commit()
    searcher = FakeSearcher(
        [
            SearchOffer(
                "a-1",
                "ThinkPad T14 usado",
                Decimal("2900.00"),
                "BRL",
                "https://a.example/t14",
                "Loja A",
                "usado",
            ),
            SearchOffer(
                "b-1",
                "ThinkPad T14 novo",
                Decimal("2950.00"),
                "BRL",
                "https://b.example/t14",
                "Loja B",
                "novo",
            ),
        ]
    )
    notifier = FakeNotifier()
    service = MonitorService(session, FakeScraper(), notifier, searcher)

    first = service.check_product(product.id)
    second = service.check_product(product.id)
    searcher.offers = (
        SearchOffer(
            "a-1",
            "ThinkPad T14 usado",
            Decimal("2800.00"),
            "BRL",
            "https://a.example/t14",
            "Loja A",
            "usado",
        ),
        searcher.offers[1],
    )
    third = service.check_product(product.id)

    assert first.alerts_sent == 2
    assert second.alerts_sent == 0
    assert third.alerts_sent == 1
    assert len(notifier.messages) == 3
    assert len(list(session.scalars(select(Offer)))) == 2
    assert len(list(session.scalars(select(OfferCheck)))) == 6
