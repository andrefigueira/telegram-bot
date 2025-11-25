"""Tests for user command handlers."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from telegram import Update, Message, User

from bot.handlers.user import start, list_products, order
from bot.services.catalog import CatalogService
from bot.services.orders import OrderService
from bot.models import Product


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
        return context

    @pytest.mark.asyncio
    async def test_start_command(self, mock_update, mock_context):
        """Test /start command handler."""
        await start(mock_update, mock_context)
        
        mock_update.message.reply_text.assert_called_once_with("Welcome to the shop!")

    @pytest.mark.asyncio
    async def test_list_products_no_products(self, mock_update, mock_context):
        """Test /list command with no products."""
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = []
        
        await list_products(mock_update, mock_context, mock_catalog)
        
        mock_update.message.reply_text.assert_called_once_with("No products found.")

    @pytest.mark.asyncio
    async def test_list_products_with_products(self, mock_update, mock_context):
        """Test /list command with products."""
        # Create test products
        product1 = Product(id=1, name="Product 1", description="", price_xmr=0.5, inventory=10, vendor_id=1)
        product2 = Product(id=2, name="Product 2", description="", price_xmr=1.0, inventory=0, vendor_id=1)
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.list_products.return_value = [product1, product2]
        
        await list_products(mock_update, mock_context, mock_catalog)
        
        # Check reply was called
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        
        # Verify content
        assert "Available Products:" in reply_text
        assert "Product 1" in reply_text
        assert "0.5 XMR" in reply_text
        assert "In Stock" in reply_text
        assert "Product 2" in reply_text
        assert "1.0 XMR" in reply_text
        assert "Out of Stock" in reply_text

    @pytest.mark.asyncio
    async def test_list_products_with_search(self, mock_update, mock_context):
        """Test /list command with search query."""
        mock_context.args = ["laptop"]
        
        product = Product(id=1, name="Gaming Laptop", description="", price_xmr=2.0, inventory=5, vendor_id=1)
        
        mock_catalog = MagicMock(spec=CatalogService)
        mock_catalog.search.return_value = [product]
        
        await list_products(mock_update, mock_context, mock_catalog)
        
        # Verify search was called
        mock_catalog.search.assert_called_once_with("laptop")
        mock_catalog.list_products.assert_not_called()

    @pytest.mark.asyncio
    async def test_order_insufficient_args(self, mock_update, mock_context):
        """Test /order command with insufficient arguments."""
        mock_context.args = ["1", "2"]  # Missing address
        mock_orders = MagicMock(spec=OrderService)
        
        await order(mock_update, mock_context, mock_orders)
        
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "Usage:" in reply_text

    @pytest.mark.asyncio
    async def test_order_invalid_args(self, mock_update, mock_context):
        """Test /order command with invalid arguments."""
        mock_context.args = ["abc", "def", "address"]  # Invalid numbers
        mock_orders = MagicMock(spec=OrderService)
        
        await order(mock_update, mock_context, mock_orders)
        
        mock_update.message.reply_text.assert_called_once()
        reply_text = mock_update.message.reply_text.call_args[0][0]
        assert "Invalid product ID or quantity" in reply_text

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
        reply_text = mock_update.message.reply_text.call_args[0][0]
        
        assert "Order #42 created!" in reply_text
        assert "2.0 XMR" in reply_text
        assert "4A1234567890abcdef" in reply_text
        assert mock_update.message.reply_text.call_args[1]["parse_mode"] == "Markdown"

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