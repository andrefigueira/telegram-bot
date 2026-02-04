"""Tests for keyboard builder functions."""

import pytest
from unittest.mock import MagicMock
from telegram import InlineKeyboardMarkup, InlineKeyboardButton

from bot.keyboards import (
    main_menu_keyboard,
    help_keyboard,
    setup_keyboard,
    payment_methods_keyboard,
    currency_keyboard,
    products_keyboard,
    product_detail_keyboard,
    quantity_keyboard,
    payment_coin_keyboard,
    order_confirmation_keyboard,
    orders_keyboard,
    confirm_cancel_keyboard,
    admin_menu_keyboard,
    vendor_products_keyboard,
    product_edit_keyboard,
    confirm_delete_keyboard,
    postage_management_keyboard,
    postage_edit_keyboard,
    postage_selection_keyboard,
    vendor_orders_keyboard,
    vendor_order_detail_keyboard,
    super_admin_keyboard,
    commission_rate_keyboard,
    _format_product_price,
    SUPPORTED_COINS,
    SUPPORTED_CURRENCIES,
)


class TestMainMenuKeyboard:
    """Test main menu keyboard."""

    def test_main_menu_keyboard(self):
        """Test main menu keyboard structure."""
        kb = main_menu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)
        assert len(kb.inline_keyboard) == 2

    def test_main_menu_has_products_button(self):
        """Test main menu has products button."""
        kb = main_menu_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        product_btns = [b for b in buttons if b.callback_data == "menu:products"]
        assert len(product_btns) == 1


class TestHelpKeyboard:
    """Test help keyboard."""

    def test_help_keyboard(self):
        """Test help keyboard structure."""
        kb = help_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)
        assert len(kb.inline_keyboard) == 1
        assert kb.inline_keyboard[0][0].callback_data == "menu:main"


class TestSetupKeyboard:
    """Test setup keyboard."""

    def test_setup_keyboard_non_vendor(self):
        """Test setup keyboard for non-vendor."""
        kb = setup_keyboard(is_vendor=False)
        assert isinstance(kb, InlineKeyboardMarkup)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        vendor_btns = [b for b in buttons if "become_vendor" in b.callback_data]
        assert len(vendor_btns) == 1

    def test_setup_keyboard_vendor(self):
        """Test setup keyboard for vendor."""
        kb = setup_keyboard(is_vendor=True)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        manage_btns = [b for b in buttons if "admin:products" in b.callback_data]
        assert len(manage_btns) == 1
        vendor_btns = [b for b in buttons if "become_vendor" in b.callback_data]
        assert len(vendor_btns) == 0


class TestPaymentMethodsKeyboard:
    """Test payment methods keyboard."""

    def test_payment_methods_keyboard_default(self):
        """Test payment methods with default selection."""
        kb = payment_methods_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        xmr_btns = [b for b in buttons if "XMR" in b.text and "✓" in b.text]
        assert len(xmr_btns) == 1

    def test_payment_methods_keyboard_custom_selection(self):
        """Test payment methods with custom selection."""
        kb = payment_methods_keyboard(selected=["BTC", "ETH"])
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        btc_btns = [b for b in buttons if "BTC" in b.text and "✓" in b.text]
        eth_btns = [b for b in buttons if "ETH" in b.text and "✓" in b.text]
        xmr_btns = [b for b in buttons if "XMR" in b.text and "○" in b.text]
        assert len(btc_btns) == 1
        assert len(eth_btns) == 1
        assert len(xmr_btns) == 1

    def test_payment_methods_has_save_button(self):
        """Test payment methods has save button."""
        kb = payment_methods_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        save_btns = [b for b in buttons if b.callback_data == "pay:save"]
        assert len(save_btns) == 1


class TestCurrencyKeyboard:
    """Test currency keyboard."""

    def test_currency_keyboard_default(self):
        """Test currency keyboard with default selection."""
        kb = currency_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        usd_btns = [b for b in buttons if "USD" in b.text and ">" in b.text]
        assert len(usd_btns) == 1

    def test_currency_keyboard_custom_selection(self):
        """Test currency keyboard with custom selection."""
        kb = currency_keyboard(current="GBP")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        gbp_btns = [b for b in buttons if "GBP" in b.text and ">" in b.text]
        usd_btns = [b for b in buttons if "USD" in b.text and ">" in b.text]
        assert len(gbp_btns) == 1
        assert len(usd_btns) == 0


