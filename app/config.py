"""Application configuration, loaded from environment variables."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    # --- RapidAPI integration ---
    # Shared secret RapidAPI injects into every proxied request. When set, requests
    # missing or mismatching this header are rejected. Leave unset for local dev.
    rapidapi_proxy_secret: str | None = None

    # --- Upstream data sources ---
    forexfactory_base_url: str = "https://nfs.faireconomy.media"
    finnhub_api_key: str | None = None
    finnhub_base_url: str = "https://finnhub.io/api/v1"
    http_timeout_seconds: float = 10.0

    # --- Caching ---
    cache_ttl_seconds: int = 900  # 15 minutes

    # --- Redis (rate limiting + cache) ---
    redis_url: str = "redis://localhost:6379/0"

    # --- Rate limiting tiers (requests per calendar month) ---
    rate_limit_free: int = 50
    rate_limit_basic: int = 1_000
    rate_limit_pro: int = 10_000
    rate_limit_business: int = 100_000

    @property
    def tier_limits(self) -> dict[str, int]:
        return {
            "FREE": self.rate_limit_free,
            "BASIC": self.rate_limit_basic,
            "PRO": self.rate_limit_pro,
            "BUSINESS": self.rate_limit_business,
        }


@lru_cache
def get_settings() -> Settings:
    return Settings()
