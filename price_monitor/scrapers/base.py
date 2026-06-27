from dataclasses import dataclass
from decimal import Decimal


class ScraperError(RuntimeError):
    """Erro esperado ao acessar ou interpretar uma pagina de produto."""


class PriceNotFoundError(ScraperError):
    pass


@dataclass(frozen=True, slots=True)
class ScrapeResult:
    price: Decimal | None
    currency: str
    title: str | None
    available: bool
    source: str