class TestFormatProductPrice:
    """Test product price formatting."""

    def test_format_product_price_xmr_only(self):
        """Test formatting XMR-only price."""
        product = MagicMock()
        product.price_xmr = 0.5
        product.currency = "XMR"
        result = _format_product_price(product)
        assert "0.5 XMR" in result

    def test_format_product_price_usd(self):
        """Test formatting USD price."""
        product = MagicMock()
        product.price_fiat = 100.50
        product.currency = "USD"
        result = _format_product_price(product)
        assert "$100.50" in result

    def test_format_product_price_gbp(self):
        """Test formatting GBP price."""
        product = MagicMock()
        product.price_fiat = 75.00
        product.currency = "GBP"
        result = _format_product_price(product)
        assert "£75.00" in result

    def test_format_product_price_eur(self):
        """Test formatting EUR price."""
        product = MagicMock()
        product.price_fiat = 50.00
        product.currency = "EUR"
        result = _format_product_price(product)
        assert "€50.00" in result

    def test_format_product_price_unknown_currency(self):
        """Test formatting unknown currency falls back to $."""
        product = MagicMock()
        product.price_fiat = 100.00
        product.currency = "ABC"
        result = _format_product_price(product)
        assert "$100.00" in result


class TestProductsKeyboard:
    """Test products keyboard."""

    def test_products_keyboard_empty(self):
        """Test products keyboard with no products."""
        kb = products_keyboard([])
        assert isinstance(kb, InlineKeyboardMarkup)
        assert len(kb.inline_keyboard) == 1  # Just back button

    def test_products_keyboard_with_products(self):
        """Test products keyboard with products."""
        products = [
            MagicMock(id=1, name="Product 1", price_xmr=0.1, inventory=5, currency="XMR"),
            MagicMock(id=2, name="Product 2", price_xmr=0.2, inventory=0, currency="XMR"),
        ]
        kb = products_keyboard(products)
        assert len(kb.inline_keyboard) == 3  # 2 products + back button
        assert "In Stock" in kb.inline_keyboard[0][0].text
        assert "Out of Stock" in kb.inline_keyboard[1][0].text

    def test_products_keyboard_pagination_first_page(self):
        """Test products keyboard pagination on first page."""
        products = [MagicMock(id=i, name=f"P{i}", price_xmr=0.1, inventory=1, currency="XMR") for i in range(10)]
        kb = products_keyboard(products, page=0, per_page=5)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        next_btns = [b for b in buttons if "Next" in b.text]
        prev_btns = [b for b in buttons if "Prev" in b.text]
        assert len(next_btns) == 1
        assert len(prev_btns) == 0

    def test_products_keyboard_pagination_middle_page(self):
        """Test products keyboard pagination on middle page."""
        products = [MagicMock(id=i, name=f"P{i}", price_xmr=0.1, inventory=1, currency="XMR") for i in range(15)]
        kb = products_keyboard(products, page=1, per_page=5)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        next_btns = [b for b in buttons if "Next" in b.text]
        prev_btns = [b for b in buttons if "Prev" in b.text]
        assert len(next_btns) == 1
        assert len(prev_btns) == 1

    def test_products_keyboard_pagination_last_page(self):
        """Test products keyboard pagination on last page."""
        products = [MagicMock(id=i, name=f"P{i}", price_xmr=0.1, inventory=1, currency="XMR") for i in range(8)]
        kb = products_keyboard(products, page=1, per_page=5)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        next_btns = [b for b in buttons if "Next" in b.text]
        prev_btns = [b for b in buttons if "Prev" in b.text]
        assert len(next_btns) == 0
        assert len(prev_btns) == 1


class TestProductDetailKeyboard:
    """Test product detail keyboard."""

    def test_product_detail_in_stock(self):
        """Test product detail keyboard when in stock."""
        kb = product_detail_keyboard(1, in_stock=True)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        order_btns = [b for b in buttons if "order:start:1" in b.callback_data]
        assert len(order_btns) == 1

    def test_product_detail_out_of_stock(self):
        """Test product detail keyboard when out of stock."""
        kb = product_detail_keyboard(1, in_stock=False)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        order_btns = [b for b in buttons if "order:start" in b.callback_data]
        assert len(order_btns) == 0


