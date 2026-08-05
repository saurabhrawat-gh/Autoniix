from __future__ import annotations

from pydantic_settings import BaseSettings, SettingsConfigDict


class Config(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    database_url: str = "postgresql://app:change_me@localhost:5433/autoniix"
    http_addr: str = "0.0.0.0:8090"
    poll_interval_ms: int = 15000
    stale_after_ms: int = 60000
    batch_size: int = 50
    max_attempts: int = 3
    http_timeout_ms: int = 10000
    slack_webhook_url: str = ""


settings = Config()
