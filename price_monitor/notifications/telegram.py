import logging
from decimal import Decimal
from typing import Protocol

import httpx

from price_monitor.config import Settings

logger = logging.getLogger(__name__)


class Notifier(Protocol):
    def send_price_alert(
        self,
        *,
        name: str,
        url: str,
        price: Decimal,
        target_price: Decimal,
        currency: str,
        store: str,
        condition: str,
    ) -> bool: ...


class NullNotifier:
    def send_price_alert(self, **_kwargs) -> bool:
        logger.info("alerta não enviado: Telegram não configurado")
        return False


class TelegramNotifier:
    def __init__(self, token: str, chat_id: str, timeout: float = 20.0):
        self.token = token
        self.chat_id = chat_id
        self.timeout = timeout

    def send_price_alert(
        self,
        *,
        name: str,
        url: str,
        price: Decimal,
        target_price: Decimal,
        currency: str,
        store: str,
        condition: str,
    ) -> bool:
        text = (
            "📉 Preço desejado encontrado!\n\n"
            f"{name}\n"
            f"Loja: {store}\n"
            f"Condição: {condition}\n"
            f"Preço: {currency} {price:.2f}\n"
            f"Meta: {currency} {target_price:.2f}\n"
            f"{url}"
        )
        endpoint = f"https://api.telegram.org/bot{self.token}/sendMessage"
        try:
            response = httpx.post(
                endpoint,
                json={"chat_id": self.chat_id, "text": text, "disable_web_page_preview": True},
                timeout=self.timeout,
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            logger.error("falha ao enviar alerta do Telegram: %s", exc)
            return False
        return True


def build_notifier(settings: Settings) -> Notifier:
    if settings.telegram_bot_token and settings.telegram_chat_id:
        return TelegramNotifier(
            settings.telegram_bot_token,
            settings.telegram_chat_id,
            settings.request_timeout_seconds,
        )
    return NullNotifier()
