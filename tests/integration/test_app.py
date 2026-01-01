from bot.main import build_app
from bot.config import Settings
import base64, os
import telegram.ext
import telegram.ext._extbot


def test_build_app(monkeypatch) -> None:
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
        monero_rpc_url="url",
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)
    monkeypatch.setattr(telegram.ext._extbot.ExtBot, "__init__", lambda self, *a, **k: None)
    app = build_app()
    assert app is not None
