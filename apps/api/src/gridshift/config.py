from __future__ import annotations

from pydantic import Field, HttpUrl
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Runtime configuration, read from ``GRIDSHIFT_*`` environment variables."""

    model_config = SettingsConfigDict(env_prefix="GRIDSHIFT_", env_file=".env", extra="ignore")

    energy_charts_url: HttpUrl = HttpUrl("https://api.energy-charts.info")
    http_timeout_s: float = Field(default=10.0, gt=0)
    max_retries: int = Field(default=3, ge=0, le=10)
    cache_ttl_s: float = Field(default=900.0, ge=0)
    cache_max_stale_s: float = Field(default=6 * 3600.0, ge=0)
    """How old cached data may be when the provider is failing (serve stale on error)."""
    upstream_min_interval_s: float = Field(default=1.0, ge=0)
    """Minimum gap between calls to Energy-Charts, which rate limits bursts."""
    cors_origins: list[str] = ["http://localhost:3000"]
    cors_origin_regex: str | None = None
    log_level: str = "INFO"
