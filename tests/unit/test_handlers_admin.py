"""Tests for admin command handlers."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, Message, User

from bot.handlers.admin import (
    _is_admin, _is_super_admin, add, add_vendor, 
    list_vendors, set_commission
)
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.models import Product, Vendor


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