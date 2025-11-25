"""Tests for configuration module."""

import pytest
import base64
import os
from unittest.mock import patch

from bot.config import Settings, get_settings, parse_ids


class TestParseIds:
    """Test parse_ids helper function."""

    def test_parse_ids_string(self):
        """Test parsing comma-separated string."""
        assert parse_ids("123,456,789") == [123, 456, 789]

    def test_parse_ids_single(self):
        """Test parsing single value."""
        assert parse_ids("123") == [123]

    def test_parse_ids_empty_string(self):
        """Test parsing empty string."""
        assert parse_ids("") == []

    def test_parse_ids_whitespace(self):
        """Test parsing whitespace string."""
        assert parse_ids("   ") == []

    def test_parse_ids_list(self):
        """Test passing list through."""
        assert parse_ids([1, 2, 3]) == [1, 2, 3]

    def test_parse_ids_with_spaces(self):
        """Test parsing with spaces around values."""
        assert parse_ids(" 123 , 456 , 789 ") == [123, 456, 789]

    def test_parse_ids_none(self):
        """Test parsing None."""
        assert parse_ids(None) == []


class TestConfig:
    """Test configuration functionality."""

    def test_settings_defaults(self):
        """Test Settings with default values."""
        settings = Settings()

        assert settings.telegram_token == ""
        assert settings.admin_ids == ""
        assert settings.super_admin_ids == ""
        assert settings.admin_ids_list == []
        assert settings.super_admin_ids_list == []
        assert settings.monero_rpc_url == ""
        assert settings.encryption_key == ""
        assert settings.totp_secret is None
        assert settings.data_retention_days == 30
        assert settings.default_commission_rate == 0.05
        assert settings.log_level == "INFO"
        assert settings.log_file is None
        assert settings.environment == "development"
        assert settings.database_url == "sqlite:///db.sqlite3"
        assert settings.max_retries == 3
        assert settings.retry_delay == 5
        assert settings.health_check_enabled is True
        assert settings.health_check_port == 8080

    def test_settings_from_env(self):
        """Test Settings loading from environment variables."""
        env_vars = {
            "TELEGRAM_TOKEN": "test_token",
            "ADMIN_IDS": "123,456",
            "SUPER_ADMIN_IDS": "789",
            "MONERO_RPC_URL": "http://localhost:18082",
            "ENCRYPTION_KEY": base64.b64encode(os.urandom(32)).decode(),
            "TOTP_SECRET": "JBSWY3DPEHPK3PXP",
            "DATA_RETENTION_DAYS": "60",
            "DEFAULT_COMMISSION_RATE": "0.10",
            "LOG_LEVEL": "DEBUG",
            "LOG_FILE": "/var/log/bot.log",
            "ENVIRONMENT": "production",
            "DATABASE_URL": "postgresql://user:pass@host/db",
            "MAX_RETRIES": "5",
            "RETRY_DELAY": "10",
            "HEALTH_CHECK_ENABLED": "false",
            "HEALTH_CHECK_PORT": "9090"
        }

        with patch.dict(os.environ, env_vars):
            settings = Settings()

            assert settings.telegram_token == "test_token"
            assert settings.admin_ids_list == [123, 456]
            assert settings.super_admin_ids_list == [789]
            assert settings.monero_rpc_url == "http://localhost:18082"
            assert settings.totp_secret == "JBSWY3DPEHPK3PXP"
            assert settings.data_retention_days == 60
            assert settings.default_commission_rate == 0.10
            assert settings.log_level == "DEBUG"
            assert settings.log_file == "/var/log/bot.log"
            assert settings.environment == "production"
            assert settings.database_url == "postgresql://user:pass@host/db"
            assert settings.max_retries == 5
            assert settings.retry_delay == 10
            assert settings.health_check_enabled is False
            assert settings.health_check_port == 9090

    def test_encryption_key_validation_valid(self):
        """Test encryption key validation with valid key."""
        valid_key = base64.b64encode(os.urandom(32)).decode()

        with patch.dict(os.environ, {"ENCRYPTION_KEY": valid_key}):
            settings = Settings()
            assert settings.encryption_key == valid_key

    def test_encryption_key_validation_empty(self):
        """Test encryption key validation with empty key."""
        settings = Settings(encryption_key="")
        assert settings.encryption_key == ""

    def test_encryption_key_validation_invalid_base64(self):
        """Test encryption key validation with invalid base64."""
        with pytest.raises(ValueError, match="valid base64-encoded"):
            Settings(encryption_key="not-base64!")

    def test_encryption_key_validation_wrong_length(self):
        """Test encryption key validation with wrong key length."""
        invalid_key = base64.b64encode(os.urandom(16)).decode()

        with pytest.raises(ValueError, match="32-byte"):
            Settings(encryption_key=invalid_key)

    def test_get_settings_singleton(self):
        """Test get_settings returns singleton."""
        with patch('bot.config._settings', None):
            settings1 = get_settings()
            settings2 = get_settings()

            assert settings1 is settings2

    def test_admin_ids_parsing(self):
        """Test parsing of comma-separated admin IDs."""
        with patch.dict(os.environ, {"ADMIN_IDS": "123,456,789"}):
            settings = Settings()
            assert settings.admin_ids_list == [123, 456, 789]

    def test_admin_ids_single_value(self):
        """Test parsing of single admin ID."""
        with patch.dict(os.environ, {"ADMIN_IDS": "123"}):
            settings = Settings()
            assert settings.admin_ids_list == [123]

    def test_admin_ids_empty(self):
        """Test empty admin IDs."""
        with patch.dict(os.environ, {"ADMIN_IDS": ""}):
            settings = Settings()
            assert settings.admin_ids_list == []