class TestQuantityKeyboard:
    """Test quantity keyboard."""

    def test_quantity_keyboard_default(self):
        """Test quantity keyboard with default max."""
        kb = quantity_keyboard(1)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        # Should have 1-10 + cancel
        qty_btns = [b for b in buttons if b.callback_data.startswith("order:qty:")]
        assert len(qty_btns) == 10

    def test_quantity_keyboard_small_max(self):
        """Test quantity keyboard with small max."""
        kb = quantity_keyboard(1, max_qty=3)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        qty_btns = [b for b in buttons if b.callback_data.startswith("order:qty:")]
        assert len(qty_btns) == 3

    def test_quantity_keyboard_large_max(self):
        """Test quantity keyboard caps at 10."""
        kb = quantity_keyboard(1, max_qty=20)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        qty_btns = [b for b in buttons if b.callback_data.startswith("order:qty:")]
        assert len(qty_btns) == 10


class TestPaymentCoinKeyboard:
    """Test payment coin keyboard."""

    def test_payment_coin_keyboard_default(self):
        """Test payment coin keyboard with default coins."""
        kb = payment_coin_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        coin_btns = [b for b in buttons if "order:currency:" in b.callback_data]
        assert len(coin_btns) == 3  # XMR, BTC, ETH by default

    def test_payment_coin_keyboard_multiple(self):
        """Test payment coin keyboard with multiple coins."""
        kb = payment_coin_keyboard(accepted_coins=["XMR", "BTC"])
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        coin_btns = [b for b in buttons if "order:currency:" in b.callback_data]
        assert len(coin_btns) == 2

    def test_payment_coin_keyboard_has_cancel(self):
        """Test payment coin keyboard has cancel button."""
        kb = payment_coin_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        cancel_btns = [b for b in buttons if "menu:main" in b.callback_data]
        assert len(cancel_btns) == 1


class TestOrderConfirmationKeyboard:
    """Test order confirmation keyboard."""

    def test_order_confirmation_keyboard(self):
        """Test order confirmation keyboard."""
        kb = order_confirmation_keyboard(456)
        assert isinstance(kb, InlineKeyboardMarkup)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        status_btns = [b for b in buttons if "order:status:456" in b.callback_data]
        assert len(status_btns) == 1


class TestOrdersKeyboard:
    """Test orders keyboard."""

    def test_orders_keyboard_empty(self):
        """Test orders keyboard with no orders."""
        kb = orders_keyboard([])
        assert len(kb.inline_keyboard) == 1  # Just back button

    def test_orders_keyboard_with_orders(self):
        """Test orders keyboard with orders."""
        orders = [
            MagicMock(id=1, state="pending"),
            MagicMock(id=2, state="paid"),
            MagicMock(id=3, state="fulfilled"),
            MagicMock(id=4, state="cancelled"),
            MagicMock(id=5, state="expired"),
            MagicMock(id=6, state="unknown"),
        ]
        kb = orders_keyboard(orders)
        assert len(kb.inline_keyboard) == 7  # 6 orders + back

    def test_orders_keyboard_max_10(self):
        """Test orders keyboard shows max 10 orders."""
        orders = [MagicMock(id=i, state="pending") for i in range(15)]
        kb = orders_keyboard(orders)
        assert len(kb.inline_keyboard) == 11  # 10 orders + back


class TestConfirmCancelKeyboard:
    """Test confirm cancel keyboard."""

    def test_confirm_cancel_keyboard(self):
        """Test confirm cancel keyboard."""
        kb = confirm_cancel_keyboard(789)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        confirm_btns = [b for b in buttons if "order:confirm_cancel:789" in b.callback_data]
        keep_btns = [b for b in buttons if "order:view:789" in b.callback_data]
        assert len(confirm_btns) == 1
        assert len(keep_btns) == 1


class TestAdminMenuKeyboard:
    """Test admin menu keyboard."""

    def test_admin_menu_keyboard(self):
        """Test admin menu keyboard."""
        kb = admin_menu_keyboard()
        assert isinstance(kb, InlineKeyboardMarkup)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        add_btns = [b for b in buttons if "admin:add_product" in b.callback_data]
        assert len(add_btns) == 1


