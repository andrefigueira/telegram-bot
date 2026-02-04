"""Tests for Bitcoin payment service."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import Mock, AsyncMock, patch

from bot.services.bitcoin_payment import BitcoinPaymentService
from bot.services.blockchain_api import BlockchainAPI, Transaction
from bot.services.payment_protocol import InvalidAddressError


@pytest.fixture
def btc_service():
    """Create Bitcoin payment service instance."""
    with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
        mock_settings.return_value.environment = "development"
        mock_settings.return_value.blockcypher_api_key = None
        service = BitcoinPaymentService()
        return service


class TestBitcoinAddressValidation:
    """Test Bitcoin address validation."""

    def test_validate_legacy_address(self, btc_service):
        """Test validation of legacy P2PKH address."""
        address = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        assert btc_service.validate_address(address)

    def test_validate_segwit_address(self, btc_service):
        """Test validation of SegWit P2SH address."""
        address = "3J98t1WpEZ73CNmYviecrnyiWrnqRhWNLy"
        assert btc_service.validate_address(address)

    def test_validate_bech32_address(self, btc_service):
        """Test validation of native SegWit bech32 address."""
        address = "bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh"
        assert btc_service.validate_address(address)

    def test_reject_invalid_address(self, btc_service):
        """Test rejection of invalid address."""
        assert not btc_service.validate_address("invalid_address")
        assert not btc_service.validate_address("")
        assert not btc_service.validate_address("0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2")  # ETH address


class TestBitcoinCreateAddress:
    """Test Bitcoin address creation."""

    def test_create_address_with_vendor_wallet(self, btc_service):
        """Test creating address with vendor wallet."""
        vendor_wallet = "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa"
        address, payment_id = btc_service.create_address(vendor_wallet)

        assert address == vendor_wallet
        assert len(payment_id) == 16
        assert payment_id.isalnum()

    def test_create_address_without_vendor_wallet_dev_mode(self, btc_service):
        """Test creating address in development mode without vendor wallet."""
        address, payment_id = btc_service.create_address()

        assert address.startswith("1")
        assert "Mock" in address
        assert len(payment_id) == 16

    def test_create_address_without_vendor_wallet_prod_mode(self):
        """Test creating address in production mode without vendor wallet."""
        with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "production"
            service = BitcoinPaymentService()

            with pytest.raises(InvalidAddressError, match="Vendor BTC wallet address is required"):
                service.create_address()

    def test_create_address_with_invalid_vendor_wallet(self, btc_service):
        """Test creating address with invalid vendor wallet."""
        with pytest.raises(InvalidAddressError, match="Invalid Bitcoin address"):
            btc_service.create_address("invalid_wallet")


@pytest.mark.asyncio
class TestBitcoinCheckPaid:
    """Test Bitcoin payment verification."""

    async def test_check_paid_without_address(self, btc_service):
        """Test check_paid requires address parameter."""
        result = await btc_service.check_paid(
            payment_id="test123",
            expected_amount=Decimal("0.001")
        )
        assert result is False

    async def test_check_paid_payment_found(self, btc_service):
        """Test check_paid finds matching payment."""
        # Mock transaction
        mock_tx = Mock()
        mock_tx.hash = "abc123"
        mock_tx.received_btc = Decimal("0.001")
        mock_tx.confirmations = 6

        # Mock API
        with patch.object(btc_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_tx

            result = await btc_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.001"),
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                created_at=datetime.utcnow()
            )

            assert result is True
            mock_find.assert_called_once()

    async def test_check_paid_insufficient_confirmations(self, btc_service):
        """Test check_paid with insufficient confirmations."""
        # Mock transaction with only 2 confirmations
        mock_tx = Mock()
        mock_tx.hash = "abc123"
        mock_tx.received_btc = Decimal("0.001")
        mock_tx.confirmations = 2

        with patch.object(btc_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_tx

            result = await btc_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.001"),
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                created_at=datetime.utcnow()
            )

            assert result is False

    async def test_check_paid_payment_not_found(self, btc_service):
        """Test check_paid when payment not found."""
        with patch.object(btc_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await btc_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.001"),
                address="1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
                created_at=datetime.utcnow()
            )

            assert result is False

    async def test_get_confirmations_from_cache(self, btc_service):
        """Test getting confirmations from cache."""
        # First, cache a transaction
        mock_tx = Mock()
        mock_tx.hash = "abc123"
        mock_tx.confirmations = 3

        btc_service._payment_cache["test123"] = (
            "1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa",
            Decimal("0.001"),
            datetime.utcnow(),
            mock_tx
        )

        with patch.object(btc_service.api, 'get_transaction_confirmations', new_callable=AsyncMock) as mock_confs:
            mock_confs.return_value = 5

            confirmations = await btc_service.get_confirmations("test123")

            assert confirmations == 5
            mock_confs.assert_called_once_with("abc123")


class TestBitcoinGetBalance:
    """Test Bitcoin balance retrieval."""

    def test_get_balance_not_implemented(self, btc_service):
        """Test get_balance returns zero (not implemented)."""
        balance = btc_service.get_balance()
        assert balance == Decimal("0")
