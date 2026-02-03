"""Tests for user command handlers."""

import pytest
from decimal import Decimal
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, Message, User, CallbackQuery, InlineKeyboardMarkup

from bot.handlers.user import (
    start,
    help_command,
    setup_command,
    list_products,
    order,
    orders_list,
    order_status,
    handle_menu_callback,
    handle_setup_callback,
    handle_payment_toggle_callback,
    handle_products_callback,
    handle_product_callback,
    handle_order_callback,
    handle_text_input,
    handle_currency_callback,
    handle_postage_callback,
    HELP_TEXT,
    SETUP_INTRO,
)
from bot.services.catalog import CatalogService
from bot.services.orders import OrderService
from bot.services.vendors import VendorService
from bot.services.postage import PostageService
from bot.models import Product, Vendor, PostageType
from bot.keyboards import main_menu_keyboard


class TestUserHandlers:
    """Test user command handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message
        update.effective_message = message
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.args = []
        context.user_data = {}
        return context

    @pytest.fixture
    def mock_callback_query(self, mock_update):
        """Create mock callback query."""
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        query.data = "menu:main"
        mock_update.callback_query = query
        return query

    @pytest.mark.asyncio
    async def test_start_command(self, mock_update, mock_context):
        """Test /start command handler shows welcome with buttons."""
        await start(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]

        # Check parse mode and reply markup
        assert call_kwargs["parse_mode"] == "Markdown"
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

        # Check message content
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Welcome to the Shop" in call_args[0]

    @pytest.mark.asyncio
    async def test_help_command(self, mock_update, mock_context):
        """Test /help command shows all available commands."""
        await help_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]

        # Verify help text contains key commands
        assert "/start" in call_args[0]
        assert "/products" in call_args[0]
        assert "/order" in call_args[0]
        assert "/setup" in call_args[0]
        assert "/help" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_command(self, mock_update, mock_context):
        """Test /setup command shows setup menu with buttons."""
        await setup_command(mock_update, mock_context)

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]

        assert call_kwargs["parse_mode"] == "Markdown"
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

    @pytest.mark.asyncio
    async def test_list_products_no_products(self, mock_update, mock_context):
        """Test /list command with no products."""
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = []

        await list_products(mock_update, mock_context, mock_catalog)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "No products found" in call_args[0]

    @pytest.mark.asyncio
    async def test_list_products_with_products(self, mock_update, mock_context):
        """Test /list command with products shows buttons."""
        product1 = Product(id=1, name="Product 1", description="", price_xmr=0.5, inventory=10, vendor_id=1)
        product2 = Product(id=2, name="Product 2", description="", price_xmr=1.0, inventory=0, vendor_id=1)

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = [product1, product2]

        await list_products(mock_update, mock_context, mock_catalog)

        mock_update.message.reply_text.assert_called_once()
        call_kwargs = mock_update.message.reply_text.call_args[1]

        # Should have inline keyboard for products
        assert isinstance(call_kwargs["reply_markup"], InlineKeyboardMarkup)

        # Products should be stored in context for pagination
        assert mock_context.user_data["products"] == [product1, product2]

    @pytest.mark.asyncio
    async def test_list_products_with_search(self, mock_update, mock_context):
        """Test /list command with search query."""
        mock_context.args = ["laptop"]

        product = Product(id=1, name="Gaming Laptop", description="", price_xmr=2.0, inventory=5, vendor_id=1)

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.search.return_value = [product]

        await list_products(mock_update, mock_context, mock_catalog)

        mock_catalog.search.assert_called_once_with("laptop")
        mock_catalog.list_products.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_insufficient_args(self, mock_update, mock_context):
        """Test /order command with insufficient arguments."""
        mock_context.args = ["1", "2"]  # Missing address
        mock_orders = MagicMock(spec=OrderService)

        await order(mock_update, mock_context, mock_orders)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Usage:" in call_args[0] or "Quick Order" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_invalid_args(self, mock_update, mock_context):
        """Test /order command with invalid arguments."""
        mock_context.args = ["abc", "def", "address"]  # Invalid numbers
        mock_orders = MagicMock(spec=OrderService)

        await order(mock_update, mock_context, mock_orders)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Invalid product ID or quantity" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_success(self, mock_update, mock_context):
        """Test /order command successful order creation."""
        mock_context.args = ["1", "2", "123", "Main", "Street"]  # Multi-word address

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.create_order.return_value = {
            "order_id": 42,
            "payment_address": "4A1234567890abcdef",
            "payment_id": "abc123",
            "total_xmr": 2.0,
            "product_name": "Test Product",
            "quantity": 2
        }

        await order(mock_update, mock_context, mock_orders)

        # Verify order was created with correct params
        mock_orders.create_order.assert_called_once_with(1, 2, "123 Main Street")

        # Verify reply
        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        call_kwargs = mock_update.message.reply_text.call_args[1]

        assert "Order #42" in call_args[0]
        assert "2.0" in call_args[0]
        assert "4A1234567890abcdef" in call_args[0]
        assert call_kwargs["parse_mode"] == "Markdown"

    @pytest.mark.asyncio
    async def test_order_service_error(self, mock_update, mock_context):
        """Test /order command when service raises error."""
        mock_context.args = ["1", "1", "address"]

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.create_order.side_effect = ValueError("Product not found")

        with pytest.raises(ValueError):
            await order(mock_update, mock_context, mock_orders)

        # Error handler decorator should have sent error message
        mock_update.message.reply_text.assert_called_once_with(
            "An error occurred. Please try again or contact support."
        )

    @pytest.mark.asyncio
    async def test_orders_list(self, mock_update, mock_context):
        """Test /orders command."""
        mock_orders = MagicMock(spec=OrderService)

        await orders_list(mock_update, mock_context, mock_orders)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Orders" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status(self, mock_update, mock_context):
        """Test /status command."""
        mock_context.args = ["42"]
        mock_orders = MagicMock(spec=OrderService)

        await order_status(mock_update, mock_context, mock_orders)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Order #42" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status_no_args(self, mock_update, mock_context):
        """Test /status command without order ID."""
        mock_context.args = []
        mock_orders = MagicMock(spec=OrderService)

        await order_status(mock_update, mock_context, mock_orders)

        mock_update.message.reply_text.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Usage:" in call_args[0]


class TestCallbackHandlers:
    """Test callback query handlers for button interactions."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_menu_callback_main(self, mock_update, mock_context):
        """Test menu:main callback."""
        mock_update.callback_query.data = "menu:main"

        await handle_menu_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()

    @pytest.mark.asyncio
    async def test_menu_callback_products(self, mock_update, mock_context):
        """Test menu:products callback."""
        mock_update.callback_query.data = "menu:products"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = []

        await handle_menu_callback(mock_update, mock_context, mock_catalog)

        mock_update.callback_query.answer.assert_called_once()

    @pytest.mark.asyncio
    async def test_menu_callback_help(self, mock_update, mock_context):
        """Test menu:help callback."""
        mock_update.callback_query.data = "menu:help"

        await handle_menu_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "/start" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_payments(self, mock_update, mock_context):
        """Test setup:payments callback."""
        mock_update.callback_query.data = "setup:payments"
        mock_update.effective_user.id = 123

        # Create mock vendors service
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.accepted_payments = "XMR"
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR"]

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        mock_update.callback_query.answer.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Payment Methods" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_shopname(self, mock_update, mock_context):
        """Test setup:shopname callback."""
        mock_update.callback_query.data = "setup:shopname"

        await handle_setup_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        assert mock_context.user_data["awaiting_input"] == "shopname"

    @pytest.mark.asyncio
    async def test_payment_toggle_callback(self, mock_update, mock_context):
        """Test pay:toggle callback."""
        mock_update.callback_query.data = "pay:toggle:BTC"
        mock_update.effective_user.id = 123

        # Create mock vendors service
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR"]

        await handle_payment_toggle_callback(mock_update, mock_context, mock_vendors)

        mock_update.callback_query.answer.assert_called_once()
        # Verify update_settings was called with BTC added
        mock_vendors.update_settings.assert_called_once()
        call_args = mock_vendors.update_settings.call_args
        assert "BTC" in call_args[1]["accepted_payments"]

    @pytest.mark.asyncio
    async def test_payment_toggle_xmr_cannot_disable(self, mock_update, mock_context):
        """Test that XMR cannot be disabled."""
        mock_update.callback_query.data = "pay:toggle:XMR"
        mock_context.user_data["accepted_payments"] = ["XMR", "BTC"]

        await handle_payment_toggle_callback(mock_update, mock_context)

        # XMR should still be in the list
        assert "XMR" in mock_context.user_data["accepted_payments"]

    @pytest.mark.asyncio
    async def test_payment_save_callback(self, mock_update, mock_context):
        """Test pay:save callback."""
        mock_update.callback_query.data = "pay:save"
        mock_context.user_data["accepted_payments"] = ["XMR", "BTC", "ETH"]

        await handle_payment_toggle_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        mock_update.callback_query.edit_message_text.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args
        # Check that the message contains "Saved" or shows the saved coins
        assert call_args is not None
        assert "XMR" in call_args[0][0] or "Saved" in call_args[0][0]


