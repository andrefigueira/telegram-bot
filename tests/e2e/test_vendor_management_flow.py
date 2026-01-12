"""
E2E Tests: Vendor Management Flow

Tests the complete vendor journey from onboarding to order fulfillment.
"""

import pytest
import tempfile
import os
import base64
from decimal import Decimal
from unittest.mock import patch

from bot.models import Database, Product, Vendor
from bot.services.vendors import VendorService
from bot.services.catalog import CatalogService
from bot.services.orders import OrderService
from bot.services.postage import PostageService
from bot.services.payments import PaymentService
from bot.config import Settings


@pytest.fixture
def mock_settings(monkeypatch):
    """Set up mock settings with valid encryption key."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
        monero_rpc_url="",
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)
    return settings


class TestVendorOnboardingFlow:
    """
    E2E Test: Vendor onboarding journey.

    Flow tested:
    1. Vendor registers
    2. Vendor sets wallet address
    3. Vendor sets pricing currency
    4. Vendor sets shop name
    5. Vendor configures payment methods
    """

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(url=f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendor_service(self, db):
        """Initialize vendor service."""
        return VendorService(db)

    def test_complete_vendor_onboarding(self, vendor_service):
        """Test complete vendor onboarding process."""
        # Step 1: Register as vendor
        vendor = vendor_service.add_vendor(Vendor(
            telegram_id=1001,
            name="New Vendor"
        ))

        assert vendor is not None
        assert vendor.telegram_id == 1001

        # Step 2: Set wallet address
        valid_wallet = "4" + "A" * 94  # Valid XMR address
        vendor_service.update_settings(vendor.id, wallet_address=valid_wallet)

        updated = vendor_service.get_vendor(vendor.id)
        assert updated.wallet_address == valid_wallet

        # Step 3: Set pricing currency
        vendor_service.update_settings(vendor.id, pricing_currency="USD")

        updated = vendor_service.get_vendor(vendor.id)
        assert updated.pricing_currency == "USD"

        # Step 4: Set shop name
        vendor_service.update_settings(vendor.id, shop_name="My Awesome Shop")

        updated = vendor_service.get_vendor(vendor.id)
        assert updated.shop_name == "My Awesome Shop"

        # Step 5: Set accepted payments
        vendor_service.update_settings(vendor.id, accepted_payments=["XMR", "BTC", "ETH"])

        updated = vendor_service.get_vendor(vendor.id)
        assert "XMR" in updated.accepted_payments
        assert "BTC" in updated.accepted_payments
        assert "ETH" in updated.accepted_payments

    def test_vendor_lookup_by_telegram_id(self, vendor_service):
        """Test looking up vendor by Telegram ID."""
        vendor = vendor_service.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor"
        ))

        found = vendor_service.get_by_telegram_id(1001)
        assert found is not None
        assert found.id == vendor.id

    def test_vendor_wallet_update(self, vendor_service):
        """Test that wallet addresses are stored correctly."""
        vendor = vendor_service.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor"
        ))

        # Set valid XMR wallet (starts with 4 or 8, 95 chars)
        valid_wallet = "4" + "A" * 94
        vendor_service.update_settings(vendor.id, wallet_address=valid_wallet)

        updated = vendor_service.get_vendor(vendor.id)
        assert updated.wallet_address == valid_wallet

    def test_vendor_payment_methods_update(self, vendor_service):
        """Test updating payment methods."""
        vendor = vendor_service.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor"
        ))

        # Enable multiple payment methods
        vendor_service.update_settings(vendor.id, accepted_payments=["XMR", "BTC", "ETH", "USDT"])

        updated = vendor_service.get_vendor(vendor.id)
        assert "XMR" in updated.accepted_payments
        assert "BTC" in updated.accepted_payments
        assert "ETH" in updated.accepted_payments
        assert "USDT" in updated.accepted_payments

    def test_vendor_commission_setting(self, vendor_service):
        """Test setting vendor commission rate."""
        vendor = vendor_service.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor"
        ))

        vendor_service.set_commission(vendor.id, 0.05)

        updated = vendor_service.get_vendor(vendor.id)
        assert float(updated.commission_rate) == 0.05


class TestProductManagementFlow:
    """
    E2E Test: Product management by vendor.

    Flow tested:
    1. Add new product
    2. Update product details
    3. Manage inventory
    4. Delete product
    """

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(url=f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendor_with_service(self, db):
        """Create a vendor with associated services."""
        vendors = VendorService(db)
        catalog = CatalogService(db)

        vendor = vendors.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor",
            wallet_address="4" + "A" * 94,
            pricing_currency="USD"
        ))

        return vendor, vendors, catalog

    def test_add_product_flow(self, vendor_with_service):
        """Test adding a new product."""
        vendor, vendors, catalog = vendor_with_service

        # Add product
        product = catalog.add_product(Product(
            name="New Product",
            description="A great new product",
            category="Electronics",
            price_xmr=Decimal("2.5"),
            price_fiat=Decimal("250.00"),
            currency="USD",
            inventory=50,
            vendor_id=vendor.id
        ))

        assert product.id is not None
        assert product.name == "New Product"
        assert product.inventory == 50

        # Verify product is in vendor's catalog
        products = catalog.list_products_by_vendor(vendor.id)
        assert len(products) == 1
        assert products[0].id == product.id

    def test_update_product_details(self, vendor_with_service):
        """Test updating product details."""
        vendor, vendors, catalog = vendor_with_service

        # Create product
        product = catalog.add_product(Product(
            name="Original Name",
            description="Original description",
            category="Test",
            price_xmr=Decimal("1.0"),
            inventory=10,
            vendor_id=vendor.id
        ))

        # Update product
        product.name = "Updated Name"
        product.description = "Updated description"
        product.price_xmr = Decimal("1.5")
        catalog.update_product(product)

        # Verify update
        updated = catalog.get_product(product.id)
        assert updated.name == "Updated Name"
        assert updated.description == "Updated description"
        assert updated.price_xmr == Decimal("1.5")

    def test_manage_inventory(self, vendor_with_service):
        """Test inventory management."""
        vendor, vendors, catalog = vendor_with_service

        # Create product with inventory
        product = catalog.add_product(Product(
            name="Inventory Test",
            description="Test",
            category="Test",
            price_xmr=Decimal("1.0"),
            inventory=100,
            vendor_id=vendor.id
        ))

        # Update inventory
        product.inventory = 50
        catalog.update_product(product)

        updated = catalog.get_product(product.id)
        assert updated.inventory == 50

    def test_delete_product(self, vendor_with_service):
        """Test deleting a product."""
        vendor, vendors, catalog = vendor_with_service

        # Create product
        product = catalog.add_product(Product(
            name="To Delete",
            description="This will be deleted",
            category="Test",
            price_xmr=Decimal("1.0"),
            inventory=10,
            vendor_id=vendor.id
        ))

        product_id = product.id

        # Delete product
        catalog.delete_product(product_id)

        # Verify deletion
        deleted = catalog.get_product(product_id)
        assert deleted is None

    def test_product_currency_conversion(self, vendor_with_service):
        """Test that fiat prices are stored alongside XMR prices."""
        vendor, vendors, catalog = vendor_with_service

        # Create product with both prices
        product = catalog.add_product(Product(
            name="Dual Price",
            description="Has both fiat and XMR prices",
            category="Test",
            price_xmr=Decimal("0.5"),
            price_fiat=Decimal("75.00"),
            currency="USD",
            inventory=10,
            vendor_id=vendor.id
        ))

        fetched = catalog.get_product(product.id)
        assert fetched.price_xmr == Decimal("0.5")
        assert fetched.price_fiat == Decimal("75.00")
        assert fetched.currency == "USD"

    def test_search_products(self, vendor_with_service):
        """Test searching for products."""
        vendor, vendors, catalog = vendor_with_service

        # Create multiple products
        catalog.add_product(Product(
            name="Blue Widget",
            description="A blue widget",
            category="Widgets",
            price_xmr=Decimal("1.0"),
            inventory=10,
            vendor_id=vendor.id
        ))
        catalog.add_product(Product(
            name="Red Gadget",
            description="A red gadget",
            category="Gadgets",
            price_xmr=Decimal("2.0"),
            inventory=5,
            vendor_id=vendor.id
        ))

        # Search by name
        found = catalog.search("Widget")
        assert len(found) == 1
        assert found[0].name == "Blue Widget"

        # Search by category
        found = catalog.search("Gadgets")
        assert len(found) == 1
        assert found[0].name == "Red Gadget"


class TestPostageManagementFlow:
    """
    E2E Test: Postage/shipping option management.

    Flow tested:
    1. Add postage option
    2. Update postage details
    3. Toggle active/inactive
    4. Delete postage option
    """

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(url=f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendor_with_postage(self, db):
        """Create a vendor with postage service."""
        vendors = VendorService(db)
        postage = PostageService(db)

        vendor = vendors.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor",
            pricing_currency="USD"
        ))

        return vendor, postage

    def test_add_postage_option(self, vendor_with_postage):
        """Test adding a postage option."""
        vendor, postage = vendor_with_postage

        option = postage.add_postage_type(
            vendor_id=vendor.id,
            name="Standard Shipping",
            price_fiat=Decimal("5.00"),
            currency="USD",
            description="5-7 business days"
        )

        assert option.id is not None
        assert option.name == "Standard Shipping"
        assert option.price_fiat == Decimal("5.00")
        assert option.is_active is True

    def test_list_vendor_postage_options(self, vendor_with_postage):
        """Test listing postage options for a vendor."""
        vendor, postage = vendor_with_postage

        # Add multiple options
        postage.add_postage_type(vendor.id, "Standard", Decimal("5.00"), "USD", "5-7 days")
        postage.add_postage_type(vendor.id, "Express", Decimal("15.00"), "USD", "1-2 days")
        postage.add_postage_type(vendor.id, "Overnight", Decimal("25.00"), "USD", "Next day")

        # List options
        options = postage.list_by_vendor(vendor.id)
        assert len(options) == 3

    def test_update_postage_option(self, vendor_with_postage):
        """Test updating a postage option."""
        vendor, postage = vendor_with_postage

        option = postage.add_postage_type(
            vendor.id, "Original", Decimal("10.00"), "USD", "Original description"
        )

        # Update using kwargs
        postage.update_postage_type(
            option.id,
            name="Updated",
            price_fiat=Decimal("12.00"),
            description="Updated description"
        )

        updated = postage.get_postage_type(option.id)
        assert updated.name == "Updated"
        assert updated.price_fiat == Decimal("12.00")
        assert updated.description == "Updated description"

    def test_toggle_postage_active(self, vendor_with_postage):
        """Test toggling postage active status."""
        vendor, postage = vendor_with_postage

        option = postage.add_postage_type(
            vendor.id, "Toggle Test", Decimal("5.00"), "USD", "Test"
        )
        assert option.is_active is True

        # Toggle to deactivate
        postage.toggle_active(option.id)
        updated = postage.get_postage_type(option.id)
        assert updated.is_active is False

        # Toggle to reactivate
        postage.toggle_active(option.id)
        updated = postage.get_postage_type(option.id)
        assert updated.is_active is True

    def test_delete_postage_option(self, vendor_with_postage):
        """Test deleting a postage option."""
        vendor, postage = vendor_with_postage

        option = postage.add_postage_type(
            vendor.id, "To Delete", Decimal("5.00"), "USD", "Will be deleted"
        )

        postage.delete_postage_type(option.id)

        deleted = postage.get_postage_type(option.id)
        assert deleted is None


class TestVendorOrderManagementFlow:
    """
    E2E Test: Vendor managing orders.

    Flow tested:
    1. View incoming orders
    2. View order details
    3. Mark order as shipped
    4. Mark order as completed
    """

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(url=f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendor_with_orders(self, db, mock_settings):
        """Create a vendor with products and orders."""
        vendors = VendorService(db)
        catalog = CatalogService(db)
        payments = PaymentService()
        orders = OrderService(db, payments, catalog, vendors)

        vendor = vendors.add_vendor(Vendor(
            telegram_id=1001,
            name="Test Vendor",
            wallet_address="4" + "A" * 94
        ))

        product = catalog.add_product(Product(
            name="Test Product",
            description="Test",
            category="Test",
            price_xmr=Decimal("1.0"),
            inventory=100,
            vendor_id=vendor.id
        ))

        # Create multiple orders
        result1 = orders.create_order(
            product_id=product.id,
            quantity=2,
            address="Address 1"
        )

        result2 = orders.create_order(
            product_id=product.id,
            quantity=3,
            address="Address 2"
        )

        return vendor, product, [result1, result2], orders

    def test_list_vendor_orders(self, vendor_with_orders):
        """Test listing orders for a vendor."""
        vendor, product, created_orders, orders = vendor_with_orders

        vendor_orders = orders.list_orders_by_vendor(vendor.id)
        assert len(vendor_orders) == 2

    def test_view_order_details(self, vendor_with_orders):
        """Test viewing order details."""
        vendor, product, created_orders, orders = vendor_with_orders

        order = orders.get_order(created_orders[0]["order_id"])
        assert order is not None
        assert order.product_id == product.id
        assert order.quantity == 2

    def test_mark_order_shipped(self, vendor_with_orders):
        """Test marking an order as shipped."""
        vendor, product, created_orders, orders = vendor_with_orders

        order_id = created_orders[0]["order_id"]

        # First pay the order
        with orders.db.session() as session:
            from bot.models import Order
            order = session.get(Order, order_id)
            order.state = "PAID"
            session.add(order)
            session.commit()

        # Then ship it
        orders.mark_shipped(order_id, "Tracking: SHIP123")

        updated = orders.get_order(order_id)
        assert updated.state == 'SHIPPED'
        assert updated.shipping_note == "Tracking: SHIP123"
        assert updated.shipped_at is not None

    def test_mark_order_completed(self, vendor_with_orders):
        """Test marking an order as completed."""
        vendor, product, created_orders, orders = vendor_with_orders

        order_id = created_orders[0]["order_id"]

        # Progress through states
        with orders.db.session() as session:
            from bot.models import Order
            order = session.get(Order, order_id)
            order.state = "PAID"
            session.add(order)
            session.commit()

        orders.mark_shipped(order_id)
        orders.mark_completed(order_id)

        updated = orders.get_order(order_id)
        assert updated.state == 'COMPLETED'

    def test_filter_orders_by_state(self, vendor_with_orders):
        """Test filtering orders by state."""
        vendor, product, created_orders, orders = vendor_with_orders

        # Initially all orders are 'new'
        all_orders = orders.list_orders_by_vendor(vendor.id)
        assert len(all_orders) == 2
        assert all(o.state.lower() == 'new' for o in all_orders)

    def test_get_order_address(self, vendor_with_orders):
        """Test that vendor can decrypt customer delivery address."""
        vendor, product, created_orders, orders = vendor_with_orders

        order_id = created_orders[0]["order_id"]

        # Get order
        order = orders.get_order(order_id)

        # Decrypt address
        address = orders.get_address(order)
        assert address == "Address 1"
