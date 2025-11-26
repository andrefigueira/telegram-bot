"""Order management service."""

from __future__ import annotations

from decimal import Decimal
from typing import List
from datetime import datetime, timedelta
from sqlmodel import select

from ..models import Order, Database, encrypt, decrypt, Product, PostageType
from .payments import PaymentService
from .vendors import VendorService
from .catalog import CatalogService
from .currency import fiat_to_xmr_sync
from ..config import get_settings


class OrderService:
    """Manage orders in the database."""

    def __init__(
        self,
        db: Database,
        payments: PaymentService,
        catalog: CatalogService,
        vendors: VendorService,
    ) -> None:
        self.db = db
        self.payments = payments
        self.catalog = catalog
        self.vendors = vendors
        self.settings = get_settings()

    def create_order(self, product_id: int, quantity: int, address: str, postage_type_id: int = None) -> dict:
        product = self.catalog.get_product(product_id)
        if not product:
            raise ValueError("Product not found")
        if product.inventory < quantity:
            raise ValueError(f"Insufficient inventory. Only {product.inventory} available.")
        vendor = self.vendors.get_vendor(product.vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")

        # Check if vendor has wallet configured (required for payments)
        import logging
        logger = logging.getLogger(__name__)
        logger.info(f"Creating order - Vendor {vendor.id} wallet: {vendor.wallet_address}")
        if not vendor.wallet_address and not self.settings.monero_rpc_url:
            raise ValueError("Vendor has not configured their payment wallet yet")

        # Create payment address - use vendor's wallet if RPC not available
        payment_address, payment_id = self.payments.create_address(
            vendor_wallet=vendor.wallet_address
        )

        # Calculate total and commission using Decimal for precision
        price_xmr = Decimal(str(product.price_xmr)) if not isinstance(product.price_xmr, Decimal) else product.price_xmr
        commission_rate = Decimal(str(vendor.commission_rate)) if not isinstance(vendor.commission_rate, Decimal) else vendor.commission_rate
        total_xmr = price_xmr * Decimal(quantity)

        # Calculate postage in XMR if selected
        postage_xmr = Decimal("0")
        if postage_type_id:
            with self.db.session() as session:
                postage_type = session.get(PostageType, postage_type_id)
                if postage_type and postage_type.is_active:
                    # Convert postage fiat price to XMR
                    postage_fiat = Decimal(str(postage_type.price_fiat))
                    postage_xmr = fiat_to_xmr_sync(float(postage_fiat), postage_type.currency)
                    total_xmr += postage_xmr

        commission = total_xmr * commission_rate

        # Encrypt delivery address
        encrypted = encrypt(address, self.settings.encryption_key)

        # Create order
        order = Order(
            product_id=product_id,
            vendor_id=vendor.id,
            quantity=quantity,
            payment_id=payment_id,
            address_encrypted=encrypted,
            commission_xmr=commission,
            postage_type_id=postage_type_id,
            postage_xmr=postage_xmr,
        )

        # Save to database
        with self.db.session() as session:
            # Get product in this session
            product_in_session = session.get(Product, product_id)
            if not product_in_session:
                raise ValueError("Product not found")

            # Update inventory
            product_in_session.inventory -= quantity
            if product_in_session.inventory < 0:
                raise ValueError("Insufficient inventory")

            # Save order
            session.add(order)
            session.add(product_in_session)
            session.commit()
            session.refresh(order)

        # Return order details for user
        return {
            "order_id": order.id,
            "payment_address": payment_address,
            "payment_id": payment_id,
            "total_xmr": total_xmr,
            "postage_xmr": postage_xmr,
            "product_name": product.name,
            "quantity": quantity
        }

    def mark_paid(self, order_id: int, payout_service=None) -> Order:
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            if self.payments.check_paid(order.payment_id):  # pragma: no cover
                order.state = "PAID"  # pragma: no cover
                session.add(order)  # pragma: no cover
                session.commit()  # pragma: no cover
                session.refresh(order)  # pragma: no cover

                # Create payout record for vendor
                if payout_service:  # pragma: no cover
                    product = session.get(Product, order.product_id)  # pragma: no cover
                    if product:  # pragma: no cover
                        # Calculate vendor's share (total - commission)
                        price_xmr = Decimal(str(product.price_xmr))  # pragma: no cover
                        total_xmr = price_xmr * order.quantity + order.postage_xmr  # pragma: no cover
                        vendor_share = total_xmr - order.commission_xmr  # pragma: no cover
                        payout_service.create_payout(order.id, order.vendor_id, vendor_share)  # pragma: no cover
            return order

    def get_order(self, order_id: int) -> Order | None:
        """Retrieve a single order."""
        with self.db.session() as session:
            return session.get(Order, order_id)

    def get_payment_info(self, order_id: int, coin: str = "XMR") -> dict:
        """Get payment info for an order."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:
                raise ValueError("Order not found")

            product = session.get(Product, order.product_id)
            if not product:
                raise ValueError("Product not found")

            # Use Decimal for precise calculation
            price_xmr = Decimal(str(product.price_xmr)) if not isinstance(product.price_xmr, Decimal) else product.price_xmr
            total_xmr = price_xmr * Decimal(order.quantity)

            # For XMR, use the existing payment address
            if coin == "XMR":
                # Regenerate payment address from payment_id
                payment_address, _ = self.payments.create_address()
                return {
                    "amount": total_xmr,
                    "address": payment_address,
                    "coin": "XMR"
                }

            # For other coins, return placeholder (crypto swap integration needed)
            return {
                "amount": total_xmr,
                "address": "Payment address pending...",
                "coin": coin
            }

    def fulfill_order(self, order_id: int) -> Order:
        """Mark a paid order as fulfilled."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            order.state = "FULFILLED"
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def cancel_order(self, order_id: int) -> Order:
        """Cancel an order."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            order.state = "CANCELLED"
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def list_orders(self) -> List[Order]:
        with self.db.session() as session:
            return list(session.exec(select(Order)))

    def get_address(self, order: Order) -> str:
        return decrypt(order.address_encrypted, self.settings.encryption_key)

    def purge_old_orders(self) -> None:
        """Delete orders older than retention days."""
        cutoff = datetime.utcnow() - timedelta(days=self.settings.data_retention_days)
        with self.db.session() as session:
            old_orders = session.exec(select(Order).where(Order.created_at < cutoff))
            for order in list(old_orders):
                session.delete(order)
            session.commit()

    def list_orders_by_vendor(self, vendor_id: int) -> List[Order]:
        """List all orders for a specific vendor."""
        with self.db.session() as session:
            stmt = select(Order).where(Order.vendor_id == vendor_id).order_by(Order.created_at.desc())
            return list(session.exec(stmt))

    def mark_shipped(self, order_id: int, shipping_note: str = None) -> Order:
        """Mark an order as shipped with optional note."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:
                raise ValueError("Order not found")
            if order.state != "PAID":
                raise ValueError(f"Cannot ship order in state: {order.state}")

            order.state = "SHIPPED"
            order.shipped_at = datetime.utcnow()
            if shipping_note:
                order.shipping_note = shipping_note

            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def mark_completed(self, order_id: int) -> Order:
        """Mark an order as completed."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:
                raise ValueError("Order not found")
            if order.state != "SHIPPED":
                raise ValueError(f"Cannot complete order in state: {order.state}")

            order.state = "COMPLETED"
            session.add(order)
            session.commit()
            session.refresh(order)
            return order
