"""Tests for main application module."""

import pytest
import signal
import sys
from unittest.mock import MagicMock, AsyncMock, patch, call

from bot.main import build_app, post_init, post_shutdown, handle_signal, main


class TestMain:
    """Test main application functionality."""

    @patch('bot.main.get_settings')
    @patch('bot.main.setup_logging')
    @patch('bot.main.Database')
    @patch('bot.main.VendorService')
    @patch('bot.main.CatalogService')
    @patch('bot.main.PaymentService')
    @patch('bot.main.OrderService')
    @patch('bot.main.ApplicationBuilder')
    def test_build_app(self, mock_app_builder, mock_orders, mock_payments, 
                       mock_catalog, mock_vendors, mock_db, mock_setup_logging, 
                       mock_settings):
        """Test application building."""
        # Setup mocks
        mock_settings.return_value.telegram_token = "test_token"
        mock_settings.return_value.log_level = "INFO"
        mock_settings.return_value.log_file = None
        mock_settings.return_value.environment = "test"
        mock_settings.return_value.database_url = "sqlite:///test.db"
        
        mock_app = MagicMock()
        mock_app.add_handler = MagicMock()
        mock_app.add_error_handler = MagicMock()
        mock_app.bot_data = {}
        
        mock_builder = MagicMock()
        mock_builder.token.return_value = mock_builder
        mock_builder.build.return_value = mock_app
        mock_app_builder.return_value = mock_builder
        
        # Call build_app
        app = build_app()
        
        # Verify setup
        mock_setup_logging.assert_called_once_with("INFO", None)
        mock_db.assert_called_once_with("sqlite:///test.db")
        
        # Verify services initialized
        mock_vendors.assert_called_once()
        mock_catalog.assert_called_once()
        mock_payments.assert_called_once()
        mock_orders.assert_called_once()
        
        # Verify bot built with token
        mock_builder.token.assert_called_once_with("test_token")
        
        # Verify handlers added (12 commands + 9 callbacks + 1 message handler = 22)
        assert mock_app.add_handler.call_count == 22
        mock_app.add_error_handler.assert_called_once()
        
        # Verify bot_data set
        assert "db" in app.bot_data
        assert "health_server" in app.bot_data

    @pytest.mark.asyncio
    async def test_post_init(self):
        """Test post initialization."""
        mock_app = MagicMock()
        mock_health_server = AsyncMock()
        mock_db = MagicMock()
        
        mock_app.bot_data = {
            "health_server": mock_health_server,
            "db": mock_db
        }
        
        with patch('bot.main.asyncio.create_task') as mock_create_task:
            await post_init(mock_app)
            
            # Verify health server started
            mock_health_server.start.assert_called_once()
            
            # Verify background tasks started
            mock_create_task.assert_called_once()

    @pytest.mark.asyncio
    async def test_post_shutdown(self):
        """Test post shutdown."""
        mock_app = MagicMock()
        mock_health_server = AsyncMock()
        
        mock_app.bot_data = {
            "health_server": mock_health_server
        }
        
        await post_shutdown(mock_app)
        
        # Verify health server stopped
        mock_health_server.stop.assert_called_once()

    def test_handle_signal(self):
        """Test signal handler."""
        with patch('sys.exit') as mock_exit:
            handle_signal(signal.SIGINT, None)
            mock_exit.assert_called_once_with(0)

    @patch('bot.main.signal.signal')
    @patch('bot.main.build_app')
    def test_main_success(self, mock_build_app, mock_signal):
        """Test main function successful execution."""
        mock_app = MagicMock()
        mock_app.run_polling = MagicMock()
        mock_build_app.return_value = mock_app
        
        main()
        
        # Verify signal handlers set
        mock_signal.assert_has_calls([
            call(signal.SIGINT, handle_signal),
            call(signal.SIGTERM, handle_signal)
        ])
        
        # Verify app built and callbacks set
        mock_build_app.assert_called_once()
        assert mock_app.post_init == post_init
        assert mock_app.post_shutdown == post_shutdown
        
        # Verify polling started
        mock_app.run_polling.assert_called_once_with(drop_pending_updates=True)

    @patch('bot.main.signal.signal')
    @patch('bot.main.build_app')
    @patch('sys.exit')
    def test_main_error(self, mock_exit, mock_build_app, mock_signal):
        """Test main function with error."""
        mock_app = MagicMock()
        mock_app.run_polling = MagicMock(side_effect=Exception("Test error"))
        mock_build_app.return_value = mock_app
        
        main()
        
        # Verify error handled
        mock_exit.assert_called_once_with(1)