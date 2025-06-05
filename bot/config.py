"""Application configuration module."""

from pydantic import BaseSettings, Field
from typing import List


class Settings(BaseSettings):
    """Environment settings."""

    telegram_token: str = Field("", env="TELEGRAM_TOKEN")
    admin_ids: List[int] = Field(default_factory=list, env="ADMIN_IDS")
    super_admin_ids: List[int] = Field(default_factory=list, env="SUPER_ADMIN_IDS")
    monero_rpc_url: str = Field("", env="MONERO_RPC_URL")
    encryption_key: str = Field("", env="ENCRYPTION_KEY")
    totp_secret: str | None = Field(None, env="TOTP_SECRET")
    data_retention_days: int = Field(30, env="DATA_RETENTION_DAYS")
    default_commission_rate: float = Field(0.05, env="DEFAULT_COMMISSION_RATE")

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


_settings: Settings | None = None

def get_settings() -> Settings:  # pragma: no cover
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
