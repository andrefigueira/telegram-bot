"""Payment processing for Monero integration."""

from __future__ import annotations

import uuid
import logging
from typing import Tuple, Optional
from decimal import Decimal
from urllib.parse import urlparse

from ..config import get_settings
from ..error_handler import RetryableError

logger = logging.getLogger(__name__)


class MoneroPaymentService:
    """Production Monero payment service."""
    
    def __init__(self):
        self.settings = get_settings()
        self._wallet = None

    def _split_rpc_url(self, rpc_url: str) -> tuple[str, int]:
        if "://" in rpc_url:
            parsed = urlparse(rpc_url)
        else:
            parsed = urlparse(f"http://{rpc_url}")
        host = parsed.hostname or rpc_url
        port = parsed.port or 18082
        return host, port
        
    def _get_wallet(self):
        """Get or create wallet connection."""
        if self._wallet is None and self.settings.monero_rpc_url:
            try:
                from monero.wallet import Wallet
                from monero.backends.jsonrpc import JSONRPCWallet
                host, port = self._split_rpc_url(self.settings.monero_rpc_url)
                # Create backend with digest auth credentials
                backend = JSONRPCWallet(
                    host=host,
                    port=port,
                    user=self.settings.monero_rpc_user or None,
                    password=self.settings.monero_rpc_password or None,
                )
                # Wrap backend with Wallet for full API access
                self._wallet = Wallet(backend)
            except Exception as e:
                logger.error(f"Failed to connect to Monero wallet: {e}")
                raise RetryableError("Monero wallet connection failed")
        return self._wallet
    
    def get_address_for_payment_id(self, payment_id: str, vendor_wallet: Optional[str] = None) -> str:
        if self.settings.monero_rpc_url:
            try:
                wallet = self._get_wallet()
                if wallet:
                    address = wallet.make_integrated_address(payment_id=payment_id)
                    return str(address)
            except Exception as e:
                logger.error(f"Failed to create Monero address via RPC: {e}")

        if vendor_wallet:
            logger.info(f"Using vendor wallet address with payment ID: {payment_id}")
            return vendor_wallet

        if self.settings.environment == "development":
            mock_address = f"4{payment_id}{'A' * (95 - len(payment_id) - 1)}"
            logger.warning("Using mock payment address (development mode)")
            return mock_address

        raise RetryableError("Failed to create payment address - vendor wallet not configured")

    def create_address(self, vendor_wallet: Optional[str] = None) -> Tuple[str, str]:
        """Create a new payment address with unique payment ID.

        Args:
            vendor_wallet: Optional vendor wallet address to use as fallback
        """
        payment_id = uuid.uuid4().hex[:16]  # 16 char payment ID for Monero
        address = self.get_address_for_payment_id(payment_id, vendor_wallet=vendor_wallet)
        return address, payment_id
    
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
