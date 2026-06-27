import logging
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from price_monitor.config import Settings
from price_monitor.models import Offer, OfferCheck, PriceCheck, Product, ProviderStatus, utc_now
from price_monitor.notifications.telegram import Notifier
from price_monitor.scrapers import PriceScraper
from price_monitor.scrapers.base import ScraperError
from price_monitor.scrapers.stores import profile_for_url
from price_monitor.search import ProductSearch, SearchLocation, SearchOffer
from price_monitor.search.base import SearchError, SearchSummary
from price_monitor.services.settings import get_default_location

logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class CheckOutcome:
    check: PriceCheck
    alerts_sent: int

    @property
    def alert_sent(self) -> bool:
        return self.alerts_sent > 0

    @property
    def successful(self) -> bool:
        return self.check.status != "error"


@dataclass(frozen=True, slots=True)
class MonitorStats:
    checked: int = 0
    successful: int = 0
    failed: int = 0
    alerts_sent: int = 0


class MonitorService:
    def __init__(
        self,
        session: Session,
        scraper: PriceScraper,
        notifier: Notifier,
        searcher: ProductSearch | None = None,
        settings: Settings | None = None,
    ):
        self.session = session
        self.scraper = scraper
        self.notifier = notifier
        self.searcher = searcher
        self.settings = settings or Settings()

    def _effective_location(self, product: Product) -> SearchLocation:
        default = get_default_location(self.session, self.settings)
        return SearchLocation(
            product.city or default.city, (product.state or default.state).upper()
        )

    def _record_provider_status(self, summary: SearchSummary) -> None:
        now = utc_now()
        for provider in summary.successful_providers:
            status = self.session.get(ProviderStatus, provider)
            if status is None:
                status = ProviderStatus(provider=provider)
                self.session.add(status)
            status.last_success_at = now
            status.last_error = None
        for failure in summary.errors:
            status = self.session.get(ProviderStatus, failure.provider)
            if status is None:
                status = ProviderStatus(provider=failure.provider)
                self.session.add(status)
            status.last_error_at = now
            status.last_error = failure.message

    def _upsert_offer(self, product: Product, found: SearchOffer, checked_at) -> Offer:
        offer = self.session.scalar(
            select(Offer).where(
                Offer.product_id == product.id,
                Offer.store == found.store,
                Offer.external_id == found.external_id,
            )
        )
        if offer is None:
            offer = Offer(
                product_id=product.id,
                store=found.store,
                external_id=found.external_id,
                title=found.title,
                url=found.url,
                condition=found.condition,
                city=found.city,
                state=found.state,
                currency=found.currency,
                current_price=found.price,
                first_seen_at=checked_at,
                last_seen_at=checked_at,
            )
            self.session.add(offer)
            self.session.flush()
        else:
            offer.title = found.title
            offer.url = found.url
            offer.condition = found.condition
            offer.city = found.city
            offer.state = found.state
            offer.currency = found.currency
            offer.current_price = found.price
            offer.last_seen_at = checked_at
            offer.active = True
        self.session.add(
            OfferCheck(offer_id=offer.id, checked_at=checked_at, price=found.price, available=True)
        )
        return offer

    def _maybe_alert_offer(self, product: Product, offer: Offer) -> bool:
        if offer.current_price > product.target_price:
            return False
        if offer.last_alerted_price is not None and offer.current_price >= offer.last_alerted_price:
            return False
        sent = self.notifier.send_price_alert(
            name=product.name,
            url=offer.url,
            price=offer.current_price,
            target_price=product.target_price,
            currency=offer.currency,
            store=offer.store,
            condition=offer.condition,
        )
        if sent:
            offer.last_alerted_price = offer.current_price
            offer.last_alerted_at = utc_now()
        return sent

    def _check_search_product(self, product: Product, checked_at) -> CheckOutcome:
        if self.searcher is None or product.search_query is None:
            raise SearchError("busca por nome não está configurada")
        summary = self.searcher.search(product.search_query, self._effective_location(product))
        self._record_provider_status(summary)
        if summary.providers_succeeded == 0:
            detail = "; ".join(failure.message for failure in summary.errors)
            raise SearchError(f"todas as fontes de busca falharam: {detail}")

        successful = set(summary.successful_providers)
        existing = list(self.session.scalars(select(Offer).where(Offer.product_id == product.id)))
        for offer in existing:
            if offer.store in successful:
                offer.active = False

        persisted = [self._upsert_offer(product, found, checked_at) for found in summary.offers]
        alerts_sent = sum(int(self._maybe_alert_offer(product, offer)) for offer in persisted)
        best = min(persisted, key=lambda offer: offer.current_price) if persisted else None
        status = "available" if best else "unavailable"
        check = PriceCheck(
            product_id=product.id,
            checked_at=checked_at,
            price=best.current_price if best else None,
            currency=best.currency if best else product.currency,
            available=best is not None,
            status=status,
            scraper=best.store if best else "Busca multi-loja",
            title=best.title if best else None,
            offer_url=best.url if best else None,
            offers_found=len(persisted),
        )
        product.last_checked_at = checked_at
        product.last_price = best.current_price if best else None
        product.last_status = status
        product.last_error = None
        product.last_offer_url = best.url if best else None
        product.last_store = best.store if best else None
        self.session.add(check)
        self.session.commit()
        self.session.refresh(check)
        return CheckOutcome(check, alerts_sent)

    def _check_direct_product(self, product: Product, checked_at) -> CheckOutcome:
        if not product.url:
            raise ScraperError("produto sem termo de busca ou URL")
        result = self.scraper.scrape(product.url)
        status = "available" if result.available and result.price is not None else "unavailable"
        check = PriceCheck(
            product_id=product.id,
            checked_at=checked_at,
            price=result.price,
            currency=result.currency,
            available=result.available,
            status=status,
            scraper=result.source,
            title=result.title,
            offer_url=product.url,
            offers_found=int(result.price is not None),
        )
        product.last_checked_at = checked_at
        product.last_price = result.price
        product.last_status = status
        product.last_error = None
        product.last_offer_url = product.url
        product.last_store = result.source
        alert_sent = False
        if result.price is not None and result.available:
            if result.price <= product.target_price and (
                product.last_alerted_price is None or result.price < product.last_alerted_price
            ):
                alert_sent = self.notifier.send_price_alert(
                    name=product.name,
                    url=product.url,
                    price=result.price,
                    target_price=product.target_price,
                    currency=result.currency,
                    store=result.source,
                    condition="desconhecido",
                )
                if alert_sent:
                    product.last_alerted_price = result.price
        self.session.add(check)
        self.session.commit()
        self.session.refresh(check)
        return CheckOutcome(check, int(alert_sent))

    def check_product(self, product_id: int) -> CheckOutcome:
        product = self.session.get(Product, product_id)
        if product is None:
            raise LookupError(f"produto {product_id} não encontrado")
        checked_at = utc_now()
        try:
            if product.search_query:
                return self._check_search_product(product, checked_at)
            return self._check_direct_product(product, checked_at)
        except (ScraperError, SearchError) as exc:
            profile = profile_for_url(product.url or "")
            check = PriceCheck(
                product_id=product.id,
                checked_at=checked_at,
                price=None,
                currency=product.currency,
                available=False,
                status="error",
                scraper=profile.name if profile else "Busca multi-loja",
                error=str(exc),
                offers_found=0,
            )
            product.last_checked_at = checked_at
            product.last_status = "error"
            product.last_error = str(exc)
            self.session.add(check)
            self.session.commit()
            self.session.refresh(check)
            logger.warning("falha ao verificar %s: %s", product.name, exc)
            return CheckOutcome(check, 0)

    def run_all(self) -> MonitorStats:
        product_ids = list(
            self.session.scalars(
                select(Product.id).where(Product.active.is_(True)).order_by(Product.id)
            )
        )
        successful = failed = alerts_sent = 0
        for product_id in product_ids:
            outcome = self.check_product(product_id)
            if outcome.successful:
                successful += 1
            else:
                failed += 1
            alerts_sent += outcome.alerts_sent
        return MonitorStats(len(product_ids), successful, failed, alerts_sent)
