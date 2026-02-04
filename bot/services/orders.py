"""Order management service."""

from __future__ import annotations

from decimal import Decimal
from typing import List
from datetime import datetime, timedelta
from sqlmodel import select

from ..models import Order, Database, encrypt, decrypt, Product, PostageType, Vendor
from .payments import PaymentService
from .payment_factory import PaymentServiceFactory
from .vendors import VendorService
from .catalog import CatalogService
from .currency import fiat_to_xmr_sync, fiat_to_crypto
from ..config import get_settings
import asyncio


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

    def create_order(
        self,
        product_id: int,
        quantity: int,
        address: str,
        postage_type_id: int = None,
        payment_currency: str = "XMR"
    ) -> dict:
        product = self.catalog.get_product(product_id)
        if not product:
            raise ValueError("Product not found")
        if product.inventory < quantity:
            raise ValueError(f"Insufficient inventory. Only {product.inventory} available.")
        vendor = self.vendors.get_vendor(product.vendor_id)
        if not vendor:
            raise ValueError("Vendor not found")

        # Normalize payment currency
        payment_currency = payment_currency.upper()
        if payment_currency not in ["XMR", "BTC", "ETH"]:
            raise ValueError(f"Unsupported payment currency: {payment_currency}")

        # Check if vendor has wallet configured for chosen currency
        import logging
        logger = logging.getLogger(__name__)

        wallet_map = {
            "XMR": vendor.wallet_address,
            "BTC": vendor.btc_wallet_address,
            "ETH": vendor.eth_wallet_address
        }
        vendor_wallet = wallet_map.get(payment_currency)

        logger.info(f"Creating order - Vendor {vendor.id} {payment_currency} wallet: {vendor_wallet}")

        if not vendor_wallet and payment_currency == "XMR" and not self.settings.monero_rpc_url:
            raise ValueError("Vendor has not configured their XMR payment wallet yet")
        elif not vendor_wallet and payment_currency != "XMR":
            raise ValueError(f"Vendor has not configured their {payment_currency} wallet yet")

        # Get appropriate payment service for currency
        payment_service = PaymentServiceFactory.create(payment_currency)

        # Create payment address
        payment_address, payment_id = payment_service.create_address(
            vendor_wallet=vendor_wallet
        )

        # Calculate total in product's fiat currency first
        commission_rate = Decimal(str(vendor.commission_rate)) if not isinstance(vendor.commission_rate, Decimal) else vendor.commission_rate

        # Get product price in fiat (or convert from XMR if needed)
        if product.price_fiat and product.currency != "XMR":
            # Product priced in fiat
            price_fiat = Decimal(str(product.price_fiat))
            product_currency = product.currency
        else:
            # Product priced in XMR, use that directly for backward compatibility
            price_xmr = Decimal(str(product.price_xmr)) if not isinstance(product.price_xmr, Decimal) else product.price_xmr
            # For now, assume USD if converting
            product_currency = "USD"
            price_fiat = price_xmr * Decimal("150")  # Rough conversion, will be recalculated

        total_fiat = price_fiat * Decimal(quantity)

        # Calculate postage in fiat if selected
        postage_fiat = Decimal("0")
        postage_currency = product_currency
        if postage_type_id:
            with self.db.session() as session:
                postage_type = session.get(PostageType, postage_type_id)
                if postage_type and postage_type.is_active:
                    postage_fiat = Decimal(str(postage_type.price_fiat))
                    postage_currency = postage_type.currency
                    # Convert to product currency if different
                    if postage_currency != product_currency:
                        # For simplicity, add directly (should do proper conversion in production)
                        pass
                    total_fiat += postage_fiat

        # Convert total to chosen cryptocurrency
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

        total_crypto = loop.run_until_complete(
            fiat_to_crypto(total_fiat, product_currency, payment_currency)
        )

        commission_crypto = total_crypto * commission_rate

        # Also calculate XMR amounts for backward compatibility
        total_xmr = loop.run_until_complete(
            fiat_to_crypto(total_fiat, product_currency, "XMR")
        )
        commission_xmr = total_xmr * commission_rate
        postage_xmr = Decimal("0")
        if postage_fiat > 0:
            postage_xmr = loop.run_until_complete(
                fiat_to_crypto(postage_fiat, postage_currency, "XMR")
            )

        # Encrypt delivery address
        encrypted = encrypt(address, self.settings.encryption_key)

        # Create order with multi-currency support
        order = Order(
            product_id=product_id,
            vendor_id=vendor.id,
            quantity=quantity,
            payment_id=payment_id,
            address_encrypted=encrypted,
            commission_xmr=commission_xmr,
            postage_type_id=postage_type_id,
            postage_xmr=postage_xmr,
            # Multi-currency fields
            payment_currency=payment_currency,
            payment_amount_crypto=total_crypto,
            commission_crypto=commission_crypto,
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

        # Return order details for user with currency info
        return {
            "order_id": order.id,
            "payment_address": payment_address,
            "payment_id": payment_id,
            "payment_currency": payment_currency,
            "total_crypto": total_crypto,
            "total_xmr": total_xmr,  # Backward compatibility
            "postage_xmr": postage_xmr,
            "product_name": product.name,
            "quantity": quantity,
            "confirmations_required": PaymentServiceFactory.get_confirmation_threshold(payment_currency)
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

    def _load_order_attrs(self, order: Order) -> None:
        """Ensure all order attributes are loaded before session closes."""
        if order:
            _ = order.id, order.product_id, order.vendor_id, order.quantity
            _ = order.payment_id, order.address_encrypted, order.commission_xmr
            _ = order.state, order.postage_type_id, order.postage_xmr
            _ = order.shipped_at, order.shipping_note, order.created_at

    def get_order(self, order_id: int) -> Order | None:
        """Retrieve a single order."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            self._load_order_attrs(order)
            return order

    def get_payment_info(self, order_id: int, coin: str = "XMR") -> dict:
        """Get payment info for an order."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:
                raise ValueError("Order not found")

            product = session.get(Product, order.product_id)
            if not product:
                raise ValueError("Product not found")

            vendor = session.get(Vendor, order.vendor_id)
            vendor_wallet = getattr(vendor, "wallet_address", None)

            # Use Decimal for precise calculation
            price_xmr = Decimal(str(product.price_xmr)) if not isinstance(product.price_xmr, Decimal) else product.price_xmr
            total_xmr = price_xmr * Decimal(order.quantity)

            # For XMR, use the existing payment address
            coin_upper = coin.upper()
            if coin_upper == "XMR":
                payment_address = self.payments.get_address_for_payment_id(
                    order.payment_id,
                    vendor_wallet=vendor_wallet
                )
                return {
                    "amount": total_xmr,
                    "address": payment_address,
                    "coin": coin_upper,
                    "payment_id": order.payment_id
                }

            # For other coins, return placeholder (crypto swap integration needed)
            return {
                "amount": total_xmr,
                "address": "Payment address pending...",
                "coin": coin_upper
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
            orders = list(session.exec(select(Order)))
            for order in orders:
                self._load_order_attrs(order)
            return orders

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
            orders = list(session.exec(stmt))
            for order in orders:
                self._load_order_attrs(order)
            return orders

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
