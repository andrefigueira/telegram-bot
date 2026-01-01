"""Tests for bot manager module."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
import base64


class TestTenantBotWorker:
    """Tests for TenantBotWorker class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        db.get_tenant.return_value = MagicMock(shop_name="Test Shop")
        db.get_products.return_value = []
        return db

    @pytest.fixture
    def mock_swap_service(self):
        """Create mock swap service."""
        return AsyncMock()

    @pytest.fixture
    def worker(self, mock_db, mock_swap_service):
        """Create a TenantBotWorker instance."""
        from bot.services.bot_manager import TenantBotWorker
        return TenantBotWorker(
            tenant_id="test-tenant",
            bot_token="123:ABC",
            tenant_xmr_address="4TestAddr",
            db=mock_db,
            swap_service=mock_swap_service,
            encryption_key="test_key"
        )

    def test_init(self, worker):
        """Test worker initialization."""
        assert worker.tenant_id == "test-tenant"
        assert worker.bot_token == "123:ABC"
        assert worker.running is False
        assert worker.application is None

    @pytest.mark.asyncio
    async def test_start_success(self, worker):
        """Test successful bot start."""
        mock_app = AsyncMock()
        mock_app.initialize = AsyncMock()
        mock_app.start = AsyncMock()
        mock_app.updater = AsyncMock()
        mock_app.updater.start_polling = AsyncMock()
        mock_app.add_handler = MagicMock()

        with patch("bot.services.bot_manager.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.return_value = mock_app

            await worker.start()

            assert worker.running is True
            assert worker.application is mock_app
            mock_app.initialize.assert_called_once()
            mock_app.start.assert_called_once()
            mock_app.updater.start_polling.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_already_running(self, worker):
        """Test start when already running."""
        worker.running = True
        await worker.start()
        assert worker.application is None

    @pytest.mark.asyncio
    async def test_start_failure(self, worker):
        """Test start failure."""
        with patch("bot.services.bot_manager.ApplicationBuilder") as mock_builder:
            mock_builder.return_value.token.return_value.build.side_effect = Exception("Failed")

            with pytest.raises(Exception):
                await worker.start()

            assert worker.running is False

    @pytest.mark.asyncio
    async def test_stop_success(self, worker):
        """Test successful bot stop."""
        mock_app = AsyncMock()
        mock_app.updater = AsyncMock()
        worker.application = mock_app
        worker.running = True

        await worker.stop()

        assert worker.running is False
        mock_app.updater.stop.assert_called_once()
        mock_app.stop.assert_called_once()
        mock_app.shutdown.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, worker):
        """Test stop when not running."""
        worker.running = False
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_no_application(self, worker):
        """Test stop with no application."""
        worker.running = True
        worker.application = None
        await worker.stop()

    @pytest.mark.asyncio
    async def test_stop_error(self, worker):
        """Test stop with error."""
        mock_app = AsyncMock()
        mock_app.updater = AsyncMock()
        mock_app.updater.stop.side_effect = Exception("Stop failed")
        worker.application = mock_app
        worker.running = True

        await worker.stop()
        assert worker.running is True

    def test_register_handlers(self, worker):
        """Test handler registration."""
        mock_app = MagicMock()
        worker.application = mock_app

        with patch("bot.services.multicrypto_orders.MultiCryptoOrderService"):
            worker._register_handlers()

        assert mock_app.add_handler.call_count == 5

    @pytest.mark.asyncio
    async def test_start_handler(self, worker, mock_db):
        """Test /start command handler."""
        handler = worker._make_start_handler()
        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        await handler(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Test Shop" in call_args
        assert "/list" in call_args

    @pytest.mark.asyncio
    async def test_list_handler_empty(self, worker, mock_db):
        """Test /list command with no products."""
        mock_db.get_products.return_value = []
        handler = worker._make_list_handler()

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        await handler(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_with("No products available.")

    @pytest.mark.asyncio
    async def test_list_handler_with_products(self, worker, mock_db):
        """Test /list command with products."""
        mock_db.get_products.return_value = [
            MagicMock(id=1, name="Product 1", price_xmr=0.5, inventory=10, description="Test"),
            MagicMock(id=2, name="Product 2", price_xmr=1.0, inventory=0, description=None),
        ]
        handler = worker._make_list_handler()

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()

        await handler(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Product 1" in call_args
        assert "Product 2" in call_args
        assert "in stock" in call_args
        assert "Out of stock" in call_args

    @pytest.mark.asyncio
    async def test_order_handler_missing_args(self, worker):
        """Test /order command with missing arguments."""
        mock_order_service = AsyncMock()
        handler = worker._make_order_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["1"]

        await handler(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        assert "Usage:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_order_handler_success(self, worker):
        """Test successful /order command."""
        mock_order_service = AsyncMock()
        mock_order_service.create_order.return_value = {
            "order_id": 123,
            "message": "Send 0.5 XMR to address"
        }
        handler = worker._make_order_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_context = MagicMock()
        mock_context.args = ["1", "2", "123", "Main", "St"]
        mock_context.user_data = {}

        await handler(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Order #123" in call_args

    @pytest.mark.asyncio
    async def test_order_handler_value_error(self, worker):
        """Test /order command with ValueError."""
        mock_order_service = AsyncMock()
        mock_order_service.create_order.side_effect = ValueError("Product not found")
        handler = worker._make_order_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_context = MagicMock()
        mock_context.args = ["999", "1", "Address"]
        mock_context.user_data = {}

        await handler(mock_update, mock_context)

        assert "Error:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_order_handler_exception(self, worker):
        """Test /order command with general exception."""
        mock_order_service = AsyncMock()
        mock_order_service.create_order.side_effect = Exception("Database error")
        handler = worker._make_order_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_update.effective_user.id = 12345
        mock_context = MagicMock()
        mock_context.args = ["1", "1", "Address"]
        mock_context.user_data = {}

        await handler(mock_update, mock_context)

        assert "error occurred" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_status_handler_missing_args(self, worker):
        """Test /status command with missing arguments."""
        mock_order_service = AsyncMock()
        handler = worker._make_status_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = []

        await handler(mock_update, mock_context)

        assert "Usage:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_status_handler_success(self, worker):
        """Test successful /status command."""
        mock_order_service = AsyncMock()
        mock_order_service.check_order_payment.return_value = {
            "state": "PAID",
            "payment_coin": "btc",
            "swap_status": "completed",
            "message": "Payment confirmed"
        }
        handler = worker._make_status_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["123"]

        await handler(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Order #123" in call_args
        assert "PAID" in call_args
        assert "BTC" in call_args
        assert "completed" in call_args

    @pytest.mark.asyncio
    async def test_status_handler_no_swap(self, worker):
        """Test /status command without swap status."""
        mock_order_service = AsyncMock()
        mock_order_service.check_order_payment.return_value = {
            "state": "PENDING",
            "payment_coin": "xmr",
            "swap_status": None,
            "message": None
        }
        handler = worker._make_status_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["123"]

        await handler(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "PENDING" in call_args
        assert "Swap" not in call_args

    @pytest.mark.asyncio
    async def test_status_handler_error(self, worker):
        """Test /status command with error."""
        mock_order_service = AsyncMock()
        mock_order_service.check_order_payment.side_effect = ValueError("Order not found")
        handler = worker._make_status_handler(mock_order_service)

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["999"]

        await handler(mock_update, mock_context)

        assert "Error:" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_pay_handler_no_args(self, worker):
        """Test /pay command with no arguments."""
        handler = worker._make_pay_handler()

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = []
        mock_context.user_data = {"payment_coin": "btc"}

        await handler(mock_update, mock_context)

        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "BTC" in call_args
        assert "Supported:" in call_args

    @pytest.mark.asyncio
    async def test_pay_handler_set_coin(self, worker):
        """Test /pay command setting coin."""
        handler = worker._make_pay_handler()

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["eth"]
        mock_context.user_data = {}

        await handler(mock_update, mock_context)

        assert mock_context.user_data["payment_coin"] == "eth"
        assert "ETH" in mock_update.message.reply_text.call_args[0][0]

    @pytest.mark.asyncio
    async def test_pay_handler_unsupported(self, worker):
        """Test /pay command with unsupported coin."""
        handler = worker._make_pay_handler()

        mock_update = MagicMock()
        mock_update.message.reply_text = AsyncMock()
        mock_context = MagicMock()
        mock_context.args = ["doge"]
        mock_context.user_data = {}

        await handler(mock_update, mock_context)

        assert "Unsupported" in mock_update.message.reply_text.call_args[0][0]


class TestBotManager:
    """Tests for BotManager class."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        db = MagicMock()
        return db

    @pytest.fixture
    def mock_swap_service(self):
        """Create mock swap service."""
        return AsyncMock()

    @pytest.fixture
    def encryption_key(self):
        """Create test encryption key."""
        return base64.b64encode(b"x" * 32).decode()

    @pytest.fixture
    def manager(self, mock_db, encryption_key, mock_swap_service):
        """Create BotManager instance."""
        from bot.services.bot_manager import BotManager
        return BotManager(
            db=mock_db,
            platform_encryption_key=encryption_key,
            swap_service=mock_swap_service
        )

    def test_init(self, manager):
        """Test manager initialization."""
        assert manager.active_bots == {}

    @pytest.mark.asyncio
    async def test_start_bot_already_running(self, manager):
        """Test start_bot when already running."""
        manager.active_bots["test-tenant"] = MagicMock()
        result = await manager.start_bot("test-tenant")
        assert result is True

    @pytest.mark.asyncio
    async def test_start_bot_tenant_not_found(self, manager, mock_db):
        """Test start_bot when tenant not found."""
        mock_db.get_tenant.return_value = None
        result = await manager.start_bot("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_not_active(self, manager, mock_db):
        """Test start_bot when bot not active."""
        mock_db.get_tenant.return_value = MagicMock(bot_active=False)
        result = await manager.start_bot("test-tenant")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_no_token(self, manager, mock_db):
        """Test start_bot when no token."""
        mock_db.get_tenant.return_value = MagicMock(
            bot_active=True,
            bot_token_encrypted=None
        )
        result = await manager.start_bot("test-tenant")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_no_wallet(self, manager, mock_db):
        """Test start_bot when no wallet."""
        mock_db.get_tenant.return_value = MagicMock(
            bot_active=True,
            bot_token_encrypted="encrypted",
            monero_wallet_address=None
        )
        result = await manager.start_bot("test-tenant")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_overdue_invoices(self, manager, mock_db):
        """Test start_bot with overdue invoices."""
        mock_db.get_tenant.return_value = MagicMock(
            bot_active=True,
            bot_token_encrypted="encrypted",
            monero_wallet_address="4TestAddr"
        )
        mock_db.get_overdue_invoices.return_value = [MagicMock()]
        result = await manager.start_bot("test-tenant")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_decrypt_failure(self, manager, mock_db):
        """Test start_bot with decrypt failure."""
        mock_db.get_tenant.return_value = MagicMock(
            bot_active=True,
            bot_token_encrypted="invalid",
            monero_wallet_address="4TestAddr"
        )
        mock_db.get_overdue_invoices.return_value = []

        result = await manager.start_bot("test-tenant")
        assert result is False

    @pytest.mark.asyncio
    async def test_start_bot_success(self, manager, mock_db, encryption_key):
        """Test successful start_bot."""
        from nacl.secret import SecretBox

        key = base64.b64decode(encryption_key)
        box = SecretBox(key)
        encrypted_token = base64.b64encode(box.encrypt(b"123:ABC")).decode()

        mock_db.get_tenant.return_value = MagicMock(
            id="test-tenant",
            bot_active=True,
            bot_token_encrypted=encrypted_token,
            monero_wallet_address="4TestAddr",
            encryption_key="tenant_key"
        )
        mock_db.get_overdue_invoices.return_value = []

        with patch("bot.services.bot_manager.TenantBotWorker") as MockWorker:
            mock_worker = AsyncMock()
            MockWorker.return_value = mock_worker

            result = await manager.start_bot("test-tenant")

            assert result is True
            assert "test-tenant" in manager.active_bots
            mock_worker.start.assert_called_once()
            mock_db.log_action.assert_called_with(
                action="bot_started",
                tenant_id="test-tenant"
            )

    @pytest.mark.asyncio
    async def test_start_bot_worker_exception(self, manager, mock_db, encryption_key):
        """Test start_bot with worker exception."""
        from nacl.secret import SecretBox

        key = base64.b64decode(encryption_key)
        box = SecretBox(key)
        encrypted_token = base64.b64encode(box.encrypt(b"123:ABC")).decode()

        mock_db.get_tenant.return_value = MagicMock(
            id="test-tenant",
            bot_active=True,
            bot_token_encrypted=encrypted_token,
            monero_wallet_address="4TestAddr",
            encryption_key="tenant_key"
        )
        mock_db.get_overdue_invoices.return_value = []

        with patch("bot.services.bot_manager.TenantBotWorker") as MockWorker:
            mock_worker = AsyncMock()
            mock_worker.start.side_effect = Exception("Start failed")
            MockWorker.return_value = mock_worker

            result = await manager.start_bot("test-tenant")

            assert result is False
            assert "test-tenant" not in manager.active_bots

    @pytest.mark.asyncio
    async def test_stop_bot_not_running(self, manager):
        """Test stop_bot when not running."""
        result = await manager.stop_bot("unknown")
        assert result is False

    @pytest.mark.asyncio
    async def test_stop_bot_success(self, manager, mock_db):
        """Test successful stop_bot."""
        mock_worker = AsyncMock()
        manager.active_bots["test-tenant"] = mock_worker

        result = await manager.stop_bot("test-tenant")

        assert result is True
        assert "test-tenant" not in manager.active_bots
        mock_worker.stop.assert_called_once()
        mock_db.log_action.assert_called_with(
            action="bot_stopped",
            tenant_id="test-tenant"
        )

    @pytest.mark.asyncio
    async def test_stop_bot_error(self, manager, mock_db):
        """Test stop_bot with error."""
        mock_worker = AsyncMock()
        mock_worker.stop.side_effect = Exception("Stop failed")
        manager.active_bots["test-tenant"] = mock_worker

        result = await manager.stop_bot("test-tenant")

        assert result is False

    @pytest.mark.asyncio
    async def test_restart_bot(self, manager):
        """Test restart_bot."""
        manager.stop_bot = AsyncMock()
        manager.start_bot = AsyncMock(return_value=True)

        result = await manager.restart_bot("test-tenant")

        assert result is True
        manager.stop_bot.assert_called_once_with("test-tenant")
        manager.start_bot.assert_called_once_with("test-tenant")

    @pytest.mark.asyncio
    async def test_start_all_bots(self, manager, mock_db):
        """Test start_all_bots."""
        mock_db.get_active_tenants.return_value = [
            MagicMock(id="tenant-1"),
            MagicMock(id="tenant-2"),
            MagicMock(id="tenant-3"),
        ]

        with patch.object(manager, "start_bot", new=AsyncMock(side_effect=[True, False, True])):
            result = await manager.start_all_bots()

        assert result == {"started": 2, "failed": 1}

    @pytest.mark.asyncio
    async def test_stop_all_bots(self, manager):
        """Test stop_all_bots."""
        manager.active_bots = {
            "tenant-1": AsyncMock(),
            "tenant-2": AsyncMock(),
        }

        mock_stop = AsyncMock()
        with patch.object(manager, "stop_bot", mock_stop):
            await manager.stop_all_bots()

        assert mock_stop.call_count == 2

    def test_get_running_bots(self, manager):
        """Test get_running_bots."""
        manager.active_bots = {
            "tenant-1": MagicMock(),
            "tenant-2": MagicMock(),
        }

        result = manager.get_running_bots()

        assert set(result) == {"tenant-1", "tenant-2"}

    def test_is_bot_running_true(self, manager):
        """Test is_bot_running when running."""
        manager.active_bots["test-tenant"] = MagicMock()
        assert manager.is_bot_running("test-tenant") is True

    def test_is_bot_running_false(self, manager):
        """Test is_bot_running when not running."""
        assert manager.is_bot_running("unknown") is False

    def test_decrypt_token_success(self, manager, encryption_key):
        """Test successful token decryption."""
        from nacl.secret import SecretBox

        key = base64.b64decode(encryption_key)
        box = SecretBox(key)
        encrypted = base64.b64encode(box.encrypt(b"test_token")).decode()

        result = manager._decrypt_token(encrypted)

        assert result == "test_token"

    def test_decrypt_token_failure(self, manager):
        """Test token decryption failure."""
        result = manager._decrypt_token("invalid_encrypted_data")
        assert result is None

    @pytest.mark.asyncio
    async def test_health_check(self, manager):
        """Test health_check."""
        manager.active_bots = {
            "tenant-1": MagicMock(),
            "tenant-2": MagicMock(),
        }

        result = await manager.health_check()

        assert result["active_bots"] == 2
        assert set(result["tenant_ids"]) == {"tenant-1", "tenant-2"}
        assert "timestamp" in result
