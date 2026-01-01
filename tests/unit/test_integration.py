"""Integration tests for the application."""

import pytest
from unittest.mock import MagicMock, patch
import base64
import os
from decimal import Decimal

from bot.models import Database, Product, Vendor, Order
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.services.orders import OrderService
from bot.services.payments import PaymentService
from bot.config import Settings


class TestIntegration:
    """Test integration between services."""

    @pytest.fixture
    def test_settings(self, monkeypatch):
        """Create test settings."""
        key = base64.b64encode(os.urandom(32)).decode()
        settings = Settings(
            telegram_token="test_token",
            admin_ids="123456789",
            super_admin_ids="987654321",
            monero_rpc_url="",
            encryption_key=key,
            data_retention_days=30,
            default_commission_rate=0.05,
            totp_secret=None,
            environment="development"
        )
        monkeypatch.setattr("bot.config.get_settings", lambda: settings)
        monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)
        monkeypatch.setattr("bot.services.payments.get_settings", lambda: settings)
        return settings

    @pytest.fixture
    def db(self, tmp_path):
        """Create test database."""
        return Database(url=f"sqlite:///{tmp_path}/test.db")

    def test_full_order_flow(self, db, test_settings):
        """Test complete order flow from product creation to order."""
        # Initialize services
        vendors = VendorService(db)
        catalog = CatalogService(db)
        payments = PaymentService()
        orders = OrderService(db, payments, catalog, vendors)
        
        # Create vendor with wallet address
        vendor = vendors.add_vendor(
            Vendor(telegram_id=123456789, name="Test Store", wallet_address="4ATestWalletAddress123")
        )
        assert vendor.id is not None

        # Create product
        product = catalog.add_product(
            Product(
                name="Test Product",
                description="A test product",
                category="Electronics",
                price_xmr=1.5,
                media_id=None,
                inventory=10,
                vendor_id=vendor.id
            )
        )
        assert product.id is not None
        
        # Search for product
        found_products = catalog.search("Test")
        assert len(found_products) == 1
        assert found_products[0].id == product.id
        
        # Create order
        order_data = orders.create_order(
            product_id=product.id,
            quantity=2,
            address="123 Test Street, Test City"
        )
        
        # Verify order data
        assert order_data["order_id"] is not None
        assert order_data["total_xmr"] == Decimal("3.0")  # 1.5 * 2
        assert order_data["quantity"] == 2
        assert order_data["payment_address"] is not None
        assert order_data["payment_id"] is not None

        # Verify inventory updated
        updated_product = catalog.get_product(product.id)
        assert updated_product.inventory == 8  # 10 - 2

        # Get order details
        order = orders.get_order(order_data["order_id"])
        assert order is not None
        assert order.state == "NEW"
        assert order.commission_xmr == Decimal("0.15")  # 3.0 * 0.05

        # Verify encrypted address
        decrypted_address = orders.get_address(order)
        assert decrypted_address == "123 Test Street, Test City"

        # In development mode, check_paid returns False, so mark_paid won't change state
        # Instead, manually verify the order can be fulfilled
        order = orders.fulfill_order(order.id)
        assert order.state == "FULFILLED"

    def test_vendor_commission_flow(self, db, test_settings):
        """Test vendor commission calculation."""
        vendors = VendorService(db)
        catalog = CatalogService(db)
        payments = PaymentService()
        orders = OrderService(db, payments, catalog, vendors)

        # Create vendor with custom commission and wallet
        vendor = vendors.add_vendor(
            Vendor(telegram_id=111222333, name="Premium Store", wallet_address="4APremiumWallet123")
        )

        # Set custom commission rate
        updated_vendor = vendors.set_commission(vendor.id, 0.10)
        assert updated_vendor.commission_rate == Decimal("0.10")

        # Create product
        product = catalog.add_product(
            Product(
                name="Premium Product",
                description="",
                price_xmr=Decimal("10.0"),
                inventory=5,
                vendor_id=vendor.id
            )
        )

        # Create order
        order_data = orders.create_order(product.id, 1, "address")

        # Verify commission
        order = orders.get_order(order_data["order_id"])
        assert order.commission_xmr == Decimal("1.0")  # 10.0 * 0.10

    def test_inventory_management(self, db, test_settings):
        """Test inventory tracking and limits."""
        vendors = VendorService(db)
        catalog = CatalogService(db)
        payments = PaymentService()
        orders = OrderService(db, payments, catalog, vendors)

        # Setup - vendor with wallet
        vendor = vendors.add_vendor(Vendor(telegram_id=123, name="Store", wallet_address="4AInventoryWallet123"))
        product = catalog.add_product(
            Product(
                name="Limited Product",
                description="",
                price_xmr=Decimal("1.0"),
                inventory=2,
                vendor_id=vendor.id
            )
        )
        
        # Order 1 item - should succeed
        order1 = orders.create_order(product.id, 1, "addr1")
        assert order1["order_id"] is not None
        
        # Try to order 2 more items - should fail
        with pytest.raises(ValueError, match="Insufficient inventory"):
            orders.create_order(product.id, 2, "addr2")
        
        # Order last item - should succeed
        order2 = orders.create_order(product.id, 1, "addr2")
        assert order2["order_id"] is not None
        
        # Verify inventory is depleted
        updated_product = catalog.get_product(product.id)
        assert updated_product.inventory == 0