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
    "carcaca",
    "case",
    "conjunto",
    "cooler",
    "dock",
    "dobradica",
    "display",
    "fonte",
    "kit",
    "lcd",
    "memoria",
    "mouse",
    "palmrest",
    "pelicula",
    "placa",
    "ssd",
    "suporte",
    "tampa",
    "teclado",
    "tela",
    "touchpad",
    "ventoinha",
}
STOP_WORDS = {"a", "as", "com", "da", "das", "de", "do", "dos", "e", "o", "os", "para"}


def normalized_tokens(value: str) -> set[str]:
    return set(normalized_token_sequence(value))


def normalized_token_sequence(value: str) -> list[str]:
    normalized = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return [token for token in re.findall(r"[a-z0-9]+", normalized) if token not in STOP_WORDS]


def is_relevant_offer(query: str, offer: SearchOffer) -> bool:
    query_sequence = normalized_token_sequence(query)
    title_sequence = normalized_token_sequence(offer.title)
    query_tokens = set(query_sequence)
    title_tokens = set(title_sequence)
    if not query_tokens or not query_tokens.issubset(title_tokens):
        return False

    query_is_accessory = bool(set(query_sequence[:2]) & ACCESSORY_TERMS)
    accessory_in_title_prefix = bool(set(title_sequence[:4]) & ACCESSORY_TERMS)
    accessory_category = bool(normalized_tokens(" ".join(offer.categories)) & ACCESSORY_TERMS)
    return query_is_accessory or not (accessory_in_title_prefix or accessory_category)
