"""Tests for admin command handlers."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, Message, User, CallbackQuery

from bot.handlers.admin import (
    _is_admin, _is_super_admin, _is_vendor_or_admin, add, add_vendor,
    list_vendors, set_commission, admin_menu, handle_admin_callback,
    handle_vendor_callback, handle_admin_text_input, super_admin_command,
    handle_super_admin_callback, handle_vendor_order_callback
)
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.services.orders import OrderService
from bot.services.payout import PayoutService
from bot.models import Product, Vendor, Order


class TestAdminHandlers:
    """Test admin command handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message
        update.effective_message = message
        
        user = MagicMock(spec=User)
        user.id = 123456789
        update.effective_user = user
        
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings."""
        with patch('bot.handlers.admin.get_settings') as mock:
            settings = MagicMock()
            settings.admin_ids_list = [123456789]
            settings.super_admin_ids_list = [987654321]
            settings.totp_secret = None
            mock.return_value = settings
            yield settings

    def test_is_admin_valid(self, mock_settings):
        """Test _is_admin with valid admin ID."""
        assert _is_admin(123456789) is True
        assert _is_admin(987654321) is True  # Super admin is also admin

    def test_is_admin_invalid(self, mock_settings):
        """Test _is_admin with invalid ID."""
        assert _is_admin(111111111) is False

    def test_is_admin_with_totp_valid(self, mock_settings):
        """Test _is_admin with TOTP enabled and valid token."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        
        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            assert _is_admin(123456789, "123456") is True

    def test_is_admin_with_totp_invalid(self, mock_settings):
        """Test _is_admin with TOTP enabled and invalid token."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        
        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = False
            assert _is_admin(123456789, "000000") is False

    def test_is_admin_with_totp_no_token(self, mock_settings):
        """Test _is_admin with TOTP enabled but no token provided."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        assert _is_admin(123456789, None) is False

    def test_is_super_admin_valid(self, mock_settings):
        """Test _is_super_admin with valid super admin ID."""
        assert _is_super_admin(987654321) is True

    def test_is_super_admin_invalid(self, mock_settings):
        """Test _is_super_admin with regular admin ID."""
        assert _is_super_admin(123456789) is False

    def test_is_super_admin_with_totp_valid(self, mock_settings):
        """Test _is_super_admin with TOTP enabled and valid token."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            assert _is_super_admin(987654321, "123456") is True

    def test_is_super_admin_with_totp_invalid(self, mock_settings):
        """Test _is_super_admin with TOTP enabled and invalid token."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = False
            assert _is_super_admin(987654321, "000000") is False

    def test_is_super_admin_with_totp_no_token(self, mock_settings):
        """Test _is_super_admin with TOTP enabled but no token provided."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        assert _is_super_admin(987654321, None) is False

    @pytest.mark.asyncio
    async def test_add_not_admin(self, mock_update, mock_context, mock_settings):
        """Test /add command with non-admin user."""
        mock_update.effective_user.id = 111111111  # Not an admin
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        
        await add(mock_update, mock_context, mock_catalog, mock_vendors)
        
        # Should not send any message
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_insufficient_args(self, mock_update, mock_context, mock_settings):
        """Test /add command with insufficient arguments."""
        mock_context.args = ["Product", "0.5"]  # Missing inventory
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        
        await add(mock_update, mock_context, mock_catalog, mock_vendors)
        
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "Usage:" in reply_text

    @pytest.mark.asyncio
    async def test_add_vendor_not_registered(self, mock_update, mock_context, mock_settings):
        """Test /add command when vendor not registered."""
        mock_context.args = ["Product", "0.5", "10"]
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None
        
        await add(mock_update, mock_context, mock_catalog, mock_vendors)
        
        mock_update.message.reply_text.assert_called_once_with("Vendor not registered")

    @pytest.mark.asyncio
    async def test_add_success(self, mock_update, mock_context, mock_settings):
        """Test /add command successful product addition."""
        mock_context.args = ["Gaming Laptop", "1.5", "5"]
        
        vendor = Vendor(id=1, telegram_id=123456789, name="Test Vendor")
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        
        await add(mock_update, mock_context, mock_catalog, mock_vendors)
        
        # Verify product was added
        mock_catalog.add_product.assert_called_once()
        product = mock_catalog.add_product.call_args[0][0]
        assert product.name == "Gaming Laptop"
        assert product.price_xmr == 1.5
        assert product.inventory == 5
        assert product.vendor_id == 1
        
        # Verify success message
        mock_update.message.reply_text.assert_called_once_with("Added Gaming Laptop")

    @pytest.mark.asyncio
    async def test_add_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /add command with TOTP authentication."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_context.args = ["Product", "1.0", "10", "123456"]
        
        vendor = Vendor(id=1, telegram_id=123456789, name="Test Vendor")
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        
        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            
            await add(mock_update, mock_context, mock_catalog, mock_vendors)
            
            # Verify TOTP was checked
            mock_totp.return_value.verify.assert_called_once_with("123456")
            
            # Verify product was added
            mock_catalog.add_product.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_vendor_not_super_admin(self, mock_update, mock_context, mock_settings):
        """Test /addvendor command with non-super-admin user."""
        # Regular admin, not super admin
        
        mock_vendors = MagicMock(spec=VendorService)
        
        await add_vendor(mock_update, mock_context, mock_vendors)
        
        # Should not send any message
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_add_vendor_success(self, mock_update, mock_context, mock_settings):
        """Test /addvendor command successful vendor addition."""
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["111222333", "John's Store"]

        mock_vendors = MagicMock(spec=VendorService)
        # The add_vendor function creates the vendor but id is set by the service
        def add_vendor_side_effect(vendor):
            vendor.id = 5
            return vendor
        mock_vendors.add_vendor.side_effect = add_vendor_side_effect

        await add_vendor(mock_update, mock_context, mock_vendors)

        # Verify vendor was added
        mock_vendors.add_vendor.assert_called_once()
        vendor = mock_vendors.add_vendor.call_args[0][0]
        assert vendor.telegram_id == 111222333
        assert vendor.name == "John's Store"

        # Verify success message
        mock_update.message.reply_text.assert_called_once_with(
            "Vendor John's Store added with id 5"
        )

    @pytest.mark.asyncio
    async def test_add_vendor_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /addvendor with TOTP enabled."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["111222333", "John's Store", "123456"]

        mock_vendors = MagicMock(spec=VendorService)
        def add_vendor_side_effect(vendor):
            vendor.id = 5
            return vendor
        mock_vendors.add_vendor.side_effect = add_vendor_side_effect

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            await add_vendor(mock_update, mock_context, mock_vendors)

        mock_vendors.add_vendor.assert_called_once()

    @pytest.mark.asyncio
    async def test_add_vendor_insufficient_args_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /addvendor with TOTP but insufficient args after TOTP removal."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["111222333", "123456"]  # Only telegram_id + totp, no name

        mock_vendors = MagicMock(spec=VendorService)

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            await add_vendor(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Usage:" in call_args

    @pytest.mark.asyncio
    async def test_list_vendors_not_super_admin(self, mock_update, mock_context, mock_settings):
        """Test /vendors command with non-super-admin user."""
        mock_update.effective_user.id = 123456789  # Regular admin, not super admin

        mock_vendors = MagicMock(spec=VendorService)

        await list_vendors(mock_update, mock_context, mock_vendors)

        # Should not send any message
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_list_vendors_empty(self, mock_update, mock_context, mock_settings):
        """Test /vendors command with no vendors."""
        mock_update.effective_user.id = 987654321  # Super admin

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.list_vendors.return_value = []

        await list_vendors(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once_with("No vendors")

    @pytest.mark.asyncio
    async def test_list_vendors_with_data(self, mock_update, mock_context, mock_settings):
        """Test /vendors command with vendors."""
        mock_update.effective_user.id = 987654321  # Super admin

        vendor1 = Vendor(id=1, telegram_id=111, name="Store 1", commission_rate=0.05)
        vendor2 = Vendor(id=2, telegram_id=222, name="Store 2", commission_rate=0.10)

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.list_vendors.return_value = [vendor1, vendor2]

        await list_vendors(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "1: Store 1 rate 0.05" in reply_text
        assert "2: Store 2 rate 0.1" in reply_text

    @pytest.mark.asyncio
    async def test_list_vendors_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /vendors command with TOTP enabled."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["123456"]

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.list_vendors.return_value = []

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            await list_vendors(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once_with("No vendors")

    @pytest.mark.asyncio
    async def test_set_commission_not_super_admin(self, mock_update, mock_context, mock_settings):
        """Test /commission command with non-super-admin user."""
        mock_update.effective_user.id = 123456789  # Regular admin, not super admin
        mock_context.args = ["1", "0.15"]

        mock_vendors = MagicMock(spec=VendorService)

        await set_commission(mock_update, mock_context, mock_vendors)

        # Should not send any message
        mock_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_set_commission_success(self, mock_update, mock_context, mock_settings):
        """Test /commission command successful commission update."""
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["1", "0.15"]

        updated_vendor = Vendor(
            id=1, telegram_id=111, name="Store 1", commission_rate=0.15
        )

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.set_commission.return_value = updated_vendor

        await set_commission(mock_update, mock_context, mock_vendors)

        # Verify commission was set
        mock_vendors.set_commission.assert_called_once_with(1, 0.15)

        # Verify success message
        mock_update.message.reply_text.assert_called_once_with(
            "Vendor Store 1 commission set to 0.15"
        )

    @pytest.mark.asyncio
    async def test_set_commission_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /commission command with TOTP enabled."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["1", "0.15", "123456"]

        updated_vendor = Vendor(
            id=1, telegram_id=111, name="Store 1", commission_rate=0.15
        )
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.set_commission.return_value = updated_vendor

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            await set_commission(mock_update, mock_context, mock_vendors)

        mock_vendors.set_commission.assert_called_once_with(1, 0.15)

    @pytest.mark.asyncio
    async def test_set_commission_insufficient_args(self, mock_update, mock_context, mock_settings):
        """Test /commission with insufficient arguments."""
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["1"]  # Missing rate

        mock_vendors = MagicMock(spec=VendorService)

        await set_commission(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Usage:" in call_args

    @pytest.mark.asyncio
    async def test_set_commission_insufficient_args_with_totp(self, mock_update, mock_context, mock_settings):
        """Test /commission with TOTP enabled but insufficient args after TOTP removal."""
        mock_settings.totp_secret = "JBSWY3DPEHPK3PXP"
        mock_update.effective_user.id = 987654321  # Super admin
        mock_context.args = ["1", "123456"]  # Only vendor_id + totp, no rate

        mock_vendors = MagicMock(spec=VendorService)

        with patch('pyotp.TOTP') as mock_totp:
            mock_totp.return_value.verify.return_value = True
            await set_commission(mock_update, mock_context, mock_vendors)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0][0]
        assert "Usage:" in call_args

    # ==================== IS VENDOR OR ADMIN TESTS ====================

    def test_is_vendor_or_admin_is_admin(self, mock_settings):
        """Test _is_vendor_or_admin when user is admin."""
        mock_vendors = MagicMock(spec=VendorService)
        assert _is_vendor_or_admin(123456789, mock_vendors) is True
        mock_vendors.get_by_telegram_id.assert_not_called()

    def test_is_vendor_or_admin_is_vendor(self, mock_settings):
        """Test _is_vendor_or_admin when user is vendor but not admin."""
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=111, name="Test")
        assert _is_vendor_or_admin(111, mock_vendors) is True

    def test_is_vendor_or_admin_neither(self, mock_settings):
        """Test _is_vendor_or_admin when user is neither."""
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None
        assert _is_vendor_or_admin(111, mock_vendors) is False

    # ==================== ADMIN MENU TESTS ====================

    @pytest.mark.asyncio
    async def test_admin_menu_authorized(self, mock_update, mock_context, mock_settings):
        """Test admin_menu with authorized user."""
        await admin_menu(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Admin Panel" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_admin_menu_unauthorized(self, mock_update, mock_context, mock_settings):
        """Test admin_menu with unauthorized user."""
        mock_update.effective_user.id = 111111111
        await admin_menu(mock_update, mock_context)
        mock_update.message.reply_text.assert_called_once_with(
            "You don't have admin access."
        )

    # ==================== HANDLE ADMIN CALLBACK TESTS ====================

    @pytest.fixture
    def mock_callback_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query

        user = MagicMock(spec=User)
        user.id = 123456789
        update.effective_user = user

        return update

    @pytest.fixture
    def mock_callback_context(self):
        """Create mock context for callbacks."""
        context = MagicMock()
        context.user_data = {}
        context.bot_data = {}
        return context

    @pytest.mark.asyncio
    async def test_handle_admin_callback_short_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test handle_admin_callback with invalid short data."""
        mock_callback_update.callback_query.data = "admin"  # No action
        await handle_admin_callback(mock_callback_update, mock_callback_context)
        # Should just return without editing
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_admin_callback_products_not_vendor(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test products action when user is not a vendor."""
        mock_callback_update.callback_query.data = "admin:products"
        mock_callback_update.effective_user.id = 111111111  # Not admin

        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_admin_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "need to be a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_products_vendor_not_found(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test products action when vendor is admin but not registered as vendor."""
        mock_callback_update.callback_query.data = "admin:products"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_admin_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "need to be registered as a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_products_empty(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test products action with no products."""
        mock_callback_update.callback_query.data = "admin:products"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products_by_vendor.return_value = []
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_admin_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "haven't added any products" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_products_with_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test products action with products."""
        mock_callback_update.callback_query.data = "admin:products"

        product = Product(id=1, name="Test Product", price_xmr=1.0, inventory=10, vendor_id=1)
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products_by_vendor.return_value = [product]
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_admin_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "My Products" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_not_admin(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test callback when user is not admin for admin-only actions."""
        mock_callback_update.callback_query.data = "admin:add_product"
        mock_callback_update.effective_user.id = 111111111

        await handle_admin_callback(mock_callback_update, mock_callback_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_once_with(
            "You don't have admin access."
        )

    @pytest.mark.asyncio
    async def test_handle_admin_callback_add_product(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test add_product action."""
        mock_callback_update.callback_query.data = "admin:add_product"

        await handle_admin_callback(mock_callback_update, mock_callback_context)

        assert mock_callback_context.user_data['awaiting_input'] == 'product_name'
        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Add New Product" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_orders_with_orders(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test orders action with vendor orders."""
        mock_callback_update.callback_query.data = "admin:orders"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        mock_orders = MagicMock(spec=OrderService)
        mock_orders.list_orders_by_vendor.return_value = [order]
        mock_callback_context.bot_data['orders'] = mock_orders

        await handle_admin_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "My Orders" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_orders_empty(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test orders action with no orders."""
        mock_callback_update.callback_query.data = "admin:orders"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.list_orders_by_vendor.return_value = []
        mock_callback_context.bot_data['orders'] = mock_orders

        await handle_admin_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "No orders yet" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_orders_no_service(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test orders action when order service unavailable."""
        mock_callback_update.callback_query.data = "admin:orders"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        # No orders in bot_data

        await handle_admin_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Order service unavailable" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_orders_not_vendor(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test orders action when user is admin but not vendor."""
        mock_callback_update.callback_query.data = "admin:orders"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_admin_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "need to be a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_callback_settings(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test settings action."""
        mock_callback_update.callback_query.data = "admin:settings"

        await handle_admin_callback(mock_callback_update, mock_callback_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Shop Settings" in call_args[0][0]

    # ==================== HANDLE VENDOR CALLBACK TESTS ====================

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_not_vendor(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor callback when user is not a vendor."""
        mock_callback_update.callback_query.data = "vendor:add"
        mock_callback_update.effective_user.id = 111111111

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "need to be a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_no_vendors_service(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor callback without vendors service."""
        mock_callback_update.callback_query.data = "vendor:add"

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=None)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_short_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor callback with invalid short data."""
        mock_callback_update.callback_query.data = "vendor"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_add(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor add action."""
        mock_callback_update.callback_query.data = "vendor:add"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'product_name'
        mock_callback_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_edit(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor edit action."""
        mock_callback_update.callback_query.data = "vendor:edit:1"

        product = Product(id=1, name="Test", price_xmr=1.0, inventory=10, vendor_id=1, description="Desc")
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Test" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_edit_name(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor edit_name action."""
        mock_callback_update.callback_query.data = "vendor:edit_name:1"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'edit_name'
        assert mock_callback_context.user_data['editing_product'] == 1

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_edit_price(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor edit_price action."""
        mock_callback_update.callback_query.data = "vendor:edit_price:1"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'edit_price'

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_edit_stock(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor edit_stock action."""
        mock_callback_update.callback_query.data = "vendor:edit_stock:1"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'edit_stock'

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_edit_desc(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor edit_desc action."""
        mock_callback_update.callback_query.data = "vendor:edit_desc:1"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'edit_desc'

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_delete(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor delete action."""
        mock_callback_update.callback_query.data = "vendor:delete:1"

        product = Product(id=1, name="Test", price_xmr=1.0, inventory=10, vendor_id=1)
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Delete Product" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_callback_confirm_delete(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor confirm_delete action."""
        mock_callback_update.callback_query.data = "vendor:confirm_delete:1"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products_by_vendor.return_value = []
        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_vendor_callback(mock_callback_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.delete_product.assert_called_once_with(1)
        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Product Deleted" in call_args[0][0]

    # ==================== HANDLE ADMIN TEXT INPUT TESTS ====================

    @pytest.fixture
    def mock_text_update(self):
        """Create mock update with text message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        message.text = "Test input"
        update.message = message

        user = MagicMock(spec=User)
        user.id = 123456789
        update.effective_user = user

        return update

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_no_awaiting(self, mock_text_update, mock_callback_context, mock_settings):
        """Test text input when not awaiting any input."""
        await handle_admin_text_input(mock_text_update, mock_callback_context)
        mock_text_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_non_admin_flow(self, mock_text_update, mock_callback_context, mock_settings):
        """Test text input for non-admin related flow."""
        mock_callback_context.user_data['awaiting_input'] = 'some_other_flow'
        await handle_admin_text_input(mock_text_update, mock_callback_context)
        mock_text_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_not_vendor(self, mock_text_update, mock_callback_context, mock_settings):
        """Test text input when user is not vendor."""
        mock_callback_context.user_data['awaiting_input'] = 'product_name'
        mock_text_update.effective_user.id = 111111111

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)
        mock_text_update.message.reply_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_name(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_name input."""
        mock_callback_context.user_data['awaiting_input'] = 'product_name'
        mock_callback_context.user_data['new_product'] = {}
        mock_text_update.message.text = "My Product"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test", pricing_currency="USD")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['new_product']['name'] == "My Product"
        assert mock_callback_context.user_data['awaiting_input'] == 'product_price'

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_name_xmr_currency(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_name input with XMR currency."""
        mock_callback_context.user_data['awaiting_input'] = 'product_name'
        mock_callback_context.user_data['new_product'] = {}
        mock_text_update.message.text = "My Product"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test", pricing_currency="XMR")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "XMR" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_price_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_price input with valid price."""
        mock_callback_context.user_data['awaiting_input'] = 'product_price'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'currency': 'USD'}
        mock_text_update.message.text = "25.50"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test", pricing_currency="USD")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        with patch('bot.handlers.admin.format_price_simple', return_value="$25.50"):
            await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['new_product']['price'] == 25.50
        assert mock_callback_context.user_data['awaiting_input'] == 'product_stock'

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_price_invalid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_price input with invalid price."""
        mock_callback_context.user_data['awaiting_input'] = 'product_price'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'currency': 'USD'}
        mock_text_update.message.text = "not a number"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid price" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_stock_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_stock input with valid stock."""
        mock_callback_context.user_data['awaiting_input'] = 'product_stock'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0, 'currency': 'USD'}
        mock_text_update.message.text = "10"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        with patch('bot.handlers.admin.format_price_simple', return_value="$25.00"):
            await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['new_product']['stock'] == 10
        assert mock_callback_context.user_data['awaiting_input'] == 'product_desc'

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_stock_invalid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_stock input with invalid stock."""
        mock_callback_context.user_data['awaiting_input'] = 'product_stock'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0}
        mock_text_update.message.text = "not a number"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid quantity" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_desc_vendor_not_found(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_desc when vendor not found."""
        mock_callback_context.user_data['awaiting_input'] = 'product_desc'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0, 'stock': 10}
        mock_text_update.message.text = "Description"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "not registered as a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_desc_success(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_desc successful product creation."""
        mock_callback_context.user_data['awaiting_input'] = 'product_desc'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0, 'stock': 10, 'currency': 'USD'}
        mock_text_update.message.text = "A great product"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products_by_vendor.return_value = []

        with patch('bot.handlers.admin.fiat_to_xmr_accurate', new=AsyncMock(return_value=Decimal("0.1"))):
            with patch('bot.handlers.admin.format_price_simple', return_value="$25.00"):
                await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.add_product.assert_called_once()
        assert mock_callback_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_desc_skip(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_desc with skip."""
        mock_callback_context.user_data['awaiting_input'] = 'product_desc'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0, 'stock': 10, 'currency': 'USD'}
        mock_text_update.message.text = "skip"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products_by_vendor.return_value = []

        with patch('bot.handlers.admin.fiat_to_xmr_accurate', new=AsyncMock(return_value=Decimal("0.1"))):
            with patch('bot.handlers.admin.format_price_simple', return_value="$25.00"):
                await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        product = mock_catalog.add_product.call_args[0][0]
        assert product.description == ""

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_product_desc_conversion_error(self, mock_text_update, mock_callback_context, mock_settings):
        """Test product_desc with currency conversion error."""
        mock_callback_context.user_data['awaiting_input'] = 'product_desc'
        mock_callback_context.user_data['new_product'] = {'name': 'Test', 'price': 25.0, 'stock': 10, 'currency': 'USD'}
        mock_text_update.message.text = "Description"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        with patch('bot.handlers.admin.fiat_to_xmr_accurate', new=AsyncMock(side_effect=ValueError("API error"))):
            await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Error converting price" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_name(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_name input."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_name'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "New Name"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = Product(id=1, name="New Name", price_xmr=1.0, inventory=10, vendor_id=1)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.update_product.assert_called_once_with(1, name="New Name")
        assert mock_callback_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_price_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_price input with valid price."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_price'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "1.5"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.update_product.assert_called_once_with(1, price_xmr=1.5)

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_price_invalid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_price input with invalid price."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_price'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "invalid"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid price" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_stock_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_stock input with valid stock."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_stock'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "50"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.update_product.assert_called_once_with(1, inventory=50)

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_stock_invalid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_stock input with invalid stock."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_stock'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "invalid"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid quantity" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_edit_desc(self, mock_text_update, mock_callback_context, mock_settings):
        """Test edit_desc input."""
        mock_callback_context.user_data['awaiting_input'] = 'edit_desc'
        mock_callback_context.user_data['editing_product'] = 1
        mock_text_update.message.text = "New description"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor
        mock_catalog = MagicMock(spec=CatalogService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, mock_catalog, mock_vendors)

        mock_catalog.update_product.assert_called_once_with(1, description="New description")

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_platform_wallet_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test platform_wallet input with valid address."""
        mock_callback_context.user_data['awaiting_input'] = 'platform_wallet'
        mock_text_update.effective_user.id = 987654321  # Super admin
        mock_text_update.message.text = "4" + "A" * 94  # Valid XMR address format

        mock_payout = MagicMock(spec=PayoutService)
        mock_callback_context.bot_data['payout_service'] = mock_payout
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_payout.set_platform_wallet.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_platform_wallet_invalid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test platform_wallet input with invalid address."""
        mock_callback_context.user_data['awaiting_input'] = 'platform_wallet'
        mock_text_update.effective_user.id = 987654321  # Super admin
        mock_text_update.message.text = "invalid_address"

        mock_payout = MagicMock(spec=PayoutService)
        mock_callback_context.bot_data['payout_service'] = mock_payout
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid Monero address" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_custom_commission_valid(self, mock_text_update, mock_callback_context, mock_settings):
        """Test custom_commission input with valid rate."""
        mock_callback_context.user_data['awaiting_input'] = 'custom_commission'
        mock_text_update.effective_user.id = 987654321  # Super admin
        mock_text_update.message.text = "0.05"

        mock_payout = MagicMock(spec=PayoutService)
        mock_callback_context.bot_data['payout_service'] = mock_payout
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_payout.set_platform_commission_rate.assert_called_once()

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_custom_commission_invalid_range(self, mock_text_update, mock_callback_context, mock_settings):
        """Test custom_commission input with invalid range."""
        mock_callback_context.user_data['awaiting_input'] = 'custom_commission'
        mock_text_update.effective_user.id = 987654321  # Super admin
        mock_text_update.message.text = "1.5"  # Invalid - should be between 0 and 1

        mock_payout = MagicMock(spec=PayoutService)
        mock_callback_context.bot_data['payout_service'] = mock_payout
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid rate" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_custom_commission_invalid_format(self, mock_text_update, mock_callback_context, mock_settings):
        """Test custom_commission input with invalid format."""
        mock_callback_context.user_data['awaiting_input'] = 'custom_commission'
        mock_text_update.effective_user.id = 987654321  # Super admin
        mock_text_update.message.text = "not a number"
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Invalid rate" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_shipping_note_success(self, mock_text_update, mock_callback_context, mock_settings):
        """Test shipping_note input success."""
        mock_callback_context.user_data['awaiting_input'] = 'shipping_note'
        mock_callback_context.user_data['shipping_order'] = 1
        mock_text_update.message.text = "Tracking: ABC123"

        mock_order = MagicMock(spec=Order)
        mock_order.state = "SHIPPED"
        mock_orders = MagicMock(spec=OrderService)
        mock_orders.mark_shipped.return_value = mock_order
        mock_callback_context.bot_data['orders'] = mock_orders
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_orders.mark_shipped.assert_called_once_with(1, shipping_note="Tracking: ABC123")

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_shipping_note_skip(self, mock_text_update, mock_callback_context, mock_settings):
        """Test shipping_note input with skip."""
        mock_callback_context.user_data['awaiting_input'] = 'shipping_note'
        mock_callback_context.user_data['shipping_order'] = 1
        mock_text_update.message.text = "skip"

        mock_order = MagicMock(spec=Order)
        mock_order.state = "SHIPPED"
        mock_orders = MagicMock(spec=OrderService)
        mock_orders.mark_shipped.return_value = mock_order
        mock_callback_context.bot_data['orders'] = mock_orders
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_orders.mark_shipped.assert_called_once_with(1, shipping_note=None)

    @pytest.mark.asyncio
    async def test_handle_admin_text_input_shipping_note_error(self, mock_text_update, mock_callback_context, mock_settings):
        """Test shipping_note input error handling."""
        mock_callback_context.user_data['awaiting_input'] = 'shipping_note'
        mock_callback_context.user_data['shipping_order'] = 1
        mock_text_update.message.text = "Note"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.mark_shipped.side_effect = Exception("Order error")
        mock_callback_context.bot_data['orders'] = mock_orders
        mock_vendors = MagicMock(spec=VendorService)

        await handle_admin_text_input(mock_text_update, mock_callback_context, vendors=mock_vendors)

        mock_text_update.message.reply_text.assert_called_once()
        call_args = mock_text_update.message.reply_text.call_args
        assert "Error" in call_args[0][0]

    # ==================== SUPER ADMIN COMMAND TESTS ====================

    @pytest.mark.asyncio
    async def test_super_admin_command_authorized(self, mock_update, mock_context, mock_settings):
        """Test super_admin_command with authorized user."""
        mock_update.effective_user.id = 987654321  # Super admin

        await super_admin_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args
        assert "Super Admin Panel" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_super_admin_command_unauthorized(self, mock_update, mock_context, mock_settings):
        """Test super_admin_command with unauthorized user."""
        mock_update.effective_user.id = 123456789  # Regular admin

        await super_admin_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once_with("Access denied.")

    # ==================== HANDLE SUPER ADMIN CALLBACK TESTS ====================

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_unauthorized(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin callback with unauthorized user."""
        mock_callback_update.callback_query.data = "sadmin:stats"
        mock_callback_update.effective_user.id = 123456789  # Regular admin

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_once_with("Access denied.")

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_short_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin callback with short data."""
        mock_callback_update.callback_query.data = "sadmin"
        mock_callback_update.effective_user.id = 987654321

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_main(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin main action."""
        mock_callback_update.callback_query.data = "sadmin:main"
        mock_callback_update.effective_user.id = 987654321

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Super Admin Panel" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_stats(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin stats action."""
        mock_callback_update.callback_query.data = "sadmin:stats"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.get_platform_stats.return_value = {
            'paid_orders': 10,
            'total_orders': 15,
            'total_commission_xmr': Decimal("1.5"),
            'pending_payouts': 3,
            'pending_payout_amount_xmr': Decimal("0.5"),
            'completed_payouts': 5,
            'completed_payout_amount_xmr': Decimal("2.0"),
            'commission_rate': Decimal("0.05"),
            'platform_wallet': "4AAAA..."
        }

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        mock_callback_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Platform Statistics" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_stats_no_wallet(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin stats when no wallet set."""
        mock_callback_update.callback_query.data = "sadmin:stats"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.get_platform_stats.return_value = {
            'paid_orders': 0,
            'total_orders': 0,
            'total_commission_xmr': Decimal("0"),
            'pending_payouts': 0,
            'pending_payout_amount_xmr': Decimal("0"),
            'completed_payouts': 0,
            'completed_payout_amount_xmr': Decimal("0"),
            'commission_rate': Decimal("0.05"),
            'platform_wallet': None
        }

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Not set" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_commission(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin commission action."""
        mock_callback_update.callback_query.data = "sadmin:commission"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.get_platform_commission_rate.return_value = Decimal("0.05")

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Set Commission Rate" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_set_commission(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin set_commission action."""
        mock_callback_update.callback_query.data = "sadmin:set_commission:0.10"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        mock_payout.set_platform_commission_rate.assert_called_once()
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Commission Rate Updated" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_custom_commission(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin custom_commission action."""
        mock_callback_update.callback_query.data = "sadmin:custom_commission"
        mock_callback_update.effective_user.id = 987654321

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)

        assert mock_callback_context.user_data['awaiting_input'] == 'custom_commission'

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_wallet(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin wallet action."""
        mock_callback_update.callback_query.data = "sadmin:wallet"
        mock_callback_update.effective_user.id = 987654321

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)

        assert mock_callback_context.user_data['awaiting_input'] == 'platform_wallet'

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_payouts(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin payouts action."""
        mock_callback_update.callback_query.data = "sadmin:payouts"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.process_payouts = AsyncMock(return_value={
            'processed': 5,
            'sent': 3,
            'failed': 1,
            'skipped': 1
        })

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Payouts Processed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_pending_empty(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin pending action with no pending payouts."""
        mock_callback_update.callback_query.data = "sadmin:pending"
        mock_callback_update.effective_user.id = 987654321

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.get_pending_payouts.return_value = []

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "No pending payouts" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_pending_with_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin pending action with pending payouts."""
        mock_callback_update.callback_query.data = "sadmin:pending"
        mock_callback_update.effective_user.id = 987654321

        mock_payout_item = MagicMock()
        mock_payout_item.order_id = 1
        mock_payout_item.amount_xmr = Decimal("0.5")

        mock_payout = MagicMock(spec=PayoutService)
        mock_payout.get_pending_payouts.return_value = [mock_payout_item]

        await handle_super_admin_callback(mock_callback_update, mock_callback_context, mock_payout)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Pending Payouts" in call_args[0][0]
        assert "Order #1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_super_admin_callback_vendors(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test super admin vendors action."""
        mock_callback_update.callback_query.data = "sadmin:vendors"
        mock_callback_update.effective_user.id = 987654321

        await handle_super_admin_callback(mock_callback_update, mock_callback_context)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Vendor Management" in call_args[0][0]

    # ==================== HANDLE VENDOR ORDER CALLBACK TESTS ====================

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_no_vendors(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order callback without vendors service."""
        mock_callback_update.callback_query.data = "vorder:view:1"

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, vendors=None)
        # Should just return
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_not_vendor(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order callback when user is not a vendor."""
        mock_callback_update.callback_query.data = "vorder:view:1"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "need to be a vendor" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_short_data(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order callback with short data."""
        mock_callback_update.callback_query.data = "vorder"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = Vendor(id=1, telegram_id=123456789, name="Test")

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)
        mock_callback_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_view(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order view action."""
        mock_callback_update.callback_query.data = "vorder:view:1"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        order.vendor_id = 1
        order.state = "PAID"
        order.quantity = 2
        order.shipped_at = None
        order.shipping_note = None

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = order
        mock_orders.get_address.return_value = "123 Test St"

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Order #1" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_view_with_shipping(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order view with shipping info."""
        mock_callback_update.callback_query.data = "vorder:view:1"

        from datetime import datetime
        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        order.vendor_id = 1
        order.state = "SHIPPED"
        order.quantity = 2
        order.shipped_at = datetime(2024, 1, 15, 10, 30)
        order.shipping_note = "Tracking: ABC123"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = order
        mock_orders.get_address.return_value = "123 Test St"

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Shipped:" in call_args[0][0]
        assert "Note:" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_view_not_found(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order view when order not found."""
        mock_callback_update.callback_query.data = "vorder:view:999"
        mock_callback_update.callback_query.answer = AsyncMock()

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = None

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        # Should show alert
        mock_callback_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_view_wrong_vendor(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order view when order belongs to different vendor."""
        mock_callback_update.callback_query.data = "vorder:view:1"
        mock_callback_update.callback_query.answer = AsyncMock()

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        order.vendor_id = 2  # Different vendor

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = order

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        mock_callback_update.callback_query.answer.assert_called()

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_ship(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order ship action."""
        mock_callback_update.callback_query.data = "vorder:ship:1"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, vendors=mock_vendors)

        assert mock_callback_context.user_data['awaiting_input'] == 'shipping_note'
        assert mock_callback_context.user_data['shipping_order'] == 1

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_complete(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order complete action."""
        mock_callback_update.callback_query.data = "vorder:complete:1"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        order.state = "COMPLETED"
        mock_orders = MagicMock(spec=OrderService)
        mock_orders.mark_completed.return_value = order

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        mock_orders.mark_completed.assert_called_once_with(1)
        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Completed" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_complete_error(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order complete action error handling."""
        mock_callback_update.callback_query.data = "vorder:complete:1"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.mark_completed.side_effect = Exception("Order error")

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        assert "Error" in call_args[0][0]

    @pytest.mark.asyncio
    async def test_handle_vendor_order_callback_view_long_address(self, mock_callback_update, mock_callback_context, mock_settings):
        """Test vendor order view with long address truncation."""
        mock_callback_update.callback_query.data = "vorder:view:1"

        vendor = Vendor(id=1, telegram_id=123456789, name="Test")
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = vendor

        order = MagicMock(spec=Order)
        order.vendor_id = 1
        order.state = "PAID"
        order.quantity = 2
        order.shipped_at = None
        order.shipping_note = None

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = order
        # Long address that should be truncated
        mock_orders.get_address.return_value = "A" * 100

        await handle_vendor_order_callback(mock_callback_update, mock_callback_context, mock_orders, mock_vendors)

        call_args = mock_callback_update.callback_query.edit_message_text.call_args
        # Address should be truncated with ...
        assert "..." in call_args[0][0]