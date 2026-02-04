"""Bitcoin payment service implementation."""

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
from .blockchain_api import BlockchainAPI, BlockchainAPIError

logger = logging.getLogger(__name__)


class BitcoinPaymentService:
    """
    Bitcoin payment service using blockchain.info API.

    Uses vendor's BTC address with amount-based payment matching.
    No unique address generation (avoids private key management).
    """

    # Confirmation threshold for considering payment complete
    CONFIRMATION_THRESHOLD = 6

    # Amount tolerance for matching (0.00001 BTC ~= $0.45 at $45k/BTC)
    AMOUNT_TOLERANCE = Decimal("0.00001")

    def __init__(self):
        self.settings = get_settings()
        self.api = BlockchainAPI(api_key=self.settings.blockcypher_api_key)
        self._payment_cache = {}  # Cache {payment_id: (address, amount, created_at, tx)}

    @staticmethod
    def validate_address(address: str) -> bool:
        """
        Validate Bitcoin address format.

        Supports:
        - Legacy (P2PKH): 1...
        - SegWit (P2SH): 3...
        - Native SegWit (Bech32): bc1...

        Args:
            address: Bitcoin address to validate

        Returns:
            True if valid format
        """
        # Legacy address (P2PKH)
        if re.match(r'^[13][a-km-zA-HJ-NP-Z1-9]{25,34}$', address):
            return True

        # Bech32 address (native SegWit)
        if re.match(r'^bc1[a-z0-9]{39,87}$', address):
            return True

        return False

    def create_address(self, vendor_wallet: Optional[str] = None) -> Tuple[str, str]:
        """
        Create a payment address for receiving BTC.

        Args:
            vendor_wallet: Vendor's BTC address (required)

        Returns:
            Tuple of (btc_address, payment_id)

        Raises:
            InvalidAddressError: If vendor_wallet is invalid or missing
        """
        if not vendor_wallet:
            if self.settings.environment == "development":
                # Mock address for testing
                payment_id = uuid.uuid4().hex[:16]
                mock_address = f"1{payment_id}MockBitcoinAddr"
                logger.warning("Using mock BTC address (development mode)")
                return mock_address, payment_id
            raise InvalidAddressError("Vendor BTC wallet address is required")

        # Validate vendor address
        if not self.validate_address(vendor_wallet):
            raise InvalidAddressError(f"Invalid Bitcoin address: {vendor_wallet}")

        # Generate unique payment ID for tracking
        payment_id = uuid.uuid4().hex[:16]

        logger.info(f"Created BTC payment address: {vendor_wallet} (ID: {payment_id})")
        return vendor_wallet, payment_id

    async def check_paid(
        self,
        payment_id: str,
        expected_amount: Optional[Decimal] = None,
        address: Optional[str] = None,
        created_at: Optional[datetime] = None
    ) -> bool:
        """
        Check if a Bitcoin payment has been received and confirmed.

        Args:
            payment_id: The payment ID to check
            expected_amount: Expected BTC amount
            address: Bitcoin address to check (required for BTC)
            created_at: Order creation time (required for BTC)

        Returns:
            True if payment is confirmed with sufficient confirmations

        Note:
            Requires 6 confirmations for PAID status (~1 hour)
        """
        # BTC requires address and amount for verification
        if not address or not expected_amount:
            logger.error(f"BTC payment check requires address and expected_amount")
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
                        logger.info(f"BTC payment {payment_id} confirmed ({confirmations} confs)")
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
                        f"BTC payment {payment_id} confirmed: {tx.received_btc} BTC "
                        f"({tx.confirmations} confs)"
                    )
                    return True
                else:
                    logger.info(
                        f"BTC payment {payment_id} pending: {tx.received_btc} BTC "
                        f"({tx.confirmations}/{self.CONFIRMATION_THRESHOLD} confs)"
                    )
                    return False

            # Payment not found
            return False

        except BlockchainAPIError as e:
            logger.error(f"Blockchain API error checking payment {payment_id}: {e}")
            raise RetryableError(f"Failed to check BTC payment: {e}")
        except Exception as e:
            logger.error(f"Unexpected error checking BTC payment {payment_id}: {e}")
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
            address: Bitcoin address (required)
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

        Note: Not implemented for Bitcoin (requires wallet integration)

        Returns:
            Decimal("0")
        """
        logger.warning("get_balance() not implemented for Bitcoin service")
        return Decimal("0")


# Ensure the service implements the protocol
def _validate():
    """Compile-time validation that BitcoinPaymentService implements the protocol."""
    service: PaymentServiceProtocol = BitcoinPaymentService()  # type: ignore


if __name__ == "__main__":
    # Basic validation
    service = BitcoinPaymentService()
    print("Bitcoin payment service initialized successfully")
    print(f"Validates legacy address: {service.validate_address('1A1zP1eP5QGefi2DMPTfTL5SLmv7DivfNa')}")
    print(f"Validates bech32 address: {service.validate_address('bc1qxy2kgdygjrsqtzq2n0yrf2493p83kkfjhx0wlh')}")
    print(f"Rejects invalid address: {not service.validate_address('invalid_address')}")
