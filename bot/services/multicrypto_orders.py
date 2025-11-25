"""Multi-crypto order service combining swap and order management."""

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional

from bot.models_multitenant import (
    MultiTenantDatabase, Tenant, TenantProduct, TenantOrder,
    OrderState, SwapState
)
from bot.services.crypto_swap import CryptoSwapService, SwapOrder, SupportedCoin

logger = logging.getLogger(__name__)


def encrypt_address(address: str, encryption_key: str) -> str:
    """Encrypt a delivery address."""
    from nacl.secret import SecretBox
    import base64

    # Key is hex string, convert to bytes
    key_bytes = bytes.fromhex(encryption_key)
    # Pad or truncate to 32 bytes
    key_bytes = key_bytes[:32].ljust(32, b'\0')

    box = SecretBox(key_bytes)
    encrypted = box.encrypt(address.encode('utf-8'))
    return base64.b64encode(encrypted).decode('utf-8')


def decrypt_address(encrypted: str, encryption_key: str) -> str:
    """Decrypt a delivery address."""
    from nacl.secret import SecretBox
    import base64

    key_bytes = bytes.fromhex(encryption_key)
    key_bytes = key_bytes[:32].ljust(32, b'\0')

    box = SecretBox(key_bytes)
    encrypted_bytes = base64.b64decode(encrypted)
    decrypted = box.decrypt(encrypted_bytes)
    return decrypted.decode('utf-8')


