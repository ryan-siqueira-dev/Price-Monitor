from functools import lru_cache
from pathlib import Path

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_prefix="PRICE_MONITOR_",
        extra="ignore",
    )

    database_url: str = "sqlite:///data/price_monitor.db"
    request_timeout_seconds: float = Field(default=20.0, gt=0)
    use_browser: bool = False
    browser_timeout_ms: int = Field(default=30_000, gt=0)
    search_max_results_per_store: int = Field(default=20, ge=1, le=50)
    default_city: str = "Itajaí"
    default_state: str = Field(default="SC", min_length=2, max_length=2)
    auth_dir: Path = Path("data/auth")
    browser_headless: bool = True
    mercado_livre_client_id: str | None = None
    mercado_livre_client_secret: str | None = None
    mercado_livre_redirect_uri: str = "http://127.0.0.1:8766/callback"
    mercado_livre_access_token: str | None = None
    user_agent: str = (
        "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/131.0 Safari/537.36"
    )
    telegram_bot_token: str | None = None
    telegram_chat_id: str | None = None
    scheduler_interval_hours: float = Field(default=24.0, gt=0)
    log_level: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()
