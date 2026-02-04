"""Tests for payment service factory."""

import pytest
from unittest.mock import patch

from bot.services.payment_factory import (
    PaymentServiceFactory,
    UnsupportedCurrencyError,
    get_payment_service
)
from bot.services.payments import MoneroPaymentService
from bot.services.bitcoin_payment import BitcoinPaymentService
from bot.services.ethereum_payment import EthereumPaymentService


@pytest.fixture(autouse=True)
def clear_factory_cache():
    """Clear factory cache before each test."""
    PaymentServiceFactory.clear_cache()
    yield
    PaymentServiceFactory.clear_cache()


class TestPaymentServiceFactory:
    """Test payment service factory."""

    def test_create_monero_service(self):
        """Test creating Monero payment service."""
        service = PaymentServiceFactory.create("XMR")
        assert isinstance(service, MoneroPaymentService)

    def test_create_bitcoin_service(self):
        """Test creating Bitcoin payment service."""
        with patch('bot.services.bitcoin_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "development"
            service = PaymentServiceFactory.create("BTC")
            assert isinstance(service, BitcoinPaymentService)

    def test_create_ethereum_service(self):
        """Test creating Ethereum payment service."""
        with patch('bot.services.ethereum_payment.get_settings') as mock_settings:
            mock_settings.return_value.environment = "development"
            mock_settings.return_value.etherscan_api_key = "test"
            service = PaymentServiceFactory.create("ETH")
            assert isinstance(service, EthereumPaymentService)

    def test_create_case_insensitive(self):
        """Test creating service with lowercase currency."""
        service1 = PaymentServiceFactory.create("xmr")
        service2 = PaymentServiceFactory.create("XMR")
        assert isinstance(service1, MoneroPaymentService)
        assert isinstance(service2, MoneroPaymentService)

    def test_create_unsupported_currency(self):
        """Test creating service with unsupported currency."""
        with pytest.raises(UnsupportedCurrencyError, match="Currency 'DOGE' is not supported"):
            PaymentServiceFactory.create("DOGE")

    def test_service_caching(self):
        """Test that services are cached."""
        service1 = PaymentServiceFactory.create("XMR")
        service2 = PaymentServiceFactory.create("XMR")
        assert service1 is service2  # Same instance

    def test_clear_cache(self):
        """Test clearing service cache."""
        service1 = PaymentServiceFactory.create("XMR")
        PaymentServiceFactory.clear_cache()
        service2 = PaymentServiceFactory.create("XMR")
        assert service1 is not service2  # Different instances


class TestConfirmationThresholds:
    """Test confirmation threshold retrieval."""

    def test_get_xmr_threshold(self):
        """Test getting XMR confirmation threshold."""
        threshold = PaymentServiceFactory.get_confirmation_threshold("XMR")
        assert threshold == 10

    def test_get_btc_threshold(self):
        """Test getting BTC confirmation threshold."""
        threshold = PaymentServiceFactory.get_confirmation_threshold("BTC")
        assert threshold == 6

    def test_get_eth_threshold(self):
        """Test getting ETH confirmation threshold."""
        threshold = PaymentServiceFactory.get_confirmation_threshold("ETH")
        assert threshold == 12

    def test_get_threshold_case_insensitive(self):
        """Test getting threshold with lowercase currency."""
        threshold = PaymentServiceFactory.get_confirmation_threshold("btc")
        assert threshold == 6


class TestSupportedCurrencies:
    """Test currency support checking."""

    def test_is_supported_xmr(self):
        """Test XMR is supported."""
        assert PaymentServiceFactory.is_supported("XMR")

    def test_is_supported_btc(self):
        """Test BTC is supported."""
        assert PaymentServiceFactory.is_supported("BTC")

    def test_is_supported_eth(self):
        """Test ETH is supported."""
        assert PaymentServiceFactory.is_supported("ETH")

    def test_is_not_supported_doge(self):
        """Test DOGE is not supported."""
        assert not PaymentServiceFactory.is_supported("DOGE")

    def test_is_supported_case_insensitive(self):
        """Test support check is case insensitive."""
        assert PaymentServiceFactory.is_supported("btc")
        assert PaymentServiceFactory.is_supported("Btc")

    def test_get_supported_currencies(self):
        """Test getting list of supported currencies."""
        currencies = PaymentServiceFactory.get_supported_currencies()
        assert currencies == ["XMR", "BTC", "ETH"]


class TestConvenienceFunction:
    """Test convenience function."""

    def test_get_payment_service(self):
        """Test get_payment_service convenience function."""
        service = get_payment_service("XMR")
        assert isinstance(service, MoneroPaymentService)

    def test_get_payment_service_unsupported(self):
        """Test get_payment_service with unsupported currency."""
        with pytest.raises(UnsupportedCurrencyError):
            get_payment_service("DOGE")
