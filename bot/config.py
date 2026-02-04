"""Application configuration module."""

from pydantic_settings import BaseSettings
from pydantic import Field, field_validator
from typing import List
import base64


def parse_ids(v) -> List[int]:
    """Parse comma-separated IDs string into list of integers."""
    if isinstance(v, list):
        return v
    if isinstance(v, str):
        if not v.strip():
            return []
        return [int(x.strip()) for x in v.split(",") if x.strip()]
    return []


class Settings(BaseSettings):
    """Environment settings."""

    telegram_token: str = Field("", env="TELEGRAM_TOKEN")
    admin_ids: str = Field("", env="ADMIN_IDS")
    super_admin_ids: str = Field("", env="SUPER_ADMIN_IDS")
    monero_rpc_url: str = Field("", env="MONERO_RPC_URL")
    monero_rpc_user: str = Field("", env="MONERO_RPC_USER")
    monero_rpc_password: str = Field("", env="MONERO_RPC_PASSWORD")
    encryption_key: str = Field("", env="ENCRYPTION_KEY")
    totp_secret: str | None = Field(None, env="TOTP_SECRET")
    data_retention_days: int = Field(30, env="DATA_RETENTION_DAYS")
    default_commission_rate: float = Field(0.05, env="DEFAULT_COMMISSION_RATE")

    # Multi-currency blockchain API keys
    etherscan_api_key: str = Field("", env="ETHERSCAN_API_KEY")
    infura_project_id: str = Field("", env="INFURA_PROJECT_ID")
    blockcypher_api_key: str = Field("", env="BLOCKCYPHER_API_KEY")

    # Confirmation thresholds per currency
    btc_confirmation_threshold: int = Field(6, env="BTC_CONFIRMATION_THRESHOLD")
    eth_confirmation_threshold: int = Field(12, env="ETH_CONFIRMATION_THRESHOLD")
    xmr_confirmation_threshold: int = Field(10, env="XMR_CONFIRMATION_THRESHOLD")

    # Logging configuration
    log_level: str = Field("INFO", env="LOG_LEVEL")
    log_file: str | None = Field(None, env="LOG_FILE")

    # Production settings
    environment: str = Field("development", env="ENVIRONMENT")
    database_url: str = Field("sqlite:///db.sqlite3", env="DATABASE_URL")
    max_retries: int = Field(3, env="MAX_RETRIES")
    retry_delay: int = Field(5, env="RETRY_DELAY")

    # Health check
    health_check_enabled: bool = Field(True, env="HEALTH_CHECK_ENABLED")
    health_check_port: int = Field(8080, env="HEALTH_CHECK_PORT")

    @field_validator("encryption_key")
    @classmethod
    def validate_encryption_key(cls, v):
        if not v:
            return v
        try:
            decoded = base64.b64decode(v)
            if len(decoded) != 32:
                raise ValueError("Encryption key must be 32 bytes")
        except Exception:
            raise ValueError("Encryption key must be valid base64-encoded 32-byte key")
        return v

    @property
    def admin_ids_list(self) -> List[int]:
        """Get admin IDs as list."""
        return parse_ids(self.admin_ids)

    @property
    def super_admin_ids_list(self) -> List[int]:
        """Get super admin IDs as list."""
        return parse_ids(self.super_admin_ids)

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"


_settings: Settings | None = None

def get_settings() -> Settings:  # pragma: no cover
    global _settings
    if _settings is None:
        _settings = Settings()  # type: ignore[call-arg]
    return _settings
