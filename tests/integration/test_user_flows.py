"""Integration tests for user flows with real database operations.

These tests use a real SQLite database (not mocks) to verify
the complete user flows work correctly end-to-end.
"""

import pytest
import tempfile
import os
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch

from telegram import Update, Message, User, CallbackQuery, Chat

from bot.models import Database, Vendor, Product, Order
from bot.services.vendors import VendorService
from bot.services.catalog import CatalogService
from bot.services.orders import OrderService
from bot.services.postage import PostageService
from bot.services.payments import PaymentService
from bot.handlers.user import (
    handle_menu_callback,
    handle_setup_callback,
    handle_currency_callback,
    handle_payment_toggle_callback,
    handle_postage_callback,
    handle_products_callback,
    handle_product_callback,
    handle_order_callback,
    handle_text_input,
)
from bot.handlers.admin import (
    handle_admin_callback,
    handle_admin_text_input,
    handle_vendor_callback,
)


class TestVendorSetupFlow:
    """Integration tests for vendor setup flow."""

    @pytest.fixture
    def db(self):
        """Create a real test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendors(self, db):
        """Create real vendor service."""
        return VendorService(db)

    @pytest.fixture
    def catalog(self, db):
        """Create real catalog service."""
        return CatalogService(db)

    @pytest.fixture
    def postage(self, db):
        """Create real postage service."""
        return PostageService(db)

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 123456789
        user.username = "testuser"
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_message_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message

        user = MagicMock(spec=User)
        user.id = 123456789
        user.username = "testuser"
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_complete_vendor_setup_flow(self, db, vendors, postage, mock_update, mock_message_update, mock_context):
        """Test complete vendor setup: become vendor -> set wallet -> set currency."""
        user_id = mock_update.effective_user.id

        # Step 1: Become a vendor
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)

        # Verify vendor was created in database
        vendor = vendors.get_by_telegram_id(user_id)
        assert vendor is not None
        assert vendor.telegram_id == user_id

        # Step 2: Set wallet address
        mock_context.user_data['awaiting_input'] = 'wallet'
        wallet_address = "4" + "A" * 94  # Valid XMR address format
        mock_message_update.message.text = wallet_address

        await handle_text_input(mock_message_update, mock_context, vendors=vendors)

        # Verify wallet was saved
        vendor = vendors.get_by_telegram_id(user_id)
        assert vendor.wallet_address == wallet_address

        # Step 3: Set currency to GBP
        mock_update.callback_query.data = "curr:select:GBP"
        await handle_currency_callback(mock_update, mock_context, vendors=vendors)

        # Verify currency was saved
        vendor = vendors.get_by_telegram_id(user_id)
        assert vendor.pricing_currency == "GBP"

        # Step 4: View settings to confirm everything saved
        mock_update.callback_query.data = "setup:view"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)

        # Check the message contains our settings
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert "GBP" in message_text
        assert "Vendor:" in message_text

    @pytest.mark.asyncio
    async def test_vendor_setup_with_shop_name(self, db, vendors, mock_update, mock_message_update, mock_context):
        """Test setting shop name."""
        user_id = mock_update.effective_user.id

        # First become a vendor
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)

        # Set shop name
        mock_update.callback_query.data = "setup:shopname"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)
        assert mock_context.user_data['awaiting_input'] == 'shopname'

        # Enter shop name
        mock_message_update.message.text = "My Awesome Shop"
        await handle_text_input(mock_message_update, mock_context, vendors=vendors)

        # Verify shop name was saved
        vendor = vendors.get_by_telegram_id(user_id)
        assert vendor.shop_name == "My Awesome Shop"

    @pytest.mark.asyncio
    async def test_payment_methods_toggle(self, db, vendors, mock_update, mock_context):
        """Test toggling payment methods on and off."""
        user_id = mock_update.effective_user.id

        # Become vendor first
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)

        # Enable BTC
        mock_update.callback_query.data = "pay:toggle:BTC"
        await handle_payment_toggle_callback(mock_update, mock_context, vendors=vendors)

        vendor = vendors.get_by_telegram_id(user_id)
        payments = vendors.get_accepted_payments_list(vendor)
        assert "BTC" in payments
        assert "XMR" in payments  # XMR always enabled

        # Enable ETH
        mock_update.callback_query.data = "pay:toggle:ETH"
        await handle_payment_toggle_callback(mock_update, mock_context, vendors=vendors)

        vendor = vendors.get_by_telegram_id(user_id)
        payments = vendors.get_accepted_payments_list(vendor)
        assert "ETH" in payments

        # Disable BTC
        mock_update.callback_query.data = "pay:toggle:BTC"
        await handle_payment_toggle_callback(mock_update, mock_context, vendors=vendors)

        vendor = vendors.get_by_telegram_id(user_id)
        payments = vendors.get_accepted_payments_list(vendor)
        assert "BTC" not in payments
        assert "ETH" in payments


class TestProductManagementFlow:
    """Integration tests for product management."""

    @pytest.fixture
    def db(self):
        """Create a real test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendors(self, db):
        """Create real vendor service."""
        return VendorService(db)

    @pytest.fixture
    def catalog(self, db):
        """Create real catalog service."""
        return CatalogService(db)

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 123456789
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_message_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message

        user = MagicMock(spec=User)
        user.id = 123456789
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_add_product_flow(self, db, vendors, catalog, mock_update, mock_message_update, mock_context):
        """Test adding a product: name -> price -> stock -> description."""
        user_id = mock_update.effective_user.id

        # Setup: Create vendor first
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)

        vendor = vendors.get_by_telegram_id(user_id)

        # Step 1: Start adding product (patch _is_admin to allow test user)
        mock_update.callback_query.data = "admin:add_product"
        with patch('bot.handlers.admin._is_admin', return_value=True):
            await handle_admin_callback(mock_update, mock_context, vendors=vendors, catalog=catalog)
        assert mock_context.user_data['awaiting_input'] == 'product_name'

        # Step 2: Enter product name
        mock_message_update.message.text = "Test Widget"
        await handle_admin_text_input(mock_message_update, mock_context, vendors=vendors, catalog=catalog)
        assert mock_context.user_data['awaiting_input'] == 'product_price'
        assert mock_context.user_data['new_product']['name'] == "Test Widget"

        # Step 3: Enter price
        mock_message_update.message.text = "25.99"
        await handle_admin_text_input(mock_message_update, mock_context, vendors=vendors, catalog=catalog)
        assert mock_context.user_data['awaiting_input'] == 'product_stock'

        # Step 4: Enter stock
        mock_message_update.message.text = "100"
        await handle_admin_text_input(mock_message_update, mock_context, vendors=vendors, catalog=catalog)
        assert mock_context.user_data['awaiting_input'] == 'product_desc'

        # Step 5: Enter description
        mock_message_update.message.text = "A fantastic test widget"
        await handle_admin_text_input(mock_message_update, mock_context, vendors=vendors, catalog=catalog)

        # Verify product was created in database
        products = catalog.list_products_by_vendor(vendor.id)
        assert len(products) == 1
        product = products[0]
        assert product.name == "Test Widget"
        assert product.price_fiat == Decimal("25.99")  # Handler stores fiat price and converts to XMR
        assert product.price_xmr > 0  # XMR price is auto-calculated from fiat
        assert product.inventory == 100
        assert product.description == "A fantastic test widget"

    @pytest.mark.asyncio
    async def test_edit_product_flow(self, db, vendors, catalog, mock_update, mock_message_update, mock_context):
        """Test editing a product."""
        user_id = mock_update.effective_user.id

        # Setup: Create vendor and product
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)
        vendor = vendors.get_by_telegram_id(user_id)

        # Create product directly
        product = catalog.add_product(Product(
            vendor_id=vendor.id,
            name="Original Name",
            description="Test product",
            price_xmr=Decimal("10.00"),
            inventory=50
        ))

        # Edit product name using vendor callback (patch _is_vendor_or_admin to allow test user)
        mock_update.callback_query.data = f"vendor:edit_name:{product.id}"
        with patch('bot.handlers.admin._is_vendor_or_admin', return_value=True):
            await handle_vendor_callback(mock_update, mock_context, vendors=vendors, catalog=catalog)
        assert mock_context.user_data['awaiting_input'] == 'edit_name'

        mock_message_update.message.text = "Updated Name"
        await handle_admin_text_input(mock_message_update, mock_context, vendors=vendors, catalog=catalog)

        # Verify name was updated
        updated_product = catalog.get_product(product.id)
        assert updated_product.name == "Updated Name"

    @pytest.mark.asyncio
    async def test_delete_product(self, db, vendors, catalog, mock_update, mock_context):
        """Test deleting a product."""
        user_id = mock_update.effective_user.id

        # Setup vendor and product
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)
        vendor = vendors.get_by_telegram_id(user_id)

        product = catalog.add_product(Product(
            vendor_id=vendor.id,
            name="To Delete",
            description="Will be deleted",
            price_xmr=Decimal("5.00"),
            inventory=10
        ))

        # Confirm delete product using vendor callback (patch _is_vendor_or_admin to allow test user)
        mock_update.callback_query.data = f"vendor:confirm_delete:{product.id}"
        with patch('bot.handlers.admin._is_vendor_or_admin', return_value=True):
            await handle_vendor_callback(mock_update, mock_context, vendors=vendors, catalog=catalog)

        # Verify product is deleted
        products = catalog.list_products_by_vendor(vendor.id)
        assert len(products) == 0 or all(p.id != product.id for p in products)


