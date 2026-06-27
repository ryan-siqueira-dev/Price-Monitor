import json
import os
import time
from pathlib import Path
from urllib.parse import urlencode

import httpx

from price_monitor.config import Settings
from price_monitor.search.base import SearchError


class MercadoLivreAuth:
    authorize_endpoint = "https://auth.mercadolivre.com.br/authorization"
    token_endpoint = "https://api.mercadolibre.com/oauth/token"

    def __init__(self, settings: Settings, transport: httpx.BaseTransport | None = None):
        self.settings = settings
        self.transport = transport
        self.path = Path(settings.auth_dir) / "mercado_livre.json"

    def authorization_url(self) -> str:
        if not self.settings.mercado_livre_client_id:
            raise SearchError("configure PRICE_MONITOR_MERCADO_LIVRE_CLIENT_ID")
        query = urlencode(
            {
                "response_type": "code",
                "client_id": self.settings.mercado_livre_client_id,
                "redirect_uri": self.settings.mercado_livre_redirect_uri,
            }
        )
        return f"{self.authorize_endpoint}?{query}"

    def _load(self) -> dict:
        if not self.path.exists():
            return {}
        try:
            return json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise SearchError(f"credencial do Mercado Livre inválida: {exc}") from exc

    def _save(self, payload: dict) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp_path = self.path.with_suffix(".tmp")
        temp_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        os.chmod(temp_path, 0o600)
        temp_path.replace(self.path)

    def _request_token(self, payload: dict) -> dict:
        try:
            with httpx.Client(timeout=20, transport=self.transport) as client:
                response = client.post(self.token_endpoint, data=payload)
                response.raise_for_status()
                data = response.json()
        except (httpx.HTTPError, ValueError) as exc:
            raise SearchError(f"falha na autenticação do Mercado Livre: {exc}") from exc
        data["expires_at"] = int(time.time()) + int(data.get("expires_in") or 0)
        self._save(data)
        return data

    def exchange_code(self, code: str) -> None:
        self._request_token(
            {
                "grant_type": "authorization_code",
                "client_id": self.settings.mercado_livre_client_id,
                "client_secret": self.settings.mercado_livre_client_secret,
                "code": code,
                "redirect_uri": self.settings.mercado_livre_redirect_uri,
            }
        )

    def refresh(self) -> str:
        current = self._load()
        refresh_token = current.get("refresh_token")
        if not refresh_token:
            raise SearchError("Mercado Livre não autenticado; execute auth setup")
        updated = self._request_token(
            {
                "grant_type": "refresh_token",
                "client_id": self.settings.mercado_livre_client_id,
                "client_secret": self.settings.mercado_livre_client_secret,
                "refresh_token": refresh_token,
            }
        )
        return str(updated["access_token"])

    def access_token(self) -> str:
        if self.settings.mercado_livre_access_token:
            return self.settings.mercado_livre_access_token
        current = self._load()
        token = current.get("access_token")
        if not token:
            raise SearchError("Mercado Livre não autenticado; execute auth setup")
        if int(current.get("expires_at") or 0) <= int(time.time()) + 60:
            return self.refresh()
        return str(token)
