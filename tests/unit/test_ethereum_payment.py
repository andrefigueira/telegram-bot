"""Tests for Ethereum payment service."""

import pytest
from decimal import Decimal
from datetime import datetime
from unittest.mock import Mock, AsyncMock, patch

from bot.services.ethereum_payment import EthereumPaymentService
from bot.services.etherscan_api import EtherscanAPI, EthereumTransaction
from bot.services.payment_protocol import InvalidAddressError


@pytest.fixture
def eth_service():
    """Create Ethereum payment service instance."""
    with patch('bot.services.ethereum_payment.get_settings') as mock_settings:
        mock_settings.return_value.environment = "development"
        mock_settings.return_value.etherscan_api_key = "test_key"
        mock_settings.return_value.infura_project_id = None
        service = EthereumPaymentService()
        return service


class TestEthereumAddressValidation:
    """Test Ethereum address validation."""

    def test_validate_valid_address(self, eth_service):
        """Test validation of valid Ethereum address."""
        address = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2"
        assert eth_service.validate_address(address)

    def test_validate_lowercase_address(self, eth_service):
        """Test validation of lowercase address."""
        address = "0x742d35cc6634c0532925a3b844bc9e7595f0beb2"
        assert eth_service.validate_address(address)

    def test_reject_invalid_address(self, eth_service):
        """Test rejection of invalid address."""
        assert not eth_service.validate_address("invalid_address")
        assert not eth_service.validate_address("")
        assert not eth_service.validate_address("1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa")  # BTC address
        assert not eth_service.validate_address("0x742d35C")  # Too short

    def test_reject_address_without_0x_prefix(self, eth_service):
        """Test rejection of address without 0x prefix."""
        assert not eth_service.validate_address("742d35Cc6634C0532925a3b844Bc9e7595f0bEb2")


class TestEthereumCreateAddress:
    """Test Ethereum address creation."""

    def test_create_address_with_vendor_wallet(self, eth_service):
        """Test creating address with vendor wallet."""
        vendor_wallet = "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2"
        address, payment_id = eth_service.create_address(vendor_wallet)

        assert address.startswith("0x")
        assert len(address) == 42
        assert len(payment_id) == 16
        assert payment_id.isalnum()

    def test_create_address_without_vendor_wallet_dev_mode(self, eth_service):
        """Test creating address in development mode without vendor wallet."""
        address, payment_id = eth_service.create_address()

        assert address.startswith("0x")
        assert len(address) == 42
        assert len(payment_id) == 16

    def test_create_address_without_vendor_wallet_prod_mode(self):
        """Test creating address in production mode without vendor wallet."""
        with patch('bot.services.ethereum_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "production"
            mock_settings.return_value.etherscan_api_key = "test_key"
            service = EthereumPaymentService()

            with pytest.raises(InvalidAddressError, match="Vendor ETH wallet address is required"):
                service.create_address()

    def test_create_address_with_invalid_vendor_wallet(self, eth_service):
        """Test creating address with invalid vendor wallet."""
        with pytest.raises(InvalidAddressError, match="Invalid Ethereum address"):
            eth_service.create_address("invalid_wallet")


@pytest.mark.asyncio
class TestEthereumCheckPaid:
    """Test Ethereum payment verification."""

    async def test_check_paid_without_address(self, eth_service):
        """Test check_paid requires address parameter."""
        result = await eth_service.check_paid(
            payment_id="test123",
            expected_amount=Decimal("0.1")
        )
        assert result is False

    async def test_check_paid_payment_found(self, eth_service):
        """Test check_paid finds matching payment."""
        # Mock transaction
        mock_tx = Mock()
        mock_tx.hash = "0xabc123"
        mock_tx.value_eth = Decimal("0.1")
        mock_tx.confirmations = 12

        # Mock API
        with patch.object(eth_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_tx

            result = await eth_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.1"),
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
                created_at=datetime.utcnow()
            )

            assert result is True
            mock_find.assert_called_once()

    async def test_check_paid_insufficient_confirmations(self, eth_service):
        """Test check_paid with insufficient confirmations."""
        # Mock transaction with only 5 confirmations
        mock_tx = Mock()
        mock_tx.hash = "0xabc123"
        mock_tx.value_eth = Decimal("0.1")
        mock_tx.confirmations = 5

        with patch.object(eth_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = mock_tx

            result = await eth_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.1"),
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
                created_at=datetime.utcnow()
            )

            assert result is False

    async def test_check_paid_payment_not_found(self, eth_service):
        """Test check_paid when payment not found."""
        with patch.object(eth_service.api, 'find_payment', new_callable=AsyncMock) as mock_find:
            mock_find.return_value = None

            result = await eth_service.check_paid(
                payment_id="test123",
                expected_amount=Decimal("0.1"),
                address="0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
                created_at=datetime.utcnow()
            )

            assert result is False

    async def test_get_confirmations_from_cache(self, eth_service):
        """Test getting confirmations from cache."""
        # First, cache a transaction
        mock_tx = Mock()
        mock_tx.hash = "0xabc123"
        mock_tx.confirmations = 7

        eth_service._payment_cache["test123"] = (
            "0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2",
            Decimal("0.1"),
            datetime.utcnow(),
            mock_tx
        )

        with patch.object(eth_service.api, 'get_transaction_confirmations', new_callable=AsyncMock) as mock_confs:
            mock_confs.return_value = 10

            confirmations = await eth_service.get_confirmations("test123")

            assert confirmations == 10
            mock_confs.assert_called_once_with("0xabc123")


class TestEthereumGetBalance:
    """Test Ethereum balance retrieval."""

    def test_get_balance_not_implemented(self, eth_service):
        """Test get_balance returns zero (not implemented)."""
        balance = eth_service.get_balance()
        assert balance == Decimal("0")


class TestEthereumChecksum:
    """Test Ethereum address checksumming."""

    def test_to_checksum_address(self, eth_service):
        """Test converting address to checksum format."""
        address = "0x742d35cc6634c0532925a3b844bc9e7595f0beb2"
        checksummed = eth_service.to_checksum_address(address)

        assert checksummed.startswith("0x")
        assert len(checksummed) == 42
