"""Payment service protocol defining the interface for all payment implementations."""

from __future__ import annotations

from decimal import Decimal
from typing import Protocol, Tuple, Optional, runtime_checkable


class RetryableError(Exception):
    """Error that indicates the operation should be retried."""
    pass


class PaymentError(Exception):
    """Base exception for payment-related errors."""
    pass


class InvalidAddressError(PaymentError):
    """Invalid cryptocurrency address."""
    pass


class InsufficientFundsError(PaymentError):
    """Insufficient funds for operation."""
    pass


@runtime_checkable
class PaymentServiceProtocol(Protocol):
    """
    Protocol defining the interface for cryptocurrency payment services.

    All payment service implementations (Monero, Bitcoin, Ethereum) must
    implement this protocol to ensure consistent behavior across currencies.
    """

    def create_address(self, vendor_wallet: Optional[str] = None) -> Tuple[str, str]:
        """
        Create a payment address for receiving funds.

        Args:
            vendor_wallet: Optional vendor wallet address to use

        Returns:
            Tuple of (payment_address, payment_id)
            - payment_address: Address where funds should be sent
            - payment_id: Unique identifier for tracking this payment

        Raises:
            RetryableError: If RPC/API is temporarily unavailable
            InvalidAddressError: If vendor_wallet is invalid
        """
        ...

    def check_paid(self, payment_id: str, expected_amount: Optional[Decimal] = None) -> bool:
        """
        Check if a payment has been received and confirmed.

        Args:
            payment_id: The payment ID to check
            expected_amount: Optional amount to verify (in crypto units)

        Returns:
            True if payment is confirmed with sufficient confirmations

        Note:
            Confirmation thresholds vary by currency:
            - Bitcoin: 6 confirmations
            - Ethereum: 12 confirmations
            - Monero: 10 confirmations
        """
        ...

    def get_confirmations(self, payment_id: str) -> int:
        """
        Get the number of confirmations for a payment.

        Args:
            payment_id: The payment ID to check

        Returns:
            Number of confirmations (0 if payment not found)
        """
        ...

    def get_balance(self) -> Decimal:
        """
        Get the current wallet balance.

        Returns:
            Balance in cryptocurrency units (BTC, ETH, XMR)
        """
        ...


def validate_payment_service(service: object) -> bool:
    """
    Validate that an object implements the PaymentServiceProtocol.

    Args:
        service: Object to validate

    Returns:
        True if service implements the protocol

    Raises:
        TypeError: If service doesn't implement required methods
    """
    if not isinstance(service, PaymentServiceProtocol):
        raise TypeError(
            f"{type(service).__name__} does not implement PaymentServiceProtocol. "
            f"Required methods: create_address, check_paid, get_confirmations, get_balance"
        )
    return True