class MultiCryptoOrderService:
    """Service for handling orders with multi-crypto payments."""

    def __init__(
        self,
        db: MultiTenantDatabase,
        swap_service: CryptoSwapService
    ):
        self.db = db
        self.swap_service = swap_service

    async def get_supported_payment_methods(self) -> list[str]:
        """Get list of supported payment cryptocurrencies."""
        return await self.swap_service.get_supported_coins()

    async def create_order(
        self,
        tenant_id: str,
        product_id: int,
        customer_telegram_id: int,
        quantity: int,
        delivery_address: str,
        payment_coin: str = "xmr"
    ) -> Optional[dict]:
        """
        Create an order with multi-crypto payment support.

        Returns dict with order details and payment instructions.
        """
        payment_coin = payment_coin.lower()

        # Validate payment coin
        supported = await self.get_supported_payment_methods()
        if payment_coin not in supported:
            raise ValueError(f"Unsupported payment method: {payment_coin}")

        # Get tenant and product
        tenant = self.db.get_tenant(tenant_id)
        if not tenant:
            raise ValueError("Tenant not found")

        if not tenant.monero_wallet_address:
            raise ValueError("Tenant has no Monero wallet configured")

        product = self.db.get_product(product_id, tenant_id)
        if not product:
            raise ValueError("Product not found")

        if not product.active:
            raise ValueError("Product is not available")

        if product.inventory < quantity:
            raise ValueError(f"Insufficient inventory. Available: {product.inventory}")

        # Calculate totals in XMR
        total_xmr = product.price_xmr * quantity
        commission_xmr = total_xmr * tenant.commission_rate

        # Encrypt delivery address with tenant's key
        address_encrypted = encrypt_address(delivery_address, tenant.encryption_key)

        # Determine payment details based on coin
        if payment_coin == "xmr":
            # Direct XMR payment to tenant's wallet
            payment_address = tenant.monero_wallet_address
            payment_amount = total_xmr
            swap_id = None
            swap_provider = None
        else:
            # Create swap from payment_coin to XMR
            swap_order = await self.swap_service.create_swap(
                from_coin=payment_coin,
                from_amount=total_xmr,  # We need to get equivalent amount
                destination_xmr_address=tenant.monero_wallet_address
            )

            if not swap_order:
                raise ValueError(f"Unable to create swap for {payment_coin}")

            payment_address = swap_order.deposit_address
            payment_amount = swap_order.expected_amount
            swap_id = swap_order.swap_id
            swap_provider = swap_order.provider

        # Decrement inventory
        if not self.db.decrement_inventory(product_id, tenant_id, quantity):
            raise ValueError("Failed to reserve inventory")

        # Create order
        order = self.db.create_order(
            tenant_id=tenant_id,
            product_id=product_id,
            customer_telegram_id=customer_telegram_id,
            quantity=quantity,
            total_xmr=total_xmr,
            commission_xmr=commission_xmr,
            payment_coin=payment_coin,
            payment_amount=payment_amount,
            payment_address=payment_address,
            address_encrypted=address_encrypted,
            swap_id=swap_id,
            swap_provider=swap_provider
        )

        logger.info(
            f"Order {order.id} created for tenant {tenant_id}: "
            f"{quantity}x {product.name} = {total_xmr} XMR "
            f"(paying in {payment_coin.upper()})"
        )

        self.db.log_action(
            action="order_created",
            tenant_id=tenant_id,
            details=f'{{"order_id": {order.id}, "product_id": {product_id}, '
                    f'"payment_coin": "{payment_coin}"}}'
        )

        return {
            "order_id": order.id,
            "product_name": product.name,
            "quantity": quantity,
            "total_xmr": str(total_xmr),
            "payment_coin": payment_coin.upper(),
            "payment_amount": str(payment_amount),
            "payment_address": payment_address,
            "swap_id": swap_id,
            "message": self._format_payment_message(
                payment_coin, payment_amount, payment_address, total_xmr
            )
        }

    def _format_payment_message(
        self,
        coin: str,
        amount: Decimal,
        address: str,
        xmr_equivalent: Decimal
    ) -> str:
        """Format payment instructions for the customer."""
        coin_upper = coin.upper()

        if coin == "xmr":
            return (
                f"Please send exactly {amount} XMR to:\n\n"
                f"`{address}`\n\n"
                f"Your order will be processed once payment is confirmed."
            )
        else:
            return (
                f"Please send {amount} {coin_upper} to:\n\n"
                f"`{address}`\n\n"
                f"This will be automatically converted to {xmr_equivalent} XMR.\n"
                f"Your order will be processed once the swap is complete."
            )

    async def check_order_payment(self, order_id: int, tenant_id: str) -> dict:
        """Check payment status for an order."""
        order = self.db.get_order(order_id, tenant_id)
        if not order:
            raise ValueError("Order not found")

        # Handle both enum and string states (SQLModel stores as string)
        state_value = order.state.value if hasattr(order.state, 'value') else order.state
        swap_status_value = None
        if order.swap_id:
            swap_status_value = order.swap_status.value if hasattr(order.swap_status, 'value') else order.swap_status

        result = {
            "order_id": order_id,
            "state": state_value,
            "payment_coin": order.payment_coin,
            "swap_status": swap_status_value
        }

        # If order has a swap, check swap status
        order_state_str = order.state.value if hasattr(order.state, 'value') else order.state
        if order.swap_id and order_state_str == OrderState.SWAP_PENDING.value:
            swap_status = await self.swap_service.check_swap_status(
                order.swap_id,
                order.swap_provider
            )

            # Update order based on swap status
            self.db.update_order_swap_status(order_id, SwapState(swap_status.value))

            result["swap_status"] = swap_status.value
            if swap_status.value == "complete":
                result["state"] = OrderState.PAID.value
                result["message"] = "Payment received! Order is being processed."
            elif swap_status.value in ["failed", "expired"]:
                result["state"] = OrderState.CANCELLED.value
                result["message"] = "Payment failed or expired."
            else:
                result["message"] = f"Swap in progress: {swap_status.value}"

        return result

    async def process_pending_swaps(self) -> dict:
        """Process all pending swap orders (background task)."""
        results = {
            "checked": 0,
            "completed": 0,
            "failed": 0
        }

        pending_orders = self.db.get_pending_swap_orders()

        for order in pending_orders:
            results["checked"] += 1

            if not order.swap_id:
                continue

            try:
                swap_status = await self.swap_service.check_swap_status(
                    order.swap_id,
                    order.swap_provider
                )

                self.db.update_order_swap_status(order.id, SwapState(swap_status.value))

                if swap_status.value == "complete":
                    results["completed"] += 1
                    logger.info(f"Order {order.id} swap completed")
                elif swap_status.value in ["failed", "expired"]:
                    results["failed"] += 1
                    logger.warning(f"Order {order.id} swap {swap_status.value}")

            except Exception as e:
                logger.error(f"Error checking swap for order {order.id}: {e}")

        return results

    def mark_order_fulfilled(self, order_id: int, tenant_id: str) -> Optional[TenantOrder]:
        """Mark an order as fulfilled."""
        order = self.db.update_order_state(
            order_id, tenant_id, OrderState.FULFILLED
        )

        if order:
            self.db.log_action(
                action="order_fulfilled",
                tenant_id=tenant_id,
                details=f'{{"order_id": {order_id}}}'
            )
            logger.info(f"Order {order_id} fulfilled")

        return order

    def cancel_order(self, order_id: int, tenant_id: str) -> Optional[TenantOrder]:
        """Cancel an order and restore inventory."""
        order = self.db.get_order(order_id, tenant_id)
        if not order:
            return None

        # Restore inventory
        if order.product_id:
            product = self.db.get_product(order.product_id, tenant_id)
            if product:
                self.db.update_product(
                    order.product_id,
                    tenant_id,
                    inventory=product.inventory + order.quantity
                )

        # Update order state
        order = self.db.update_order_state(
            order_id, tenant_id, OrderState.CANCELLED
        )

        if order:
            self.db.log_action(
                action="order_cancelled",
                tenant_id=tenant_id,
                details=f'{{"order_id": {order_id}}}'
            )
            logger.info(f"Order {order_id} cancelled")

        return order

    def get_order_delivery_address(
        self,
        order_id: int,
        tenant_id: str,
        encryption_key: str
    ) -> Optional[str]:
        """Get decrypted delivery address for an order."""
        order = self.db.get_order(order_id, tenant_id)
        if not order:
            return None

        try:
            return decrypt_address(order.address_encrypted, encryption_key)
        except Exception as e:
            logger.error(f"Failed to decrypt address for order {order_id}: {e}")
            return None

    def get_orders(
        self,
        tenant_id: str,
        state: Optional[OrderState] = None
    ) -> list[TenantOrder]:
        """Get orders for a tenant."""
        return self.db.get_orders(tenant_id, state)

    def get_order(self, order_id: int, tenant_id: str) -> Optional[TenantOrder]:
        """Get a specific order."""
        return self.db.get_order(order_id, tenant_id)
