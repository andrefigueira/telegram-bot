"""Pytest configuration and fixtures."""

import sys
import os
from pathlib import Path
import pytest
import shutil

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Environment variables that affect Settings
SETTINGS_ENV_VARS = [
    "TELEGRAM_TOKEN",
    "ADMIN_IDS",
    "SUPER_ADMIN_IDS",
    "MONERO_RPC_URL",
    "ENCRYPTION_KEY",
    "TOTP_SECRET",
    "DATA_RETENTION_DAYS",
    "DEFAULT_COMMISSION_RATE",
    "LOG_LEVEL",
    "LOG_FILE",
    "ENVIRONMENT",
    "DATABASE_URL",
    "MAX_RETRIES",
    "RETRY_DELAY",
    "HEALTH_CHECK_ENABLED",
    "HEALTH_CHECK_PORT",
]

# Path to project root
PROJECT_ROOT = Path(__file__).resolve().parents[1]
ENV_FILE = PROJECT_ROOT / ".env"
ENV_BACKUP = PROJECT_ROOT / ".env.test_backup"


@pytest.fixture(autouse=True)
def clean_env():
    """Clear settings-related env vars and reset singleton before each test."""
    # Store original values
    original = {k: os.environ.get(k) for k in SETTINGS_ENV_VARS}

    # Clear env vars
    for key in SETTINGS_ENV_VARS:
        os.environ.pop(key, None)

    # Temporarily rename .env file if it exists
    env_existed = ENV_FILE.exists()
    if env_existed:
        shutil.move(ENV_FILE, ENV_BACKUP)

    # Reset settings singleton
    import bot.config
    bot.config._settings = None

    yield

    # Restore .env file
    if env_existed and ENV_BACKUP.exists():
        shutil.move(ENV_BACKUP, ENV_FILE)

    # Restore original env values
    for key, value in original.items():
        if value is not None:
            os.environ[key] = value
        else:
            os.environ.pop(key, None)

    # Reset singleton again
    bot.config._settings = None