class TestOrderFlow:
    """Integration tests for order/checkout flow."""

    @pytest.fixture
    def db(self):
        """Create a real test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendors(self, db):
        """Create real vendor service."""
        return VendorService(db)

    @pytest.fixture
    def catalog(self, db):
        """Create real catalog service."""
        return CatalogService(db)

    @pytest.fixture
    def postage(self, db):
        """Create real postage service."""
        return PostageService(db)

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 987654321  # Customer ID (different from vendor)
        user.full_name = "Customer User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_message_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message

        user = MagicMock(spec=User)
        user.id = 987654321
        user.full_name = "Customer User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.fixture
    def vendor_with_products(self, db, vendors, catalog):
        """Create a vendor with products."""
        # Create vendor directly in DB
        with db.session() as session:
            vendor = Vendor(
                telegram_id=123456789,
                name="Test Vendor",
                wallet_address="4" + "A" * 94,
                pricing_currency="USD"
            )
            session.add(vendor)
            session.commit()
            session.refresh(vendor)

            # Add products
            product1 = Product(
                vendor_id=vendor.id,
                name="Widget A",
                description="A great widget",
                price_xmr=Decimal("1.5"),
                inventory=10,
                active=True
            )
            product2 = Product(
                vendor_id=vendor.id,
                name="Widget B",
                description="Another widget",
                price_xmr=Decimal("2.5"),
                inventory=5,
                active=True
            )
            session.add(product1)
            session.add(product2)
            session.commit()
            session.refresh(product1)
            session.refresh(product2)

            return vendor, [product1, product2]

    @pytest.mark.asyncio
    async def test_browse_products(self, db, catalog, mock_update, mock_context, vendor_with_products):
        """Test browsing available products."""
        vendor, products = vendor_with_products

        # Browse products menu
        mock_update.callback_query.data = "menu:products"
        await handle_menu_callback(mock_update, mock_context, catalog=catalog)

        # Verify products are shown
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert "Products" in message_text or "product" in message_text.lower()

    @pytest.mark.asyncio
    async def test_view_product_details(self, db, catalog, mock_update, mock_context, vendor_with_products):
        """Test viewing product details."""
        vendor, products = vendor_with_products
        product = products[0]

        mock_update.callback_query.data = f"product:view:{product.id}"
        await handle_product_callback(mock_update, mock_context, catalog=catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert product.name in message_text

    @pytest.mark.asyncio
    async def test_start_order_flow(self, db, catalog, postage, mock_update, mock_context, vendor_with_products):
        """Test starting an order."""
        vendor, products = vendor_with_products
        product = products[0]

        # Start order
        mock_update.callback_query.data = f"order:start:{product.id}"
        await handle_order_callback(mock_update, mock_context, catalog=catalog, postage=postage)

        # Should show quantity selection
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert "quantity" in message_text.lower() or "Qty" in message_text

    @pytest.mark.asyncio
    async def test_order_out_of_stock(self, db, catalog, postage, mock_update, mock_context, vendor_with_products):
        """Test ordering out of stock product."""
        vendor, products = vendor_with_products

        # Set product to 0 inventory
        with db.session() as session:
            product = session.get(Product, products[0].id)
            product.inventory = 0
            session.commit()

        mock_update.callback_query.data = f"order:start:{products[0].id}"
        await handle_order_callback(mock_update, mock_context, catalog=catalog, postage=postage)

        # Should show out of stock message
        call_args = mock_update.callback_query.edit_message_text.call_args
        message_text = call_args[0][0]
        assert "out of stock" in message_text.lower() or "unavailable" in message_text.lower() or "no longer available" in message_text.lower()


class TestDatabaseResilience:
    """Test database connection resilience."""

    @pytest.fixture
    def db(self):
        """Create a real test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendors(self, db):
        """Create real vendor service."""
        return VendorService(db)

    def test_multiple_sequential_queries(self, db, vendors):
        """Test multiple sequential database queries don't fail."""
        # Create vendor
        with db.session() as session:
            vendor = Vendor(telegram_id=111, name="Test")
            session.add(vendor)
            session.commit()

        # Multiple sequential queries
        for i in range(10):
            result = vendors.get_by_telegram_id(111)
            assert result is not None
            assert result.telegram_id == 111

    def test_query_after_write(self, db, vendors):
        """Test reading after writing works correctly."""
        # Write
        with db.session() as session:
            vendor = Vendor(telegram_id=222, name="Test2")
            session.add(vendor)
            session.commit()

        # Immediate read
        result = vendors.get_by_telegram_id(222)
        assert result is not None

        # Update
        vendors.update_settings(result.id, shop_name="Updated Shop")

        # Read again
        result = vendors.get_by_telegram_id(222)
        assert result.shop_name == "Updated Shop"

    def test_concurrent_session_operations(self, db):
        """Test that multiple session operations work correctly."""
        # Create data in one session
        with db.session() as session1:
            vendor = Vendor(telegram_id=333, name="Concurrent Test")
            session1.add(vendor)
            session1.commit()
            vendor_id = vendor.id

        # Read in another session
        with db.session() as session2:
            vendor = session2.get(Vendor, vendor_id)
            assert vendor is not None
            assert vendor.name == "Concurrent Test"

        # Update in third session
        with db.session() as session3:
            vendor = session3.get(Vendor, vendor_id)
            vendor.shop_name = "New Name"
            session3.commit()

        # Verify update in fourth session
        with db.session() as session4:
            vendor = session4.get(Vendor, vendor_id)
            assert vendor.shop_name == "New Name"


