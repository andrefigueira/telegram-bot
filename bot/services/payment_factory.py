"""Factory for creating payment service instances based on currency."""

from __future__ import annotations

import logging
from typing import Union

from .payment_protocol import PaymentServiceProtocol, PaymentError
from .payments import MoneroPaymentService
from .bitcoin_payment import BitcoinPaymentService
from .ethereum_payment import EthereumPaymentService

logger = logging.getLogger(__name__)


# Type alias for payment services
PaymentService = Union[MoneroPaymentService, BitcoinPaymentService, EthereumPaymentService]


# Supported currencies
SUPPORTED_CURRENCIES = ["XMR", "BTC", "ETH"]

# Confirmation thresholds per currency
CONFIRMATION_THRESHOLDS = {
    "XMR": 10,  # ~20 minutes
    "BTC": 6,   # ~1 hour
    "ETH": 12,  # ~3 minutes
}


class UnsupportedCurrencyError(PaymentError):
    """Raised when an unsupported currency is requested."""
    pass


class PaymentServiceFactory:
    """
    Factory for creating cryptocurrency payment service instances.

    Usage:
        service = PaymentServiceFactory.create("BTC")
        address, payment_id = service.create_address(vendor_wallet="1ABC...")
    """

    # Singleton instances (cached for efficiency)
    _instances = {}

    @classmethod
    def create(cls, currency: str) -> PaymentService:
        """
        Create or retrieve a payment service instance for the specified currency.

        Args:
            currency: Currency code ("XMR", "BTC", or "ETH")

        Returns:
            Payment service instance implementing PaymentServiceProtocol

        Raises:
            UnsupportedCurrencyError: If currency is not supported

        Example:
            >>> service = PaymentServiceFactory.create("BTC")
            >>> address, payment_id = service.create_address(vendor_wallet="1ABC...")
        """
        currency = currency.upper()

        if currency not in SUPPORTED_CURRENCIES:
            raise UnsupportedCurrencyError(
                f"Currency '{currency}' is not supported. "
                f"Supported currencies: {', '.join(SUPPORTED_CURRENCIES)}"
            )

        # Return cached instance if available
        if currency in cls._instances:
            return cls._instances[currency]

        # Create new instance
        if currency == "XMR":
            service = MoneroPaymentService()
        elif currency == "BTC":
            service = BitcoinPaymentService()
        elif currency == "ETH":
            service = EthereumPaymentService()
        else:
            # Should never reach here due to validation above
            raise UnsupportedCurrencyError(f"Unsupported currency: {currency}")

        # Cache the instance
        cls._instances[currency] = service

        logger.info(f"Created payment service for {currency}")
        return service

    @classmethod
    def get_confirmation_threshold(cls, currency: str) -> int:
        """
        Get the required confirmation threshold for a currency.

        Args:
            currency: Currency code ("XMR", "BTC", or "ETH")

        Returns:
            Number of confirmations required

        Example:
            >>> PaymentServiceFactory.get_confirmation_threshold("BTC")
            6
        """
        currency = currency.upper()
        return CONFIRMATION_THRESHOLDS.get(currency, 10)

    @classmethod
    def is_supported(cls, currency: str) -> bool:
        """
        Check if a currency is supported.

        Args:
            currency: Currency code to check

        Returns:
            True if currency is supported

        Example:
            >>> PaymentServiceFactory.is_supported("BTC")
            True
            >>> PaymentServiceFactory.is_supported("DOGE")
            False
        """
        return currency.upper() in SUPPORTED_CURRENCIES

    @classmethod
    def get_supported_currencies(cls) -> list[str]:
        """
        Get list of supported currencies.

        Returns:
            List of currency codes

        Example:
            >>> PaymentServiceFactory.get_supported_currencies()
            ['XMR', 'BTC', 'ETH']
        """
        return SUPPORTED_CURRENCIES.copy()

    @classmethod
    def clear_cache(cls):
        """
        Clear all cached payment service instances.

        Useful for testing or when configuration changes.
        """
        cls._instances.clear()
        logger.info("Cleared payment service cache")


def get_payment_service(currency: str) -> PaymentService:
    """
    Convenience function to create a payment service.

    Args:
        currency: Currency code ("XMR", "BTC", or "ETH")

    Returns:
        Payment service instance

    Example:
        >>> service = get_payment_service("ETH")
        >>> address, payment_id = service.create_address(vendor_wallet="0x...")
    """
    return PaymentServiceFactory.create(currency)


if __name__ == "__main__":
    # Test the factory
    print("Testing Payment Service Factory")
    print(f"Supported currencies: {PaymentServiceFactory.get_supported_currencies()}")

    for currency in ["XMR", "BTC", "ETH"]:
        service = PaymentServiceFactory.create(currency)
        threshold = PaymentServiceFactory.get_confirmation_threshold(currency)
        print(f"{currency}: {type(service).__name__} (threshold: {threshold} confs)")

    # Test unsupported currency
    try:
        PaymentServiceFactory.create("DOGE")
        print("ERROR: Should have raised UnsupportedCurrencyError")
    except UnsupportedCurrencyError as e:
        print(f"Correctly rejected unsupported currency: {e}")

    print("\nAll tests passed!")
