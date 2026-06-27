import json
import time

import httpx

from price_monitor.config import Settings
from price_monitor.search.auth import MercadoLivreAuth


def test_expired_mercado_livre_token_is_refreshed(tmp_path):
    auth_dir = tmp_path / "auth"
    auth_dir.mkdir()
    token_path = auth_dir / "mercado_livre.json"
    token_path.write_text(
        json.dumps(
            {
                "access_token": "expired",
                "refresh_token": "refresh",
                "expires_at": int(time.time()) - 10,
            }
        ),
        encoding="utf-8",
    )

    def handler(request: httpx.Request) -> httpx.Response:
        assert request.url.path == "/oauth/token"
        return httpx.Response(
            200,
            json={"access_token": "new-token", "refresh_token": "new-refresh", "expires_in": 3600},
        )

    settings = Settings(
        _env_file=None,
        auth_dir=auth_dir,
        mercado_livre_client_id="client",
        mercado_livre_client_secret="secret",
    )
    auth = MercadoLivreAuth(settings, httpx.MockTransport(handler))

    assert auth.access_token() == "new-token"
    assert json.loads(token_path.read_text(encoding="utf-8"))["refresh_token"] == "new-refresh"
