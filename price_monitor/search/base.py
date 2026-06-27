from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol


class SearchError(RuntimeError):
    """Erro esperado ao consultar ou interpretar uma fonte de busca."""


@dataclass(frozen=True, slots=True)
class SearchOffer:
    external_id: str
    title: str
    price: Decimal
    currency: str
    url: str
    store: str
    condition: str = "desconhecido"
    city: str | None = None
    state: str | None = None
    categories: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class SearchLocation:
    city: str
    state: str


@dataclass(frozen=True, slots=True)
class SearchSummary:
    offers: tuple[SearchOffer, ...]
    providers_succeeded: int
    successful_providers: tuple[str, ...] = ()
    errors: tuple["ProviderFailure", ...] = ()


@dataclass(frozen=True, slots=True)
class ProviderFailure:
    provider: str
    message: str


class SearchProvider(Protocol):
    name: str

    def search(self, query: str, location: SearchLocation | None = None) -> list[SearchOffer]: ...