class TestTextInputHandlers:
    """Test text input handlers for setup flows."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        message.text = "Test input"
        update.message = message
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_text_input_shopname(self, mock_update, mock_context):
        """Test text input for shop name."""
        mock_context.user_data["awaiting_input"] = "shopname"
        mock_update.message.text = "My Cool Shop"
        mock_update.effective_user.id = 123

        # Create mock vendors service
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        # Verify shop name saved to database
        mock_vendors.update_settings.assert_called_once_with(1, shop_name="My Cool Shop")
        assert mock_context.user_data["awaiting_input"] is None

    @pytest.mark.asyncio
    async def test_text_input_wallet_valid(self, mock_update, mock_context):
        """Test text input for valid wallet address."""
        mock_context.user_data["awaiting_input"] = "wallet"
        # Valid Monero address (95 chars starting with 4)
        wallet_address = "4" + "A" * 94
        mock_update.message.text = wallet_address
        mock_update.effective_user.id = 123

        # Create mock vendors service
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        # Verify wallet saved to database
        mock_vendors.update_settings.assert_called_once_with(1, wallet_address=wallet_address)
        assert mock_context.user_data["awaiting_input"] is None

    @pytest.mark.asyncio
    async def test_text_input_wallet_invalid(self, mock_update, mock_context):
        """Test text input for invalid wallet address."""
        mock_context.user_data["awaiting_input"] = "wallet"
        mock_update.message.text = "invalid_address"

        await handle_text_input(mock_update, mock_context)

        # Wallet should not be saved
        assert "wallet_address" not in mock_context.user_data

    @pytest.mark.asyncio
    async def test_text_input_no_awaiting(self, mock_update, mock_context):
        """Test text input when not awaiting any input."""
        mock_context.user_data["awaiting_input"] = None
        mock_update.message.text = "Random text"

        await handle_text_input(mock_update, mock_context)

        # Should not process the input
        mock_update.message.reply_text.assert_not_called()


class TestKeyboards:
    """Test keyboard generation functions."""

    def test_main_menu_keyboard(self):
        """Test main menu keyboard has expected buttons."""
        keyboard = main_menu_keyboard()

        assert isinstance(keyboard, InlineKeyboardMarkup)

        # Flatten keyboard to check buttons
        buttons = []
        for row in keyboard.inline_keyboard:
            for button in row:
                buttons.append(button.callback_data)

        assert "menu:products" in buttons
        assert "menu:orders" in buttons
        assert "menu:setup" in buttons
        assert "menu:help" in buttons


class TestMenuCallbackHandlers:
    """Additional tests for menu callback handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
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
    async def test_menu_callback_orders(self, mock_update, mock_context):
        """Test menu:orders callback."""
        mock_update.callback_query.data = "menu:orders"

        await handle_menu_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Your Orders" in call_args[0]

    @pytest.mark.asyncio
    async def test_menu_callback_setup(self, mock_update, mock_context):
        """Test menu:setup callback."""
        mock_update.callback_query.data = "menu:setup"

        await handle_menu_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Shop Setup" in call_args[0]

    @pytest.mark.asyncio
    async def test_menu_callback_admin(self, mock_update, mock_context):
        """Test menu:admin callback."""
        mock_update.callback_query.data = "menu:admin"

        await handle_menu_callback(mock_update, mock_context)

        mock_update.callback_query.answer.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Vendor Panel" in call_args[0]

    @pytest.mark.asyncio
    async def test_menu_callback_products_with_data(self, mock_update, mock_context):
        """Test menu:products callback with product data."""
        mock_update.callback_query.data = "menu:products"

        product = Product(id=1, name="Test", price_xmr=Decimal("1.0"), inventory=10, vendor_id=1)
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = [product]

        await handle_menu_callback(mock_update, mock_context, mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Available Products" in call_args[0]

    @pytest.mark.asyncio
    async def test_menu_callback_products_empty(self, mock_update, mock_context):
        """Test menu:products callback with no products."""
        mock_update.callback_query.data = "menu:products"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = []

        await handle_menu_callback(mock_update, mock_context, mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "No products" in call_args[0]


class TestSetupCallbackHandlers:
    """Additional tests for setup callback handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        user.full_name = "Test User"
        user.username = "testuser"
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_setup_callback_main(self, mock_update, mock_context):
        """Test setup:main callback."""
        mock_update.callback_query.data = "setup:main"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Shop Setup" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_become_vendor_new(self, mock_update, mock_context):
        """Test setup:become_vendor for new vendor."""
        mock_update.callback_query.data = "setup:become_vendor"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        mock_vendors.add_vendor.assert_called_once()
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Congratulations" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_become_vendor_already_vendor(self, mock_update, mock_context):
        """Test setup:become_vendor when already a vendor."""
        mock_update.callback_query.data = "setup:become_vendor"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "already a vendor" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_wallet(self, mock_update, mock_context):
        """Test setup:wallet callback."""
        mock_update.callback_query.data = "setup:wallet"

        await handle_setup_callback(mock_update, mock_context)

        assert mock_context.user_data['awaiting_input'] == 'wallet'
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Wallet Address" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_currency(self, mock_update, mock_context):
        """Test setup:currency callback."""
        mock_update.callback_query.data = "setup:currency"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.pricing_currency = "USD"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Pricing Currency" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_postage(self, mock_update, mock_context):
        """Test setup:postage callback."""
        mock_update.callback_query.data = "setup:postage"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.list_by_vendor.return_value = []

        await handle_setup_callback(mock_update, mock_context, mock_vendors, mock_postage)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Postage Options" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_view(self, mock_update, mock_context):
        """Test setup:view callback."""
        mock_update.callback_query.data = "setup:view"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.shop_name = "My Shop"
        mock_vendor.wallet_address = "4AAAABBBB..."
        mock_vendor.pricing_currency = "EUR"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR", "BTC"]

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Your Settings" in call_args[0]
        assert "My Shop" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_callback_view_not_vendor(self, mock_update, mock_context):
        """Test setup:view callback when not a vendor."""
        mock_update.callback_query.data = "setup:view"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Your Settings" in call_args[0]
        assert "Not set" in call_args[0]


class TestCurrencyCallback:
    """Tests for currency selection callback."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_currency_callback_short_data(self, mock_update, mock_context):
        """Test currency callback with short data."""
        mock_update.callback_query.data = "curr:select"  # Missing currency

        await handle_currency_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_currency_callback_select(self, mock_update, mock_context):
        """Test currency:select callback."""
        mock_update.callback_query.data = "curr:select:GBP"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_currency_callback(mock_update, mock_context, mock_vendors)

        mock_vendors.update_settings.assert_called_once_with(1, pricing_currency="GBP")
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Currency Set" in call_args[0]
        assert "GBP" in call_args[0]

    @pytest.mark.asyncio
    async def test_currency_callback_no_vendor(self, mock_update, mock_context):
        """Test currency:select callback without vendor."""
        mock_update.callback_query.data = "curr:select:EUR"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_currency_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Currency Set" in call_args[0]


class TestPostageCallback:
    """Tests for postage management callbacks."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_postage_callback_short_data(self, mock_update, mock_context):
        """Test postage callback with short data."""
        mock_update.callback_query.data = "postage"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_postage_callback_not_vendor(self, mock_update, mock_context):
        """Test postage callback when not a vendor."""
        mock_update.callback_query.data = "postage:add"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "need to be a vendor" in call_args[0]

    @pytest.mark.asyncio
    async def test_postage_callback_add(self, mock_update, mock_context):
        """Test postage:add callback."""
        mock_update.callback_query.data = "postage:add"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        assert mock_context.user_data['awaiting_input'] == 'postage_name'
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Add Postage" in call_args[0]

    @pytest.mark.asyncio
    async def test_postage_callback_edit(self, mock_update, mock_context):
        """Test postage:edit callback."""
        mock_update.callback_query.data = "postage:edit:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.name = "Standard"
        mock_postage_type.price_fiat = Decimal("5.00")
        mock_postage_type.currency = "USD"
        mock_postage_type.is_active = True
        mock_postage_type.description = "5-7 days"

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.get_postage_type.return_value = mock_postage_type

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Standard" in call_args[0]
        assert "$5.00" in call_args[0]

    @pytest.mark.asyncio
    async def test_postage_callback_edit_name(self, mock_update, mock_context):
        """Test postage:edit_name callback."""
        mock_update.callback_query.data = "postage:edit_name:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        assert mock_context.user_data['awaiting_input'] == 'edit_postage_name'
        assert mock_context.user_data['editing_postage'] == 1

    @pytest.mark.asyncio
    async def test_postage_callback_toggle(self, mock_update, mock_context):
        """Test postage:toggle callback."""
        mock_update.callback_query.data = "postage:toggle:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.name = "Express"
        mock_postage_type.price_fiat = Decimal("10.00")
        mock_postage_type.currency = "GBP"
        mock_postage_type.is_active = True
        mock_postage_type.description = "Next day"

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.toggle_active.return_value = mock_postage_type

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        mock_postage.toggle_active.assert_called_once_with(1)

    @pytest.mark.asyncio
    async def test_postage_callback_delete(self, mock_update, mock_context):
        """Test postage:delete callback."""
        mock_update.callback_query.data = "postage:delete:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.list_by_vendor.return_value = []

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        mock_postage.delete_postage_type.assert_called_once_with(1)
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Postage Deleted" in call_args[0]


class TestProductsCallback:
    """Tests for products browsing callbacks."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_products_callback_short_data(self, mock_update, mock_context):
        """Test products callback with short data."""
        mock_update.callback_query.data = "prods:page"

        await handle_products_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_products_callback_page(self, mock_update, mock_context):
        """Test products:page callback."""
        mock_update.callback_query.data = "prods:page:1"

        product = Product(id=1, name="Test", price_xmr=Decimal("1.0"), inventory=10, vendor_id=1)
        mock_context.user_data['products'] = [product]

        await handle_products_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Available Products" in call_args[0]


class TestProductCallback:
    """Tests for single product view callbacks."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_product_callback_short_data(self, mock_update, mock_context):
        """Test product callback with short data."""
        mock_update.callback_query.data = "prod:view"

        await handle_product_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_product_callback_view(self, mock_update, mock_context):
        """Test prod:view callback."""
        mock_update.callback_query.data = "prod:view:1"

        product = Product(
            id=1, name="Test Product", description="A test product",
            price_xmr=Decimal("1.5"), inventory=10, vendor_id=1
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        await handle_product_callback(mock_update, mock_context, mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Test Product" in call_args[0]
        assert "1.5" in call_args[0]

    @pytest.mark.asyncio
    async def test_product_callback_view_with_fiat_price(self, mock_update, mock_context):
        """Test prod:view callback with fiat pricing."""
        mock_update.callback_query.data = "prod:view:1"

        product = Product(
            id=1, name="Test Product", description="A test product",
            price_xmr=Decimal("0.5"), price_fiat=Decimal("25.00"),
            currency="GBP", inventory=10, vendor_id=1
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        await handle_product_callback(mock_update, mock_context, mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Test Product" in call_args[0]
        assert "£25.00" in call_args[0]

    @pytest.mark.asyncio
    async def test_product_callback_view_out_of_stock(self, mock_update, mock_context):
        """Test prod:view callback for out of stock product."""
        mock_update.callback_query.data = "prod:view:1"

        product = Product(
            id=1, name="Sold Out", description="No stock",
            price_xmr=Decimal("1.0"), inventory=0, vendor_id=1
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        await handle_product_callback(mock_update, mock_context, mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Out of stock" in call_args[0]


class TestOrderCallback:
    """Tests for order-related callbacks."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_order_callback_short_data(self, mock_update, mock_context):
        """Test order callback with short data."""
        mock_update.callback_query.data = "order:start"

        await handle_order_callback(mock_update, mock_context)

        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_callback_start(self, mock_update, mock_context):
        """Test order:start callback."""
        mock_update.callback_query.data = "order:start:1"

        product = Product(
            id=1, name="Test Product",
            price_xmr=Decimal("1.5"), inventory=5, vendor_id=1
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog)

        assert mock_context.user_data['ordering_product'] == 1
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Order: Test Product" in call_args[0]
        assert "Select quantity" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_callback_start_out_of_stock(self, mock_update, mock_context):
        """Test order:start callback for out of stock product."""
        mock_update.callback_query.data = "order:start:1"

        product = Product(
            id=1, name="Sold Out",
            price_xmr=Decimal("1.5"), inventory=0, vendor_id=1
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "no longer available" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_callback_start_product_not_found(self, mock_update, mock_context):
        """Test order:start callback when product not found."""
        mock_update.callback_query.data = "order:start:999"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = None

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "no longer available" in call_args[0]


class TestAdditionalTextInput:
    """Additional tests for text input handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        message.text = "Test input"
        update.message = message
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_text_input_wallet_with_8_prefix(self, mock_update, mock_context):
        """Test wallet address with 8 prefix (integrated address)."""
        mock_context.user_data['awaiting_input'] = 'wallet'
        # Valid integrated address (106 chars starting with 8)
        wallet_address = "8" + "B" * 105
        mock_update.message.text = wallet_address

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        mock_vendors.update_settings.assert_called_once()

    @pytest.mark.asyncio
    async def test_text_input_postage_name(self, mock_update, mock_context):
        """Test postage name input."""
        mock_context.user_data['awaiting_input'] = 'postage_name'
        mock_context.user_data['new_postage'] = {'vendor_id': 1}
        mock_update.message.text = "Express Shipping"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.pricing_currency = "USD"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        assert mock_context.user_data['new_postage']['name'] == "Express Shipping"
        assert mock_context.user_data['awaiting_input'] == 'postage_price'

    @pytest.mark.asyncio
    async def test_text_input_postage_price(self, mock_update, mock_context):
        """Test postage price input."""
        mock_context.user_data['awaiting_input'] = 'postage_price'
        mock_context.user_data['new_postage'] = {'vendor_id': 1, 'name': 'Standard'}
        mock_update.message.text = "5.99"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        assert mock_context.user_data['new_postage']['price'] == 5.99
        assert mock_context.user_data['awaiting_input'] == 'postage_desc'

    @pytest.mark.asyncio
    async def test_text_input_postage_price_invalid(self, mock_update, mock_context):
        """Test postage price input with invalid value."""
        mock_context.user_data['awaiting_input'] = 'postage_price'
        mock_context.user_data['new_postage'] = {'vendor_id': 1, 'name': 'Standard'}
        mock_update.message.text = "not a number"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_update.message.reply_text.assert_called()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Invalid price" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_delivery_address(self, mock_update, mock_context):
        """Test delivery address input."""
        mock_context.user_data['awaiting_input'] = 'delivery_address'
        mock_context.user_data['ordering_product'] = 1
        mock_context.user_data['order_quantity'] = 2
        mock_context.user_data['order_coin'] = 'xmr'
        mock_context.user_data['selected_postage'] = None
        mock_update.message.text = "123 Test Street"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.create_order.return_value = {
            'order_id': 42,
            'payment_address': '4ABC...',
            'payment_id': 'abc123',
            'total_xmr': Decimal("2.0"),
            'product_name': 'Test Product',
            'quantity': 2
        }

        await handle_text_input(mock_update, mock_context, orders=mock_orders)

        mock_orders.create_order.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Order #42" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_shopname(self, mock_update, mock_context):
        """Test shop name input with database save."""
        mock_context.user_data['awaiting_input'] = 'shopname'
        mock_update.message.text = "My Cool Shop"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        mock_vendors.update_settings.assert_called_once_with(1, shop_name="My Cool Shop")
        assert mock_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_text_input_wallet_save(self, mock_update, mock_context):
        """Test wallet address saves to database."""
        mock_context.user_data['awaiting_input'] = 'wallet'
        wallet_address = "4" + "A" * 94
        mock_update.message.text = wallet_address

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        mock_vendors.update_settings.assert_called_once_with(1, wallet_address=wallet_address)
        assert mock_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_text_input_delivery_address_with_postage(self, mock_update, mock_context):
        """Test delivery address with postage type included."""
        mock_context.user_data['awaiting_input'] = 'delivery_address'
        mock_context.user_data['ordering_product'] = 1
        mock_context.user_data['order_quantity'] = 2
        mock_context.user_data['order_postage_id'] = 5
        mock_update.message.text = "123 Test Street"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.create_order.return_value = {
            'order_id': 42,
            'payment_address': '4ABC...',
            'payment_id': 'abc123',
            'total_xmr': Decimal("2.0"),
            'product_name': 'Test Product',
            'quantity': 2
        }

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.name = "Express"
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.get_postage_type.return_value = mock_postage_type

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_text_input(mock_update, mock_context, orders=mock_orders, postage=mock_postage, vendors=mock_vendors)

        mock_orders.create_order.assert_called_once()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Postage:" in call_args[0]
        assert "Express" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_delivery_address_error(self, mock_update, mock_context):
        """Test delivery address with order creation error."""
        mock_context.user_data['awaiting_input'] = 'delivery_address'
        mock_context.user_data['ordering_product'] = 1
        mock_context.user_data['order_quantity'] = 2
        mock_update.message.text = "123 Test Street"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.create_order.side_effect = Exception("Payment service error")

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_text_input(mock_update, mock_context, orders=mock_orders, vendors=mock_vendors)

        call_args = mock_update.message.reply_text.call_args[0]
        assert "Error creating order" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_delivery_address_no_product(self, mock_update, mock_context):
        """Test delivery address when product session expired."""
        mock_context.user_data['awaiting_input'] = 'delivery_address'
        mock_context.user_data['ordering_product'] = None
        mock_update.message.text = "123 Test Street"

        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = None

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors)

        call_args = mock_update.message.reply_text.call_args[0]
        assert "session expired" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_postage_desc(self, mock_update, mock_context):
        """Test postage description input creates postage type."""
        mock_context.user_data['awaiting_input'] = 'postage_desc'
        mock_context.user_data['new_postage'] = {'vendor_id': 1, 'name': 'Standard', 'price': 5.99}
        mock_update.message.text = "3-5 business days"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.pricing_currency = "USD"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.name = "Standard"
        mock_postage_type.price_fiat = Decimal("5.99")
        mock_postage_type.currency = "USD"

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.add_postage_type.return_value = mock_postage_type
        mock_postage.list_by_vendor.return_value = [mock_postage_type]

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_postage.add_postage_type.assert_called_once()
        assert mock_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_text_input_postage_desc_skip(self, mock_update, mock_context):
        """Test postage description input with skip."""
        mock_context.user_data['awaiting_input'] = 'postage_desc'
        mock_context.user_data['new_postage'] = {'vendor_id': 1, 'name': 'Standard', 'price': 5.99}
        mock_update.message.text = "skip"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.pricing_currency = "EUR"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.name = "Standard"
        mock_postage_type.price_fiat = Decimal("5.99")
        mock_postage_type.currency = "EUR"

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.add_postage_type.return_value = mock_postage_type
        mock_postage.list_by_vendor.return_value = [mock_postage_type]

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        # Verify description was None (skip)
        call_args = mock_postage.add_postage_type.call_args
        assert call_args[1]['description'] is None

    @pytest.mark.asyncio
    async def test_text_input_edit_postage_name(self, mock_update, mock_context):
        """Test editing postage name."""
        mock_context.user_data['awaiting_input'] = 'edit_postage_name'
        mock_context.user_data['editing_postage'] = 5
        mock_update.message.text = "New Name"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_postage.update_postage_type.assert_called_once_with(5, name="New Name")
        assert mock_context.user_data['awaiting_input'] is None
        assert mock_context.user_data['editing_postage'] is None

    @pytest.mark.asyncio
    async def test_text_input_edit_postage_price(self, mock_update, mock_context):
        """Test editing postage price."""
        mock_context.user_data['awaiting_input'] = 'edit_postage_price'
        mock_context.user_data['editing_postage'] = 5
        mock_update.message.text = "12.50"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_postage.update_postage_type.assert_called_once()
        assert mock_context.user_data['awaiting_input'] is None

    @pytest.mark.asyncio
    async def test_text_input_edit_postage_price_invalid(self, mock_update, mock_context):
        """Test editing postage price with invalid value."""
        mock_context.user_data['awaiting_input'] = 'edit_postage_price'
        mock_context.user_data['editing_postage'] = 5
        mock_update.message.text = "invalid"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_postage.update_postage_type.assert_not_called()
        call_args = mock_update.message.reply_text.call_args[0]
        assert "Invalid price" in call_args[0]

    @pytest.mark.asyncio
    async def test_text_input_edit_postage_desc(self, mock_update, mock_context):
        """Test editing postage description."""
        mock_context.user_data['awaiting_input'] = 'edit_postage_desc'
        mock_context.user_data['editing_postage'] = 5
        mock_update.message.text = "New description"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        mock_postage = MagicMock(spec=PostageService)

        await handle_text_input(mock_update, mock_context, vendors=mock_vendors, postage=mock_postage)

        mock_postage.update_postage_type.assert_called_once_with(5, description="New description")
        assert mock_context.user_data['awaiting_input'] is None


class TestStatusCommand:
    """Tests for status command."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with message."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.message = message
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.args = []
        return context

    @pytest.mark.asyncio
    async def test_status_invalid_order_id(self, mock_update, mock_context):
        """Test status command with invalid order ID."""
        mock_context.args = ["abc"]  # Not a number

        from bot.handlers.user import order_status
        mock_orders = MagicMock(spec=OrderService)
        await order_status(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.message.reply_text.call_args[0]
        assert "Invalid order ID" in call_args[0]


class TestMenuCallbackNoCatalog:
    """Tests for menu callback when catalog is not available."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_menu_products_no_catalog(self, mock_update, mock_context):
        """Test menu:products when catalog is None."""
        mock_update.callback_query.data = "menu:products"

        await handle_menu_callback(mock_update, mock_context, catalog=None)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "loading" in call_args[0]


class TestSetupCallbackPayments:
    """Tests for setup callback with payment-related actions."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_setup_payments_with_vendor(self, mock_update, mock_context):
        """Test setup:payments with existing vendor."""
        mock_update.callback_query.data = "setup:payments"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR", "BTC"]

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        mock_vendors.get_accepted_payments_list.assert_called_with(mock_vendor)
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Payment Methods" in call_args[0]

    @pytest.mark.asyncio
    async def test_setup_currency_with_vendor(self, mock_update, mock_context):
        """Test setup:currency with existing vendor."""
        mock_update.callback_query.data = "setup:currency"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendor.pricing_currency = "GBP"
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_setup_callback(mock_update, mock_context, mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Pricing Currency" in call_args[0]


class TestPaymentToggle:
    """Tests for payment toggle callback."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_payment_toggle_short_data(self, mock_update, mock_context):
        """Test payment toggle with short data."""
        mock_update.callback_query.data = "pay"  # Only 1 part

        from bot.handlers.user import handle_payment_toggle_callback
        await handle_payment_toggle_callback(mock_update, mock_context)

        # Should return early without editing
        mock_update.callback_query.edit_message_text.assert_not_called()

    @pytest.mark.asyncio
    async def test_payment_toggle_remove_coin(self, mock_update, mock_context):
        """Test payment toggle removes coin when already selected."""
        mock_update.callback_query.data = "pay:toggle:BTC"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR", "BTC", "LTC"]

        from bot.handlers.user import handle_payment_toggle_callback
        await handle_payment_toggle_callback(mock_update, mock_context, vendors=mock_vendors)

        # Should have called update_settings with BTC removed
        mock_vendors.update_settings.assert_called_once()
        call_args = mock_vendors.update_settings.call_args
        assert "BTC" not in call_args[1]['accepted_payments']

    @pytest.mark.asyncio
    async def test_payment_toggle_save_with_vendor(self, mock_update, mock_context):
        """Test payment toggle save action with vendor."""
        mock_update.callback_query.data = "pay:save"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_vendors.get_accepted_payments_list.return_value = ["XMR", "ETH"]

        from bot.handlers.user import handle_payment_toggle_callback
        await handle_payment_toggle_callback(mock_update, mock_context, vendors=mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Saved" in call_args[0]
        assert "XMR" in call_args[0]


class TestCurrencyCallbackExtended:
    """Extended tests for currency callback."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_currency_select_gbp(self, mock_update, mock_context):
        """Test currency selection with GBP."""
        mock_update.callback_query.data = "curr:select:GBP"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_currency_callback(mock_update, mock_context, vendors=mock_vendors)

        mock_vendors.update_settings.assert_called_once_with(1, pricing_currency="GBP")
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "£" in call_args[0]

    @pytest.mark.asyncio
    async def test_currency_select_eur(self, mock_update, mock_context):
        """Test currency selection with EUR."""
        mock_update.callback_query.data = "curr:select:EUR"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendor.id = 1
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor

        await handle_currency_callback(mock_update, mock_context, vendors=mock_vendors)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "€" in call_args[0]


class TestPostageCallbackExtended:
    """Extended tests for postage callback."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        user = MagicMock(spec=User)
        user.id = 123
        update.effective_user = user
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_postage_edit_price(self, mock_update, mock_context):
        """Test postage:edit_price callback."""
        mock_update.callback_query.data = "postage:edit_price:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        assert mock_context.user_data['awaiting_input'] == 'edit_postage_price'
        assert mock_context.user_data['editing_postage'] == 1

    @pytest.mark.asyncio
    async def test_postage_edit_desc(self, mock_update, mock_context):
        """Test postage:edit_desc callback."""
        mock_update.callback_query.data = "postage:edit_desc:1"

        mock_vendor = MagicMock(spec=Vendor)
        mock_vendors = MagicMock(spec=VendorService)
        mock_vendors.get_by_telegram_id.return_value = mock_vendor
        mock_postage = MagicMock(spec=PostageService)

        await handle_postage_callback(mock_update, mock_context, mock_vendors, mock_postage)

        assert mock_context.user_data['awaiting_input'] == 'edit_postage_desc'
        assert mock_context.user_data['editing_postage'] == 1


class TestOrderCallbackExtended:
    """Extended tests for order callback handlers."""

    @pytest.fixture
    def mock_update(self):
        """Create mock update with callback query."""
        update = MagicMock(spec=Update)
        query = MagicMock(spec=CallbackQuery)
        query.answer = AsyncMock()
        query.edit_message_text = AsyncMock()
        update.callback_query = query
        return update

    @pytest.fixture
    def mock_context(self):
        """Create mock context."""
        context = MagicMock()
        context.user_data = {}
        return context

    @pytest.mark.asyncio
    async def test_order_qty_with_postage_options(self, mock_update, mock_context):
        """Test order:qty callback with postage options."""
        mock_update.callback_query.data = "order:qty:1:2"

        product = Product(
            id=1, name="Test Product",
            price_xmr=Decimal("1.5"), inventory=5, vendor_id=10
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        mock_postage_type = PostageType(
            id=1, vendor_id=10, name="Express",
            price_fiat=Decimal("5.00"), currency="USD", is_active=True
        )
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.list_by_vendor.return_value = [mock_postage_type]

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog, postage=mock_postage)

        assert mock_context.user_data['order_quantity'] == 2
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Quantity: 2" in call_args[0]
        assert "delivery option" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_qty_no_postage_options(self, mock_update, mock_context):
        """Test order:qty callback without postage options."""
        mock_update.callback_query.data = "order:qty:1:3"

        product = Product(
            id=1, name="Test Product",
            price_xmr=Decimal("1.5"), inventory=5, vendor_id=10
        )
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = product

        mock_postage = MagicMock(spec=PostageService)
        mock_postage.list_by_vendor.return_value = []

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog, postage=mock_postage)

        assert mock_context.user_data['awaiting_input'] == 'delivery_address'
        assert mock_context.user_data['order_postage_id'] is None

    @pytest.mark.asyncio
    async def test_order_qty_product_not_found(self, mock_update, mock_context):
        """Test order:qty callback when product not found."""
        mock_update.callback_query.data = "order:qty:999:2"

        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.get_product.return_value = None

        mock_postage = MagicMock(spec=PostageService)

        await handle_order_callback(mock_update, mock_context, catalog=mock_catalog, postage=mock_postage)

        # Should go to delivery address flow directly when product not found
        assert mock_context.user_data['order_postage_id'] is None

    @pytest.mark.asyncio
    async def test_order_postage_selection(self, mock_update, mock_context):
        """Test order:postage callback."""
        mock_update.callback_query.data = "order:postage:1:2:5"

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.id = 5
        mock_postage_type.name = "Express"
        mock_postage_type.price_fiat = Decimal("10.00")
        mock_postage_type.currency = "USD"
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.get_postage_type.return_value = mock_postage_type

        await handle_order_callback(mock_update, mock_context, postage=mock_postage)

        assert mock_context.user_data['order_postage_id'] == 5
        assert mock_context.user_data['awaiting_input'] == 'delivery_address'
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Postage:" in call_args[0]
        assert "Express" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_postage_selection_no_postage(self, mock_update, mock_context):
        """Test order:postage callback with postage_id=0 (no postage)."""
        mock_update.callback_query.data = "order:postage:1:2:0"

        mock_postage = MagicMock(spec=PostageService)

        await handle_order_callback(mock_update, mock_context, postage=mock_postage)

        assert mock_context.user_data['order_postage_id'] is None
        assert mock_context.user_data['awaiting_input'] == 'delivery_address'

    @pytest.mark.asyncio
    async def test_order_postage_selection_gbp(self, mock_update, mock_context):
        """Test order:postage callback with GBP currency."""
        mock_update.callback_query.data = "order:postage:1:2:5"

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.id = 5
        mock_postage_type.name = "Royal Mail"
        mock_postage_type.price_fiat = Decimal("5.00")
        mock_postage_type.currency = "GBP"
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.get_postage_type.return_value = mock_postage_type

        await handle_order_callback(mock_update, mock_context, postage=mock_postage)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "£5.00" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_postage_selection_eur(self, mock_update, mock_context):
        """Test order:postage callback with EUR currency."""
        mock_update.callback_query.data = "order:postage:1:2:5"

        mock_postage_type = MagicMock(spec=PostageType)
        mock_postage_type.id = 5
        mock_postage_type.name = "DHL Express"
        mock_postage_type.price_fiat = Decimal("7.50")
        mock_postage_type.currency = "EUR"
        mock_postage = MagicMock(spec=PostageService)
        mock_postage.get_postage_type.return_value = mock_postage_type

        await handle_order_callback(mock_update, mock_context, postage=mock_postage)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "€7.50" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status(self, mock_update, mock_context):
        """Test order:status callback."""
        mock_update.callback_query.data = "order:status:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "PAID"
        mock_order.created_at = MagicMock()
        mock_order.created_at.strftime.return_value = "2024-01-15 10:30"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Order #42" in call_args[0]
        assert "Payment received" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status_new(self, mock_update, mock_context):
        """Test order:status callback with NEW status."""
        mock_update.callback_query.data = "order:status:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "NEW"
        mock_order.created_at = MagicMock()
        mock_order.created_at.strftime.return_value = "2024-01-15 10:30"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Awaiting payment" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status_fulfilled(self, mock_update, mock_context):
        """Test order:status callback with FULFILLED status."""
        mock_update.callback_query.data = "order:status:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "FULFILLED"
        mock_order.created_at = MagicMock()
        mock_order.created_at.strftime.return_value = "2024-01-15 10:30"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Completed" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status_cancelled(self, mock_update, mock_context):
        """Test order:status callback with CANCELLED status."""
        mock_update.callback_query.data = "order:status:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "CANCELLED"
        mock_order.created_at = MagicMock()
        mock_order.created_at.strftime.return_value = "2024-01-15 10:30"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Cancelled" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_status_not_found(self, mock_update, mock_context):
        """Test order:status callback when order not found."""
        mock_update.callback_query.data = "order:status:999"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = None

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        mock_update.callback_query.answer.assert_called_with("Order not found", show_alert=True)

    @pytest.mark.asyncio
    async def test_order_status_message_unchanged(self, mock_update, mock_context):
        """Test order:status callback when message unchanged."""
        mock_update.callback_query.data = "order:status:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "PAID"
        mock_order.created_at = MagicMock()
        mock_order.created_at.strftime.return_value = "2024-01-15 10:30"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order

        mock_update.callback_query.edit_message_text.side_effect = Exception("Message not modified")

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        mock_update.callback_query.answer.assert_called_with("Status unchanged", show_alert=False)

    @pytest.mark.asyncio
    async def test_order_pay(self, mock_update, mock_context):
        """Test order:pay callback."""
        mock_update.callback_query.data = "order:pay:42:xmr"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_payment_info.return_value = {
            'amount': '1.5',
            'address': '4ABC123...'
        }

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Order #42" in call_args[0]
        assert "Pay with xmr" in call_args[0]
        assert "1.5" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_pay_includes_payment_id(self, mock_update, mock_context):
        """Test order:pay callback includes payment ID when provided."""
        mock_update.callback_query.data = "order:pay:42:xmr"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_payment_info.return_value = {
            'amount': '1.5',
            'address': '4ABC123...',
            'payment_id': 'pid123'
        }

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Payment ID" in call_args[0]
        assert "pid123" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_pay_error(self, mock_update, mock_context):
        """Test order:pay callback with error."""
        mock_update.callback_query.data = "order:pay:42:xmr"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_payment_info.side_effect = Exception("Payment error")

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "being generated" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_cancel(self, mock_update, mock_context):
        """Test order:cancel callback."""
        mock_update.callback_query.data = "order:cancel:42"

        await handle_order_callback(mock_update, mock_context)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Cancel Order #42" in call_args[0]
        assert "Are you sure" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_confirm_cancel(self, mock_update, mock_context):
        """Test order:confirm_cancel callback."""
        mock_update.callback_query.data = "order:confirm_cancel:42"

        mock_orders = MagicMock(spec=OrderService)

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        mock_orders.cancel_order.assert_called_once_with(42)
        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Order #42 Cancelled" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_confirm_cancel_error(self, mock_update, mock_context):
        """Test order:confirm_cancel callback with error."""
        mock_update.callback_query.data = "order:confirm_cancel:42"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.cancel_order.side_effect = Exception("Cancel failed")

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Could not cancel" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_view(self, mock_update, mock_context):
        """Test order:view callback."""
        mock_update.callback_query.data = "order:view:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "PAID"
        mock_order.quantity = 3

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order
        mock_orders.get_address.return_value = "123 Short Street"

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Order #42" in call_args[0]
        assert "Quantity:" in call_args[0]
        assert "123 Short Street" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_view_long_address(self, mock_update, mock_context):
        """Test order:view callback with long address truncation."""
        mock_update.callback_query.data = "order:view:42"

        mock_order = MagicMock()
        mock_order.id = 42
        mock_order.state = "NEW"
        mock_order.quantity = 1

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = mock_order
        mock_orders.get_address.return_value = "123 Very Long Street Name That Should Be Truncated"

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "..." in call_args[0]

    @pytest.mark.asyncio
    async def test_order_view_not_found(self, mock_update, mock_context):
        """Test order:view callback when order not found."""
        mock_update.callback_query.data = "order:view:999"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.return_value = None

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "not found" in call_args[0]

    @pytest.mark.asyncio
    async def test_order_view_error(self, mock_update, mock_context):
        """Test order:view callback with error."""
        mock_update.callback_query.data = "order:view:42"

        mock_orders = MagicMock(spec=OrderService)
        mock_orders.get_order.side_effect = Exception("Database error")

        await handle_order_callback(mock_update, mock_context, orders=mock_orders)

        call_args = mock_update.callback_query.edit_message_text.call_args[0]
        assert "Could not load" in call_args[0]