class TestVendorProductsKeyboard:
    """Test vendor products keyboard."""

    def test_vendor_products_keyboard_empty(self):
        """Test vendor products keyboard with no products."""
        kb = vendor_products_keyboard([])
        assert len(kb.inline_keyboard) == 2  # Add + back

    def test_vendor_products_keyboard_with_products(self):
        """Test vendor products keyboard with products."""
        products = [
            MagicMock(id=1, name="P1", price_xmr=0.1, inventory=5, currency="XMR"),
            MagicMock(id=2, name="P2", price_xmr=0.2, inventory=0, currency="XMR"),
        ]
        kb = vendor_products_keyboard(products)
        assert len(kb.inline_keyboard) == 4  # 2 products + add + back
        assert "Active" in kb.inline_keyboard[0][0].text
        assert "Out" in kb.inline_keyboard[1][0].text


class TestProductEditKeyboard:
    """Test product edit keyboard."""

    def test_product_edit_keyboard(self):
        """Test product edit keyboard."""
        kb = product_edit_keyboard(123)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        edit_name = [b for b in buttons if "vendor:edit_name:123" in b.callback_data]
        edit_price = [b for b in buttons if "vendor:edit_price:123" in b.callback_data]
        delete = [b for b in buttons if "vendor:delete:123" in b.callback_data]
        assert len(edit_name) == 1
        assert len(edit_price) == 1
        assert len(delete) == 1


class TestConfirmDeleteKeyboard:
    """Test confirm delete keyboard."""

    def test_confirm_delete_keyboard(self):
        """Test confirm delete keyboard."""
        kb = confirm_delete_keyboard(456)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        confirm = [b for b in buttons if "vendor:confirm_delete:456" in b.callback_data]
        cancel = [b for b in buttons if "vendor:edit:456" in b.callback_data]
        assert len(confirm) == 1
        assert len(cancel) == 1


class TestPostageManagementKeyboard:
    """Test postage management keyboard."""

    def test_postage_management_keyboard_empty(self):
        """Test postage management keyboard with no postage types."""
        kb = postage_management_keyboard([])
        assert len(kb.inline_keyboard) == 2  # Add + back

    def test_postage_management_keyboard_with_types(self):
        """Test postage management keyboard with postage types."""
        postage_types = [
            MagicMock(id=1, name="Standard", price_fiat=5.0, currency="USD", is_active=True),
            MagicMock(id=2, name="Express", price_fiat=15.0, currency="GBP", is_active=False),
            MagicMock(id=3, name="Overnight", price_fiat=25.0, currency="EUR", is_active=True),
        ]
        kb = postage_management_keyboard(postage_types)
        assert len(kb.inline_keyboard) == 5  # 3 types + add + back
        assert "Active" in kb.inline_keyboard[0][0].text
        assert "Inactive" in kb.inline_keyboard[1][0].text


class TestPostageEditKeyboard:
    """Test postage edit keyboard."""

    def test_postage_edit_keyboard(self):
        """Test postage edit keyboard."""
        kb = postage_edit_keyboard(789)
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        edit_name = [b for b in buttons if "postage:edit_name:789" in b.callback_data]
        toggle = [b for b in buttons if "postage:toggle:789" in b.callback_data]
        delete = [b for b in buttons if "postage:delete:789" in b.callback_data]
        assert len(edit_name) == 1
        assert len(toggle) == 1
        assert len(delete) == 1


class TestPostageSelectionKeyboard:
    """Test postage selection keyboard."""

    def test_postage_selection_keyboard_empty(self):
        """Test postage selection with no active postage."""
        postage_types = [
            MagicMock(id=1, name="Standard", price_fiat=5.0, currency="USD", is_active=False, description=None),
        ]
        kb = postage_selection_keyboard(postage_types, product_id=1, quantity=2)
        # Should have "No Postage" + cancel
        assert len(kb.inline_keyboard) == 2

    def test_postage_selection_keyboard_with_active(self):
        """Test postage selection with active postage types."""
        postage_types = [
            MagicMock(id=1, name="Standard", price_fiat=5.0, currency="USD", is_active=True, description=None),
            MagicMock(id=2, name="Express", price_fiat=15.0, currency="GBP", is_active=True, description="Fast"),
        ]
        kb = postage_selection_keyboard(postage_types, product_id=3, quantity=2)
        # 2 active types + no postage + cancel
        assert len(kb.inline_keyboard) == 4
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        postage_btns = [b for b in buttons if "order:postage:3:2:" in b.callback_data]
        assert len(postage_btns) == 3  # 2 types + no postage option


