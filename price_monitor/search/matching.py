import re
import unicodedata

from price_monitor.search.base import SearchOffer

ACCESSORY_TERMS = {
    "acessorio",
    "acessorios",
    "adaptador",
    "bateria",
    "bolsa",
    "cabo",
    "capa",
    "carregador",
    "case",
    "cooler",
    "dock",
    "dobradica",
    "fonte",
    "pelicula",
    "suporte",
    "ventoinha",
}
STOP_WORDS = {"a", "as", "com", "da", "das", "de", "do", "dos", "e", "o", "os", "para"}


def normalized_tokens(value: str) -> set[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return {token for token in re.findall(r"[a-z0-9]+", normalized) if token not in STOP_WORDS}


def is_relevant_offer(query: str, offer: SearchOffer) -> bool:
    query_tokens = normalized_tokens(query)
    title_tokens = normalized_tokens(offer.title)
    if not query_tokens or not query_tokens.issubset(title_tokens):
        return False

    context_tokens = title_tokens | normalized_tokens(" ".join(offer.categories))
    query_is_accessory = bool(query_tokens & ACCESSORY_TERMS)
    return query_is_accessory or not bool(context_tokens & ACCESSORY_TERMS)
