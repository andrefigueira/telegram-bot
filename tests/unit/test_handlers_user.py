"""Tests for user command handlers."""

import pytest
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
    HELP_TEXT,
    SETUP_INTRO,
)
from bot.services.catalog import CatalogService
from bot.services.orders import OrderService
from bot.services.vendors import VendorService
from bot.models import Product, Vendor
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