class TestPostageFlow:
    """Integration tests for postage management."""

    @pytest.fixture
    def db(self):
        """Create a real test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = Database(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def vendors(self, db):
        """Create real vendor service."""
        return VendorService(db)

    @pytest.fixture
    def postage(self, db):
        """Create real postage service."""
        return PostageService(db)

    @pytest.fixture
    def mock_update(self):
        """Create mock Telegram update."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 123456789
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_message_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message

        user = MagicMock(spec=User)
        user.id = 123456789
        user.full_name = "Test User"
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_add_postage_option(self, db, vendors, postage, mock_update, mock_message_update, mock_context):
        """Test adding a postage option."""
        user_id = mock_update.effective_user.id

        # Setup vendor
        mock_update.callback_query.data = "setup:become_vendor"
        await handle_setup_callback(mock_update, mock_context, vendors=vendors)
        vendor = vendors.get_by_telegram_id(user_id)

        # Start adding postage
        mock_update.callback_query.data = "postage:add"
        await handle_postage_callback(mock_update, mock_context, vendors=vendors, postage=postage)
        assert mock_context.user_data['awaiting_input'] == 'postage_name'

        # Enter name
        mock_message_update.message.text = "Express Shipping"
        await handle_text_input(mock_message_update, mock_context, vendors=vendors, postage=postage)
        assert mock_context.user_data['awaiting_input'] == 'postage_price'

        # Enter price
        mock_message_update.message.text = "9.99"
        await handle_text_input(mock_message_update, mock_context, vendors=vendors, postage=postage)
        assert mock_context.user_data['awaiting_input'] == 'postage_desc'

        # Enter description
        mock_message_update.message.text = "2-3 business days"
        await handle_text_input(mock_message_update, mock_context, vendors=vendors, postage=postage)

        # Verify postage was created
        postage_types = postage.list_by_vendor(vendor.id)
        assert len(postage_types) == 1
        assert postage_types[0].name == "Express Shipping"
        assert postage_types[0].price_fiat == Decimal("9.99")
