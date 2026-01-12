"""Tests for payment service module."""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal
import sys

from bot.services.payments import MoneroPaymentService, PaymentService
from bot.error_handler import RetryableError

# Check if monero module is available
monero_available = "monero" in sys.modules or any(
    spec is not None for spec in [__import__('importlib.util').util.find_spec('monero')]
    if spec is not None
)
try:
    import monero
    monero_available = True
except ImportError:
    monero_available = False


class TestMoneroPaymentService:
    """Test Monero payment service functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('bot.services.payments.get_settings') as mock:
            settings = MagicMock()
            settings.monero_rpc_url = "http://localhost:18082"
            settings.monero_rpc_user = "user"
            settings.monero_rpc_password = "pass"
            settings.environment = "production"
            mock.return_value = settings
            yield settings

    @pytest.fixture
    def payment_service(self, mock_settings):
        """Create payment service instance."""
        return MoneroPaymentService()

    def test_create_address_success(self, payment_service, mock_settings):
        """Test successful address creation."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()
            mock_wallet.make_integrated_address.return_value = "4A1234567890abcdef"
            mock_get_wallet.return_value = mock_wallet

            address, payment_id = payment_service.create_address()

            assert address == "4A1234567890abcdef"
            assert len(payment_id) == 16  # 16 char payment ID for Monero
            mock_wallet.make_integrated_address.assert_called_once()

    def test_create_address_wallet_error(self, payment_service, mock_settings):
        """Test address creation with wallet error falls back to vendor wallet."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_get_wallet.side_effect = Exception("Connection failed")

            # Without vendor wallet in production, should raise
            with pytest.raises(RetryableError, match="Failed to create payment address"):
                payment_service.create_address()

    def test_create_address_with_vendor_wallet(self, payment_service, mock_settings):
        """Test address creation falls back to vendor wallet."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_get_wallet.return_value = None

            address, payment_id = payment_service.create_address(vendor_wallet="vendor123wallet")

            assert address == "vendor123wallet"
            assert len(payment_id) == 16

    def test_create_address_development_fallback(self, mock_settings):
        """Test address creation in development mode."""
        mock_settings.environment = "development"
        mock_settings.monero_rpc_url = ""

        service = MoneroPaymentService()
        address, payment_id = service.create_address()

        assert address.startswith("4")
        assert len(payment_id) == 16

    def test_create_address_production_no_wallet_no_vendor(self, mock_settings):
        """Test address creation in production without wallet or vendor."""
        mock_settings.monero_rpc_url = ""

        service = MoneroPaymentService()
        with pytest.raises(RetryableError, match="Failed to create payment address"):
            service.create_address()

    def test_check_paid_success(self, payment_service, mock_settings):
        """Test successful payment check."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()

            # Mock transfer object
            mock_transfer = MagicMock()
            mock_transfer.amount = Decimal("1.5")

            mock_wallet.incoming.return_value = [mock_transfer]
            mock_get_wallet.return_value = mock_wallet

            result = payment_service.check_paid("payment123")

            assert result is True
            mock_wallet.incoming.assert_called_once_with(payment_id="payment123")

    def test_check_paid_no_payment(self, payment_service, mock_settings):
        """Test payment check with no payment received."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()
            mock_wallet.incoming.return_value = []
            mock_get_wallet.return_value = mock_wallet

            result = payment_service.check_paid("payment123")

            assert result is False

    def test_check_paid_insufficient_amount(self, payment_service, mock_settings):
        """Test payment check with insufficient amount."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()

            # Mock transfer with insufficient amount
            mock_transfer = MagicMock()
            mock_transfer.amount = Decimal("0.5")

            mock_wallet.incoming.return_value = [mock_transfer]
            mock_get_wallet.return_value = mock_wallet

            result = payment_service.check_paid("payment123", expected_amount=Decimal("1.0"))

            assert result is False

    def test_check_paid_multiple_transfers(self, payment_service, mock_settings):
        """Test payment check with multiple transfers."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()

            # Mock multiple transfers
            transfer1 = MagicMock()
            transfer1.amount = Decimal("0.5")
            transfer2 = MagicMock()
            transfer2.amount = Decimal("0.6")

            mock_wallet.incoming.return_value = [transfer1, transfer2]
            mock_get_wallet.return_value = mock_wallet

            result = payment_service.check_paid("payment123", expected_amount=Decimal("1.0"))

            assert result is True  # 0.5 + 0.6 = 1.1 >= 1.0

    def test_check_paid_development_mode(self, mock_settings):
        """Test payment check in development mode without RPC."""
        mock_settings.environment = "development"
        mock_settings.monero_rpc_url = ""

        service = MoneroPaymentService()
        result = service.check_paid("payment123")

        assert result is False  # Returns False in development mode

    def test_check_paid_no_rpc_configured(self, mock_settings):
        """Test payment check when RPC not configured."""
        mock_settings.environment = "production"
        mock_settings.monero_rpc_url = ""

        service = MoneroPaymentService()
        result = service.check_paid("payment123")

        # Returns False when RPC not configured (not development)
        assert result is False

    def test_check_paid_error_in_production(self, payment_service, mock_settings):
        """Test payment check with error in production raises."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_get_wallet.side_effect = Exception("Connection failed")

            with pytest.raises(RetryableError, match="Failed to check payment status"):
                payment_service.check_paid("payment123")

    def test_get_balance_success(self, payment_service, mock_settings):
        """Test successful balance retrieval."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_wallet = MagicMock()
            mock_wallet.balance.return_value = Decimal("10.5")
            mock_get_wallet.return_value = mock_wallet

            balance = payment_service.get_balance()

            assert balance == Decimal("10.5")
            mock_wallet.balance.assert_called_once()

    def test_get_balance_error(self, payment_service, mock_settings):
        """Test balance retrieval with error returns zero."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_get_wallet.side_effect = Exception("Connection failed")

            balance = payment_service.get_balance()

            assert balance == Decimal("0")

    def test_get_balance_no_wallet(self, payment_service, mock_settings):
        """Test balance retrieval when wallet not available."""
        with patch.object(payment_service, '_get_wallet') as mock_get_wallet:
            mock_get_wallet.return_value = None

            balance = payment_service.get_balance()

            assert balance == Decimal("0")

    @pytest.mark.skipif(not monero_available, reason="monero module not installed")
    def test_get_wallet_caching(self, mock_settings):
        """Test wallet connection caching."""
        with patch('bot.services.payments.get_settings') as settings_mock:
            settings_mock.return_value = mock_settings

            service = MoneroPaymentService()

            with patch('monero.wallet.Wallet') as mock_wallet_class:
                with patch('monero.backends.jsonrpc.JSONRPCWallet') as mock_backend_class:
                    mock_wallet = MagicMock()
                    mock_wallet_class.return_value = mock_wallet

                    # First call
                    wallet1 = service._get_wallet()
                    # Second call should return cached instance
                    wallet2 = service._get_wallet()

                    assert wallet1 is wallet2
                    mock_backend_class.assert_called_once()  # Backend only created once

    def test_get_wallet_no_rpc_url(self, mock_settings):
        """Test _get_wallet returns None when no RPC URL."""
        mock_settings.monero_rpc_url = ""

        service = MoneroPaymentService()
        wallet = service._get_wallet()

        assert wallet is None

    @pytest.mark.skipif(not monero_available, reason="monero module not installed")
    def test_get_wallet_connection_failure(self, mock_settings):
        """Test _get_wallet raises RetryableError on connection failure."""
        with patch('monero.backends.jsonrpc.JSONRPCWallet') as mock_backend_class:
            mock_backend_class.side_effect = Exception("Connection refused")

            service = MoneroPaymentService()

            with pytest.raises(RetryableError, match="Monero wallet connection failed"):
                service._get_wallet()

    def test_payment_service_is_subclass(self):
        """Test PaymentService is subclass of MoneroPaymentService."""
        assert issubclass(PaymentService, MoneroPaymentService)

    def test_payment_service_instance(self):
        """Test PaymentService can be instantiated."""
        with patch('bot.services.payments.get_settings') as mock:
            settings = MagicMock()
            settings.monero_rpc_url = ""
            settings.environment = "development"
            mock.return_value = settings

            service = PaymentService()
            assert isinstance(service, MoneroPaymentService)
