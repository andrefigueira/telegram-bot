"""Ethereum payment service implementation."""

from __future__ import annotations

import uuid
import logging
import re
from typing import Tuple, Optional
from decimal import Decimal
from datetime import datetime

from ..config import get_settings
from .payment_protocol import (
    PaymentServiceProtocol,
    RetryableError,
    InvalidAddressError,
    PaymentError
)
from .etherscan_api import EtherscanAPI, EtherscanAPIError

logger = logging.getLogger(__name__)


class EthereumPaymentService:
    """
    Ethereum payment service using Etherscan API.

    Uses vendor's ETH address with amount-based payment matching.
    No unique address generation (avoids private key management).
    """

    # Confirmation threshold for considering payment complete
    CONFIRMATION_THRESHOLD = 12

    # Amount tolerance for matching (0.001 ETH ~= $3 at $3k/ETH)
    AMOUNT_TOLERANCE = Decimal("0.001")

    def __init__(self):
        self.settings = get_settings()

        if not self.settings.etherscan_api_key:
            logger.warning("Etherscan API key not configured")

        self.api = EtherscanAPI(
            api_key=self.settings.etherscan_api_key or "",
            infura_project_id=self.settings.infura_project_id
        )
        self._payment_cache = {}  # Cache {payment_id: (address, amount, created_at, tx)}

    @staticmethod
    def validate_address(address: str) -> bool:
        """
        Validate Ethereum address format.

        Args:
            address: Ethereum address to validate (0x...)

        Returns:
            True if valid format
        """
        # Basic format check (0x followed by 40 hex characters)
        if not re.match(r'^0x[a-fA-F0-9]{40}$', address):
            return False

        return True

    @staticmethod
    def to_checksum_address(address: str) -> str:
        """
        Convert address to checksummed format (EIP-55).

        Args:
            address: Ethereum address

        Returns:
            Checksummed address

        Note:
            Simplified implementation. For production, use web3.py's toChecksumAddress
        """
        address = address.lower().replace('0x', '')

        # Simple checksum (not full EIP-55 implementation)
        # For full implementation, would need to use web3.py or implement keccak256
        return '0x' + address

    def create_address(self, vendor_wallet: Optional[str] = None) -> Tuple[str, str]:
        """
        Create a payment address for receiving ETH.

        Args:
            vendor_wallet: Vendor's ETH address (required)

        Returns:
            Tuple of (eth_address, payment_id)

        Raises:
            InvalidAddressError: If vendor_wallet is invalid or missing
        """
        if not vendor_wallet:
            if self.settings.environment == "development":
                # Mock address for testing
                payment_id = uuid.uuid4().hex[:16]
                mock_address = f"0x{payment_id}{'0' * 24}"
                logger.warning("Using mock ETH address (development mode)")
                return mock_address, payment_id
            raise InvalidAddressError("Vendor ETH wallet address is required")

        # Validate vendor address
        if not self.validate_address(vendor_wallet):
            raise InvalidAddressError(f"Invalid Ethereum address: {vendor_wallet}")

        # Normalize to checksummed format
        checksummed = self.to_checksum_address(vendor_wallet)

        # Generate unique payment ID for tracking
        payment_id = uuid.uuid4().hex[:16]

        logger.info(f"Created ETH payment address: {checksummed} (ID: {payment_id})")
        return checksummed, payment_id

    async def check_paid(
        self,
        payment_id: str,
        expected_amount: Optional[Decimal] = None,
        address: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> bool:
        """
        Check if an Ethereum payment has been received and confirmed.

        Args:
            payment_id: The payment ID to check
            expected_amount: Expected ETH amount
            address: Ethereum address to check (required for ETH)
            created_at: Order creation time (required for ETH)

        Returns:
            True if payment is confirmed with sufficient confirmations

        Note:
            Requires 12 confirmations for PAID status (~3 minutes)
        """
        # ETH requires address and amount for verification
        if not address or not expected_amount:
            logger.error(f"ETH payment check requires address and expected_amount")
            return False

        # Use provided created_at or fallback to cached value
        if not created_at:
            cached = self._payment_cache.get(payment_id)
            if cached:
                _, _, created_at, _ = cached
            else:
                logger.error(f"No created_at time for payment {payment_id}")
                return False

        try:
            # Check if we've already found this transaction
            cached = self._payment_cache.get(payment_id)
            if cached:
                cached_addr, cached_amount, cached_time, cached_tx = cached
                if cached_tx:
                    # Re-check confirmations
                    confirmations = await self.api.get_transaction_confirmations(cached_tx.hash)
                    if confirmations >= self.CONFIRMATION_THRESHOLD:
                        logger.info(f"ETH payment {payment_id} confirmed ({confirmations} confs)")
                        return True
                    return False

            # Search for payment
            tx = await self.api.find_payment(
                address=address,
                expected_amount=expected_amount,
                created_at=created_at,
                tolerance=self.AMOUNT_TOLERANCE
            )

            if tx:
                # Cache the transaction
                self._payment_cache[payment_id] = (address, expected_amount, created_at, tx)

                # Check if sufficient confirmations
                if tx.confirmations >= self.CONFIRMATION_THRESHOLD:
                    logger.info(
                        f"ETH payment {payment_id} confirmed: {tx.value_eth} ETH "
                        f"({tx.confirmations} confs)"
                    )
                    return True
                else:
                    logger.info(
                        f"ETH payment {payment_id} pending: {tx.value_eth} ETH "
                        f"({tx.confirmations}/{self.CONFIRMATION_THRESHOLD} confs)"
                    )
                    return False

            # Payment not found
            return False

        except EtherscanAPIError as e:
            logger.error(f"Etherscan API error checking payment {payment_id}: {e}")
            raise RetryableError(f"Failed to check ETH payment: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking ETH payment {payment_id}: {e}")
            return False

    def check_paid_sync(
        self,
        payment_id: str,
        expected_amount: Optional[Decimal] = None,
        address: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> bool:
        """
        Synchronous wrapper for check_paid (for compatibility).

        Note: This creates a new event loop. Prefer async version when possible.
        """
        import asyncio
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        return loop.run_until_complete(
            self.check_paid(payment_id, expected_amount, address, created_at)
        )

    async def get_confirmations(
        self,
        payment_id: str,
        address: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> int:
        """
        Get the number of confirmations for a payment.

        Args:
            payment_id: The payment ID to check
            address: Ethereum address (required)
            created_at: Order creation time (required)

        Returns:
            Number of confirmations (0 if payment not found)
        """
        # Check cache first
        cached = self._payment_cache.get(payment_id)
        if cached:
            cached_addr, cached_amount, cached_time, cached_tx = cached
            if cached_tx:
                try:
                    confirmations = await self.api.get_transaction_confirmations(cached_tx.hash)
                    # Update cache
                    cached_tx.confirmations = confirmations
                    return confirmations
                except Exception as e:
                    logger.error(f"Error getting confirmations: {e}")
                    return 0

        # If not in cache, we can't find it without the full payment details
        logger.warning(
            f"Cannot get confirmations for {payment_id} - transaction not cached"
        )
        return 0

    def get_balance(self) -> Decimal:
        """
        Get the current wallet balance.

        Note: Not implemented for Ethereum (requires wallet integration)

        Returns:
            Decimal("0")
        """
        logger.warning("get_balance() not implemented for Ethereum service")
        return Decimal("0")


# Ensure the service implements the protocol
def _validate():
    """Compile-time validation that EthereumPaymentService implements the protocol."""
    service: PaymentServiceProtocol = EthereumPaymentService()  # type: ignore


if __name__ == "__main__":
    # Basic validation
    service = EthereumPaymentService()
    print("Ethereum payment service initialized successfully")
    print(f"Validates address: {service.validate_address('0x742d35Cc6634C0532925a3b844Bc9e7595f0bEb2')}")
    print(f"Rejects invalid: {not service.validate_address('invalid_address')}")
