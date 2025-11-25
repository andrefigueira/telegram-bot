"""Tests for payment service module."""

import pytest
from unittest.mock import MagicMock, patch
from decimal import Decimal

from bot.services.payments import MoneroPaymentService, PaymentService
from bot.error_handler import RetryableError


class TestMoneroPaymentService:
    """Test Monero payment service functionality."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('bot.services.payments.get_settings') as mock:
            settings = MagicMock()
            settings.monero_rpc_url = "http://localhost:18082"
            settings.environment = "production"
            mock.return_value = settings
            yield settings

    @pytest.fixture
    def payment_service(self, mock_settings):
        """Create payment service instance."""
        return MoneroPaymentService()

    def test_create_address_success(self, payment_service, mock_settings):
        """Test successful address creation."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            mock_wallet.make_integrated_address.return_value = "4A1234567890abcdef"
            mock_wallet_class.return_value = mock_wallet
            
            address, payment_id = payment_service.create_address()
            
            assert address == "4A1234567890abcdef"
            assert len(payment_id) == 32  # UUID hex length
            mock_wallet.make_integrated_address.assert_called_once()

    def test_create_address_wallet_error(self, payment_service, mock_settings):
        """Test address creation with wallet error."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(RetryableError, match="Monero wallet connection failed"):
                payment_service.create_address()

    def test_create_address_development_fallback(self, payment_service, mock_settings):
        """Test address creation in development mode."""
        mock_settings.environment = "development"
        mock_settings.monero_rpc_url = ""
        
        address, payment_id = payment_service.create_address()
        
        assert address.startswith("4A")
        assert len(payment_id) == 32

    def test_create_address_production_no_wallet(self, payment_service, mock_settings):
        """Test address creation in production without wallet."""
        mock_settings.monero_rpc_url = ""
        
        with pytest.raises(RetryableError, match="Failed to create payment address"):
            payment_service.create_address()

    def test_check_paid_success(self, payment_service, mock_settings):
        """Test successful payment check."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            
            # Mock transfer object
            mock_transfer = MagicMock()
            mock_transfer.amount = Decimal("1.5")
            
            mock_wallet.incoming.return_value = [mock_transfer]
            mock_wallet_class.return_value = mock_wallet
            
            result = payment_service.check_paid("payment123")
            
            assert result is True
            mock_wallet.incoming.assert_called_once_with(payment_id="payment123")

    def test_check_paid_no_payment(self, payment_service, mock_settings):
        """Test payment check with no payment received."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            mock_wallet.incoming.return_value = []
            mock_wallet_class.return_value = mock_wallet
            
            result = payment_service.check_paid("payment123")
            
            assert result is False

    def test_check_paid_insufficient_amount(self, payment_service, mock_settings):
        """Test payment check with insufficient amount."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            
            # Mock transfer with insufficient amount
            mock_transfer = MagicMock()
            mock_transfer.amount = Decimal("0.5")
            
            mock_wallet.incoming.return_value = [mock_transfer]
            mock_wallet_class.return_value = mock_wallet
            
            result = payment_service.check_paid("payment123", expected_amount=Decimal("1.0"))
            
            assert result is False

    def test_check_paid_multiple_transfers(self, payment_service, mock_settings):
        """Test payment check with multiple transfers."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            
            # Mock multiple transfers
            transfer1 = MagicMock()
            transfer1.amount = Decimal("0.5")
            transfer2 = MagicMock()
            transfer2.amount = Decimal("0.6")
            
            mock_wallet.incoming.return_value = [transfer1, transfer2]
            mock_wallet_class.return_value = mock_wallet
            
            result = payment_service.check_paid("payment123", expected_amount=Decimal("1.0"))
            
            assert result is True  # 0.5 + 0.6 = 1.1 >= 1.0

    def test_check_paid_development_mode(self, payment_service, mock_settings):
        """Test payment check in development mode."""
        mock_settings.environment = "development"
        mock_settings.monero_rpc_url = ""
        
        result = payment_service.check_paid("payment123")
        
        assert result is True  # Always returns True in development

    def test_check_paid_error(self, payment_service, mock_settings):
        """Test payment check with error."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet_class.side_effect = Exception("Connection failed")
            
            with pytest.raises(RetryableError, match="Failed to check payment status"):
                payment_service.check_paid("payment123")

    def test_get_balance_success(self, payment_service, mock_settings):
        """Test successful balance retrieval."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            mock_wallet.balance.return_value = Decimal("10.5")
            mock_wallet_class.return_value = mock_wallet
            
            balance = payment_service.get_balance()
            
            assert balance == Decimal("10.5")
            mock_wallet.balance.assert_called_once()

    def test_get_balance_error(self, payment_service, mock_settings):
        """Test balance retrieval with error."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet_class.side_effect = Exception("Connection failed")
            
            balance = payment_service.get_balance()
            
            assert balance == Decimal("0")

    def test_get_wallet_caching(self, payment_service, mock_settings):
        """Test wallet connection caching."""
        with patch('bot.services.payments.Wallet') as mock_wallet_class:
            mock_wallet = MagicMock()
            mock_wallet_class.return_value = mock_wallet
            
            # First call
            wallet1 = payment_service._get_wallet()
            # Second call should return cached instance
            wallet2 = payment_service._get_wallet()
            
            assert wallet1 is wallet2
            mock_wallet_class.assert_called_once()  # Only called once

    def test_payment_service_alias(self):
        """Test PaymentService is alias for MoneroPaymentService."""
        assert PaymentService is MoneroPaymentService