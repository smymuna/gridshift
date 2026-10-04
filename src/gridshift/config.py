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
    log_level: str = "INFO"
