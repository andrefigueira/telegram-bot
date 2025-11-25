"""Payment processing for Monero integration."""

from __future__ import annotations

import uuid
import logging
from typing import Tuple, Optional
from decimal import Decimal

from ..config import get_settings
from ..error_handler import RetryableError

logger = logging.getLogger(__name__)


class MoneroPaymentService:
    """Production Monero payment service."""
    
    def __init__(self):
        self.settings = get_settings()
        self._wallet = None
        
    def _get_wallet(self):
        """Get or create wallet connection."""
        if self._wallet is None and self.settings.monero_rpc_url:
            try:
                from monero.wallet import Wallet
                self._wallet = Wallet(self.settings.monero_rpc_url)
            except Exception as e:
                logger.error(f"Failed to connect to Monero wallet: {e}")
                raise RetryableError("Monero wallet connection failed")
        return self._wallet
    
    def create_address(self, vendor_wallet: Optional[str] = None) -> Tuple[str, str]:
        """Create a new payment address with unique payment ID.

        Args:
            vendor_wallet: Optional vendor wallet address to use as fallback
        """
        payment_id = uuid.uuid4().hex[:16]  # 16 char payment ID for Monero

        # Try RPC first if configured
        if self.settings.monero_rpc_url:
            try:
                wallet = self._get_wallet()
                if wallet:
                    # Create integrated address with payment ID
                    address = wallet.make_integrated_address(payment_id=payment_id)
                    return str(address), payment_id
            except Exception as e:
                logger.error(f"Failed to create Monero address via RPC: {e}")

        # Use vendor's wallet address if available
        if vendor_wallet:
            logger.info(f"Using vendor wallet address with payment ID: {payment_id}")
            return vendor_wallet, payment_id

        # Final fallback for development/testing
        if self.settings.environment == "development":
            mock_address = f"4{payment_id}{'A' * (95 - len(payment_id) - 1)}"
            logger.warning(f"Using mock payment address (development mode)")
            return mock_address, payment_id

        raise RetryableError("Failed to create payment address - vendor wallet not configured")
    
    def check_paid(self, payment_id: str, expected_amount: Optional[Decimal] = None) -> bool:
        """Check if payment has been received."""
        try:
            wallet = self._get_wallet()
            if wallet:
                # Check incoming transfers with payment ID
                transfers = wallet.incoming(payment_id=payment_id)

                if not transfers:
                    return False

                # Sum all transfers with this payment ID
                total_received = sum(t.amount for t in transfers)

                # Check if expected amount is met
                if expected_amount and total_received < expected_amount:
                    logger.warning(
                        f"Payment {payment_id} received {total_received} XMR, "
                        f"expected {expected_amount} XMR"
                    )
                    return False

                return True

        except Exception as e:
            logger.error(f"Failed to check payment status: {e}")

        # Fallback for development/testing or when RPC not configured
        if self.settings.environment == "development" or not self.settings.monero_rpc_url:
            return False  # In demo mode, payments stay pending

        raise RetryableError("Failed to check payment status")
    
    def get_balance(self) -> Decimal:
        """Get wallet balance."""
        try:
            wallet = self._get_wallet()
            if wallet:
                return wallet.balance()
        except Exception as e:
            logger.error(f"Failed to get wallet balance: {e}")
        
        return Decimal("0")


class PaymentService(MoneroPaymentService):
    """Alias for backward compatibility."""
    pass