class TestVendorOrdersKeyboard:
    """Test vendor orders keyboard."""

    def test_vendor_orders_keyboard_empty(self):
        """Test vendor orders keyboard with no orders."""
        kb = vendor_orders_keyboard([])
        assert len(kb.inline_keyboard) == 1  # Just back

    def test_vendor_orders_keyboard_with_orders(self):
        """Test vendor orders keyboard with orders."""
        orders = [
            MagicMock(id=1, state="NEW"),
            MagicMock(id=2, state="PAID"),
            MagicMock(id=3, state="SHIPPED"),
            MagicMock(id=4, state="COMPLETED"),
            MagicMock(id=5, state="CANCELLED"),
            MagicMock(id=6, state="UNKNOWN"),
        ]
        kb = vendor_orders_keyboard(orders)
        assert len(kb.inline_keyboard) == 7  # 6 orders + back


class TestVendorOrderDetailKeyboard:
    """Test vendor order detail keyboard."""

    def test_vendor_order_detail_paid(self):
        """Test vendor order detail for paid order."""
        kb = vendor_order_detail_keyboard(123, state="PAID")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        ship_btns = [b for b in buttons if "vorder:ship:123" in b.callback_data]
        assert len(ship_btns) == 1

    def test_vendor_order_detail_shipped(self):
        """Test vendor order detail for shipped order."""
        kb = vendor_order_detail_keyboard(123, state="SHIPPED")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        complete_btns = [b for b in buttons if "vorder:complete:123" in b.callback_data]
        assert len(complete_btns) == 1

    def test_vendor_order_detail_other(self):
        """Test vendor order detail for other states."""
        kb = vendor_order_detail_keyboard(123, state="COMPLETED")
        # Should just have back button
        assert len(kb.inline_keyboard) == 1


class TestSuperAdminKeyboard:
    """Test super admin keyboard."""

    def test_super_admin_keyboard(self):
        """Test super admin keyboard."""
        kb = super_admin_keyboard()
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        stats = [b for b in buttons if "sadmin:stats" in b.callback_data]
        commission = [b for b in buttons if "sadmin:commission" in b.callback_data]
        assert len(stats) == 1
        assert len(commission) == 1


class TestCommissionRateKeyboard:
    """Test commission rate keyboard."""

    def test_commission_rate_keyboard_default(self):
        """Test commission rate keyboard."""
        kb = commission_rate_keyboard("0.05")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        selected = [b for b in buttons if ">5%" in b.text]
        assert len(selected) == 1

    def test_commission_rate_keyboard_other(self):
        """Test commission rate keyboard with different rate."""
        kb = commission_rate_keyboard("0.10")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        selected = [b for b in buttons if ">10%" in b.text]
        assert len(selected) == 1

    def test_commission_rate_keyboard_has_custom(self):
        """Test commission rate keyboard has custom option."""
        kb = commission_rate_keyboard("0.05")
        buttons = [btn for row in kb.inline_keyboard for btn in row]
        custom = [b for b in buttons if "sadmin:custom_commission" in b.callback_data]
        assert len(custom) == 1


class TestConstants:
    """Test keyboard constants."""

    def test_supported_coins(self):
        """Test supported coins list."""
        assert len(SUPPORTED_COINS) == 3  # XMR, BTC, ETH
        # Check format: (code, name, emoji)
        codes = [coin[0] for coin in SUPPORTED_COINS]
        assert "XMR" in codes
        assert "BTC" in codes
        assert "ETH" in codes

    def test_supported_currencies(self):
        """Test supported currencies list."""
        assert len(SUPPORTED_CURRENCIES) > 0
        usd = [c for c in SUPPORTED_CURRENCIES if c[0] == "USD"]
        assert len(usd) == 1
