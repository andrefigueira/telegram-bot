"""Admin command handlers."""

from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..services.vendors import VendorService
from ..models import Product, Vendor
from ..config import get_settings
from ..error_handler import handle_errors, handle_callback_errors
from ..keyboards import (
    admin_menu_keyboard,
    vendor_products_keyboard,
    product_edit_keyboard,
    confirm_delete_keyboard,
    main_menu_keyboard,
    vendor_orders_keyboard,
    vendor_order_detail_keyboard,
    super_admin_keyboard,
    commission_rate_keyboard,
    setup_keyboard,
    SUPPORTED_CURRENCIES,
)
from ..services.currency import (
    fiat_to_xmr_accurate,
    format_price_simple,
    get_currency_symbol,
)
from ..services.orders import OrderService
from ..services.payout import PayoutService
import pyotp

logger = logging.getLogger(__name__)


def _is_admin(user_id: int, token: str | None = None) -> bool:
    settings = get_settings()
    allowed = user_id in settings.admin_ids_list or user_id in settings.super_admin_ids_list
    if not allowed:
        return False
    if settings.totp_secret:
        if token is None:
            return False
        return pyotp.TOTP(settings.totp_secret).verify(token)
    return True


def _is_super_admin(user_id: int, token: str | None = None) -> bool:
    settings = get_settings()
    if user_id not in settings.super_admin_ids_list:
        return False
    if settings.totp_secret:
        if token is None:
            return False
        return pyotp.TOTP(settings.totp_secret).verify(token)
    return True


def _is_vendor_or_admin(user_id: int, vendors: VendorService) -> bool:
    """Check if user is a vendor or admin (for product management)."""
    if _is_admin(user_id):
        return True
    vendor = vendors.get_by_telegram_id(user_id)
    return vendor is not None


@handle_errors
async def admin_menu(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show admin menu."""
    user_id = update.effective_user.id
    if not _is_admin(user_id):
        await update.message.reply_text("You don't have admin access.")
        return

    await update.message.reply_text(
        "*Admin Panel*\n\n"
        "Manage your shop from here:",
        parse_mode='Markdown',
        reply_markup=admin_menu_keyboard()
    )


async def add(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    catalog: CatalogService,
    vendors: VendorService,
) -> None:
    """Add a new product from command arguments."""
    user_id = update.effective_user.id
    args = context.args
    token = args[-1] if get_settings().totp_secret else None
    if not _is_admin(user_id, token):
        return
    if get_settings().totp_secret:
        args = args[:-1]
    if len(args) < 3:
        await update.message.reply_text("Usage: /add <name> <price> <inventory> [totp]")
        return
    name, price, inventory = args[0], float(args[1]), int(args[2])
    vendor = vendors.get_by_telegram_id(user_id)
    if not vendor:
        await update.message.reply_text("Vendor not registered")
        return
    product = Product(
        name=name,
        description="",
        price_xmr=price,
        inventory=inventory,
        vendor_id=vendor.id,
    )
    catalog.add_product(product)
    await update.message.reply_text(f"Added {product.name}")


async def add_vendor(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    vendors: VendorService,
) -> None:
    """Register a new vendor (super admin only)."""
    args = context.args
    token = args[-1] if get_settings().totp_secret else None
    if not _is_super_admin(update.effective_user.id, token):
        return
    if get_settings().totp_secret:
        args = args[:-1]
    if len(args) < 2:
        await update.message.reply_text("Usage: /addvendor <telegram_id> <name> [totp]")
        return
    tg_id, name = int(args[0]), args[1]
    vendor = Vendor(telegram_id=tg_id, name=name)
    vendors.add_vendor(vendor)
    await update.message.reply_text(f"Vendor {vendor.name} added with id {vendor.id}")


async def list_vendors(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    vendors: VendorService,
) -> None:
    """List all vendors (super admin only)."""
    args = context.args
    token = args[-1] if get_settings().totp_secret else None
    if not _is_super_admin(update.effective_user.id, token):
        return
    if get_settings().totp_secret:
        args = args[:-1]
    items = vendors.list_vendors()
    if not items:
        await update.message.reply_text("No vendors")
        return
    lines = [f"{v.id}: {v.name} rate {v.commission_rate}" for v in items]
    await update.message.reply_text("\n".join(lines))


async def set_commission(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    vendors: VendorService,
) -> None:
    """Set vendor commission (super admin only)."""
    args = context.args
    token = args[-1] if get_settings().totp_secret else None
    if not _is_super_admin(update.effective_user.id, token):
        return
    if get_settings().totp_secret:
        args = args[:-1]
    if len(args) < 2:
        await update.message.reply_text("Usage: /commission <vendor_id> <rate> [totp]")
        return
    vendor_id, rate = int(args[0]), float(args[1])
    vendor = vendors.set_commission(vendor_id, rate)
    await update.message.reply_text(
        f"Vendor {vendor.name} commission set to {vendor.commission_rate}"
    )


# Callback handlers for admin/vendor actions

@handle_callback_errors
async def handle_admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    catalog: CatalogService = None,
    vendors: VendorService = None,
) -> None:
    """Handle admin menu callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    # Product management - allow vendors or admins
    if action == "products" and catalog and vendors:
        if not _is_vendor_or_admin(user_id, vendors):
            await query.edit_message_text(
                "You need to be a vendor to manage products.\n\n"
                "Use /setup and tap 'Become a Vendor' to get started!",
                reply_markup=main_menu_keyboard()
            )
            return

        vendor = vendors.get_by_telegram_id(user_id)
        if not vendor:
            await query.edit_message_text(
                "You need to be registered as a vendor first.\n\n"
                "Use /setup and tap 'Become a Vendor' to get started!",
                reply_markup=main_menu_keyboard()
            )
            return

        products = catalog.list_products_by_vendor(vendor.id)
        if not products:
            await query.edit_message_text(
                "*My Products*\n\n"
                "You haven't added any products yet.\n"
                "Tap below to add your first product!",
                parse_mode='Markdown',
                reply_markup=vendor_products_keyboard([])
            )
        else:
            await query.edit_message_text(
                "*My Products*\n\n"
                "Tap a product to edit it:",
                parse_mode='Markdown',
                reply_markup=vendor_products_keyboard(products)
            )
        return

    # Admin-only actions below
    if not _is_admin(user_id):
        await query.edit_message_text("You don't have admin access.")
        return

    if action == "add_product":
        context.user_data['awaiting_input'] = 'product_name'
        context.user_data['new_product'] = {}
        await query.edit_message_text(
            "*Add New Product*\n\n"
            "Step 1/4: Enter the product name:",
            parse_mode='Markdown'
        )

    elif action == "orders" and vendors:
        vendor = vendors.get_by_telegram_id(user_id)
        if vendor:
            # Get vendor's orders from context
            orders = context.bot_data.get('orders')
            if orders:
                vendor_orders = orders.list_orders_by_vendor(vendor.id)
                if vendor_orders:
                    await query.edit_message_text(
                        "*My Orders*\n\n"
                        "Tap an order to view details and manage:",
                        parse_mode='Markdown',
                        reply_markup=vendor_orders_keyboard(vendor_orders)
                    )
                else:
                    await query.edit_message_text(
                        "*My Orders*\n\n"
                        "No orders yet.",
                        parse_mode='Markdown',
                        reply_markup=admin_menu_keyboard()
                    )
            else:
                await query.edit_message_text(
                    "*Orders*\n\n"
                    "Order service unavailable.",
                    parse_mode='Markdown',
                    reply_markup=admin_menu_keyboard()
                )
        else:
            await query.edit_message_text(
                "You need to be a vendor to view orders.",
                reply_markup=main_menu_keyboard()
            )

    elif action == "settings":
        await query.edit_message_text(
            "*Shop Settings*\n\n"
            "Use /setup to configure your shop settings.",
            parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )


@handle_callback_errors
async def handle_vendor_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    catalog: CatalogService = None,
    vendors: VendorService = None,
) -> None:
    """Handle vendor product management callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not vendors or not _is_vendor_or_admin(user_id, vendors):
        await query.edit_message_text(
            "You need to be a vendor to manage products.\n\n"
            "Use /setup and tap 'Become a Vendor' to get started!",
            reply_markup=main_menu_keyboard()
        )
        return

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    if action == "add":
        context.user_data['awaiting_input'] = 'product_name'
        context.user_data['new_product'] = {}
        await query.edit_message_text(
            "*Add New Product*\n\n"
            "Step 1/4: Enter the product name:",
            parse_mode='Markdown'
        )

    elif action == "edit" and len(parts) >= 3 and catalog:
        product_id = int(parts[2])
        product = catalog.get_product(product_id)
        if product:
            await query.edit_message_text(
                f"*{product.name}*\n\n"
                f"Price: `{product.price_xmr}` XMR\n"
                f"Stock: {product.inventory}\n"
                f"Description: {product.description or 'None'}\n\n"
                f"What would you like to edit?",
                parse_mode='Markdown',
                reply_markup=product_edit_keyboard(product_id)
            )

    elif action == "edit_name" and len(parts) >= 3:
        product_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_name'
        context.user_data['editing_product'] = product_id
        await query.edit_message_text(
            "*Edit Product Name*\n\n"
            "Enter the new name:",
            parse_mode='Markdown'
        )

    elif action == "edit_price" and len(parts) >= 3:
        product_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_price'
        context.user_data['editing_product'] = product_id
        await query.edit_message_text(
            "*Edit Product Price*\n\n"
            "Enter the new price in XMR (e.g., 0.05):",
            parse_mode='Markdown'
        )

    elif action == "edit_stock" and len(parts) >= 3:
        product_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_stock'
        context.user_data['editing_product'] = product_id
        await query.edit_message_text(
            "*Edit Stock Quantity*\n\n"
            "Enter the new stock quantity:",
            parse_mode='Markdown'
        )

    elif action == "edit_desc" and len(parts) >= 3:
        product_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_desc'
        context.user_data['editing_product'] = product_id
        await query.edit_message_text(
            "*Edit Description*\n\n"
            "Enter the new description:",
            parse_mode='Markdown'
        )

    elif action == "delete" and len(parts) >= 3 and catalog:
        product_id = int(parts[2])
        product = catalog.get_product(product_id)
        if product:
            await query.edit_message_text(
                f"*Delete Product*\n\n"
                f"Are you sure you want to delete *{product.name}*?\n\n"
                f"This action cannot be undone.",
                parse_mode='Markdown',
                reply_markup=confirm_delete_keyboard(product_id)
            )

    elif action == "confirm_delete" and len(parts) >= 3 and catalog and vendors:
        product_id = int(parts[2])
        catalog.delete_product(product_id)
        vendor = vendors.get_by_telegram_id(user_id)
        products = catalog.list_products_by_vendor(vendor.id) if vendor else []
        await query.edit_message_text(
            "*Product Deleted*\n\n"
            "The product has been removed.",
            parse_mode='Markdown',
            reply_markup=vendor_products_keyboard(products)
        )


@handle_errors
async def handle_admin_text_input(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    catalog: CatalogService = None,
    vendors: VendorService = None,
) -> None:
    """Handle text input for admin/vendor flows."""
    awaiting = context.user_data.get('awaiting_input')

    if not awaiting:
        return

    # Only process admin-related inputs
    if awaiting not in ['product_name', 'product_price', 'product_stock', 'product_desc',
                        'edit_name', 'edit_price', 'edit_stock', 'edit_desc',
                        'platform_wallet', 'custom_commission', 'shipping_note']:
        return

    user_id = update.effective_user.id
    if not vendors or not _is_vendor_or_admin(user_id, vendors):
        return

    text = update.message.text

    # New product creation flow
    # Get vendor's currency setting from database
    vendor = vendors.get_by_telegram_id(user_id)
    vendor_currency = vendor.pricing_currency if vendor else 'USD'
    currency_symbol = get_currency_symbol(vendor_currency)

    if awaiting == 'product_name':
        context.user_data['new_product']['name'] = text
        context.user_data['new_product']['currency'] = vendor_currency
        context.user_data['awaiting_input'] = 'product_price'

        if vendor_currency == 'XMR':
            price_prompt = "Step 2/4: Enter the price in XMR (e.g., 0.05):"
        else:
            price_prompt = f"Step 2/4: Enter the price in {vendor_currency} (e.g., 25.00):"

        await update.message.reply_text(
            "*Add New Product*\n\n"
            f"Name: {text}\n\n"
            f"{price_prompt}",
            parse_mode='Markdown'
        )

    elif awaiting == 'product_price':
        try:
            price = float(text)
            product_currency = context.user_data['new_product'].get('currency', 'USD')
            context.user_data['new_product']['price'] = price
            context.user_data['awaiting_input'] = 'product_stock'

            price_display = format_price_simple(price, product_currency)
            await update.message.reply_text(
                "*Add New Product*\n\n"
                f"Name: {context.user_data['new_product']['name']}\n"
                f"Price: {price_display}\n\n"
                "Step 3/4: Enter the stock quantity:",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text(
                f"Invalid price. Please enter a number (e.g., 25.00):"
            )

    elif awaiting == 'product_stock':
        try:
            stock = int(text)
            product_currency = context.user_data['new_product'].get('currency', 'USD')
            context.user_data['new_product']['stock'] = stock
            context.user_data['awaiting_input'] = 'product_desc'

            price_display = format_price_simple(
                context.user_data['new_product']['price'],
                product_currency
            )
            await update.message.reply_text(
                "*Add New Product*\n\n"
                f"Name: {context.user_data['new_product']['name']}\n"
                f"Price: {price_display}\n"
                f"Stock: {stock}\n\n"
                "Step 4/4: Enter a description (or send 'skip' for none):",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text(
                "Invalid quantity. Please enter a number:"
            )

    elif awaiting == 'product_desc' and catalog and vendors:
        vendor = vendors.get_by_telegram_id(user_id)
        if not vendor:
            await update.message.reply_text(
                "Error: You're not registered as a vendor.",
                reply_markup=main_menu_keyboard()
            )
            context.user_data['awaiting_input'] = None
            return

        new_prod = context.user_data.get('new_product', {})
        desc = "" if text.lower() == 'skip' else text
        product_currency = new_prod.get('currency', 'USD')
        price_fiat = new_prod.get('price', 0)

        # Convert to XMR for storage (use accurate conversion)
        try:
            price_xmr = await fiat_to_xmr_accurate(price_fiat, product_currency)
        except ValueError as e:
            await update.message.reply_text(
                f"Error converting price: {e}\nPlease try again.",
                reply_markup=main_menu_keyboard()
            )
            context.user_data['awaiting_input'] = None
            return

        product = Product(
            name=new_prod.get('name', 'Unnamed'),
            description=desc,
            price_xmr=price_xmr,
            price_fiat=price_fiat,
            currency=product_currency,
            inventory=new_prod.get('stock', 0),
            vendor_id=vendor.id,
        )
        catalog.add_product(product)

        context.user_data['awaiting_input'] = None
        context.user_data['new_product'] = None

        products = catalog.list_products_by_vendor(vendor.id)
        price_display = format_price_simple(price_fiat, product_currency)
        await update.message.reply_text(
            f"*Product Added!*\n\n"
            f"*{product.name}*\n"
            f"Price: {price_display}\n"
            f"(~{price_xmr:.6f} XMR at current rate)\n"
            f"Stock: {product.inventory}",
            parse_mode='Markdown',
            reply_markup=vendor_products_keyboard(products)
        )

    # Edit product flows
    elif awaiting == 'edit_name' and catalog:
        product_id = context.user_data.get('editing_product')
        if product_id:
            catalog.update_product(product_id, name=text)
            context.user_data['awaiting_input'] = None
            context.user_data['editing_product'] = None
            product = catalog.get_product(product_id)
            await update.message.reply_text(
                f"*Name Updated!*\n\n"
                f"New name: {text}",
                parse_mode='Markdown',
                reply_markup=product_edit_keyboard(product_id)
            )

    elif awaiting == 'edit_price' and catalog:
        product_id = context.user_data.get('editing_product')
        if product_id:
            try:
                price = float(text)
                catalog.update_product(product_id, price_xmr=price)
                context.user_data['awaiting_input'] = None
                context.user_data['editing_product'] = None
                await update.message.reply_text(
                    f"*Price Updated!*\n\n"
                    f"New price: {price} XMR",
                    parse_mode='Markdown',
                    reply_markup=product_edit_keyboard(product_id)
                )
            except ValueError:
                await update.message.reply_text(
                    "Invalid price. Please enter a number:"
                )

    elif awaiting == 'edit_stock' and catalog:
        product_id = context.user_data.get('editing_product')
        if product_id:
            try:
                stock = int(text)
                catalog.update_product(product_id, inventory=stock)
                context.user_data['awaiting_input'] = None
                context.user_data['editing_product'] = None
                await update.message.reply_text(
                    f"*Stock Updated!*\n\n"
                    f"New quantity: {stock}",
                    parse_mode='Markdown',
                    reply_markup=product_edit_keyboard(product_id)
                )
            except ValueError:
                await update.message.reply_text(
                    "Invalid quantity. Please enter a number:"
                )

    elif awaiting == 'edit_desc' and catalog:
        product_id = context.user_data.get('editing_product')
        if product_id:
            catalog.update_product(product_id, description=text)
            context.user_data['awaiting_input'] = None
            context.user_data['editing_product'] = None
            await update.message.reply_text(
                f"*Description Updated!*",
                parse_mode='Markdown',
                reply_markup=product_edit_keyboard(product_id)
            )

    # Super admin text inputs
    elif awaiting == 'platform_wallet':
        if _is_super_admin(user_id):
            payout = context.bot_data.get('payout_service')
            currency = context.user_data.get('platform_wallet_currency', 'XMR')

            # Validate address based on currency
            valid = False
            error_msg = f"Invalid {currency} address."

            if currency == "XMR":
                valid = len(text) >= 95 and (text.startswith('4') or text.startswith('8'))
                error_msg = "Invalid Monero address. Please send a valid XMR address (starts with 4 or 8, 95+ chars)."
            elif currency == "BTC":
                from ..services.bitcoin_payment import BitcoinPaymentService
                valid = BitcoinPaymentService.validate_address(text)
                error_msg = "Invalid Bitcoin address. Please send a valid BTC address (starts with 1, 3, or bc1)."
            elif currency == "ETH":
                from ..services.ethereum_payment import EthereumPaymentService
                valid = EthereumPaymentService.validate_address(text)
                error_msg = "Invalid Ethereum address. Please send a valid ETH address (starts with 0x, 42 chars)."

            if payout and valid:
                payout.set_platform_wallet(text, currency)
                context.user_data['awaiting_input'] = None
                context.user_data['platform_wallet_currency'] = None
                await update.message.reply_text(
                    f"*Platform {currency} Wallet Set!*\n\n`{text[:30]}...`",
                    parse_mode='Markdown',
                    reply_markup=super_admin_keyboard()
                )
            else:
                await update.message.reply_text(error_msg)

    elif awaiting == 'custom_commission':
        if _is_super_admin(user_id):
            try:
                rate = float(text)
                if 0 < rate < 1:
                    payout = context.bot_data.get('payout_service')
                    if payout:
                        from decimal import Decimal
                        payout.set_platform_commission_rate(Decimal(str(rate)))
                        context.user_data['awaiting_input'] = None
                        await update.message.reply_text(
                            f"*Commission Rate Set!*\n\n{rate * 100:.1f}%",
                            parse_mode='Markdown',
                            reply_markup=super_admin_keyboard()
                        )
                else:
                    await update.message.reply_text(
                        "Invalid rate. Enter a decimal between 0 and 1 (e.g., 0.05 for 5%)."
                    )
            except ValueError:
                await update.message.reply_text(
                    "Invalid rate. Enter a decimal (e.g., 0.05 for 5%)."
                )

    elif awaiting == 'shipping_note':
        order_id = context.user_data.get('shipping_order')
        orders = context.bot_data.get('orders')
        if order_id and orders:
            try:
                note = text if text.lower() != 'skip' else None
                order = orders.mark_shipped(order_id, shipping_note=note)
                context.user_data['awaiting_input'] = None
                context.user_data['shipping_order'] = None
                await update.message.reply_text(
                    f"*Order #{order_id} Shipped!*\n\n"
                    f"Status: {order.state}",
                    parse_mode='Markdown',
                    reply_markup=vendor_order_detail_keyboard(order_id, order.state)
                )
            except Exception as e:
                await update.message.reply_text(
                    f"Error: {str(e)}",
                    reply_markup=main_menu_keyboard()
                )


# Super admin command
@handle_errors
async def super_admin_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show super admin panel."""
    user_id = update.effective_user.id
    if not _is_super_admin(user_id):
        await update.message.reply_text("Access denied.")
        return

    await update.message.reply_text(
        "*Super Admin Panel*\n\n"
        "Platform management controls:",
        parse_mode='Markdown',
        reply_markup=super_admin_keyboard()
    )


# Super admin callback handler
@handle_callback_errors
async def handle_super_admin_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    payout: PayoutService = None,
) -> None:
    """Handle super admin callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not _is_super_admin(user_id):
        await query.edit_message_text("Access denied.")
        return

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    if action == "main":
        await query.edit_message_text(
            "*Super Admin Panel*\n\n"
            "Platform management controls:",
            parse_mode='Markdown',
            reply_markup=super_admin_keyboard()
        )

    elif action == "stats" and payout:
        stats = payout.get_platform_stats()
        earnings = payout.get_platform_earnings()

        # Build multi-currency earnings display
        earnings_lines = []
        for currency in ["XMR", "BTC", "ETH"]:
            amount = earnings.get(currency, 0)
            if amount > 0:
                if currency == "BTC":
                    earnings_lines.append(f"₿ {amount:.8f} BTC")
                elif currency == "ETH":
                    earnings_lines.append(f"Ξ {amount:.6f} ETH")
                else:
                    earnings_lines.append(f"🔒 {amount:.8f} XMR")
        earnings_display = "\n".join(earnings_lines) if earnings_lines else "No earnings yet"

        # Build multi-currency wallets display
        wallet_lines = []
        for currency in ["XMR", "BTC", "ETH"]:
            wallet_addr = payout.get_platform_wallet(currency)
            if wallet_addr:
                short_addr = wallet_addr[:15] + "..." if len(wallet_addr) > 15 else wallet_addr
                wallet_lines.append(f"*{currency}:* `{short_addr}`")
        wallets_display = "\n".join(wallet_lines) if wallet_lines else "No wallets set"

        await query.edit_message_text(
            f"*Platform Statistics*\n\n"
            f"*Orders:* {stats['paid_orders']}/{stats['total_orders']} paid\n\n"
            f"*Commission Earned:*\n{earnings_display}\n\n"
            f"*Pending Payouts:* {stats['pending_payouts']} ({stats['pending_payout_amount_xmr']:.6f} XMR)\n"
            f"*Completed Payouts:* {stats['completed_payouts']} ({stats['completed_payout_amount_xmr']:.6f} XMR)\n\n"
            f"*Commission Rate:* {float(stats['commission_rate']) * 100:.1f}%\n\n"
            f"*Platform Wallets:*\n{wallets_display}",
            parse_mode='Markdown',
            reply_markup=super_admin_keyboard()
        )

    elif action == "commission" and payout:
        current_rate = str(payout.get_platform_commission_rate())
        await query.edit_message_text(
            "*Set Commission Rate*\n\n"
            "Select a commission rate or enter a custom value.",
            parse_mode='Markdown',
            reply_markup=commission_rate_keyboard(current_rate)
        )

    elif action == "set_commission" and len(parts) >= 3 and payout:
        from decimal import Decimal
        rate = Decimal(parts[2])
        payout.set_platform_commission_rate(rate)
        await query.edit_message_text(
            f"*Commission Rate Updated!*\n\n"
            f"New rate: {float(rate) * 100:.1f}%",
            parse_mode='Markdown',
            reply_markup=super_admin_keyboard()
        )

    elif action == "custom_commission":
        context.user_data['awaiting_input'] = 'custom_commission'
        await query.edit_message_text(
            "*Custom Commission Rate*\n\n"
            "Enter the rate as a decimal (e.g., 0.05 for 5%):",
            parse_mode='Markdown'
        )

    elif action == "wallet":
        from ..keyboards import SUPPORTED_COINS
        keyboard = []
        for coin_code, coin_name, emoji in SUPPORTED_COINS:
            keyboard.append([{
                "text": f"{emoji} {coin_name} ({coin_code})",
                "callback_data": f"sadmin:wallet_currency:{coin_code}"
            }])
        keyboard.append([{"text": "Back", "callback_data": "sadmin:main"}])

        from telegram import InlineKeyboardButton, InlineKeyboardMarkup
        markup = InlineKeyboardMarkup([[InlineKeyboardButton(btn["text"], callback_data=btn["callback_data"])] for row in keyboard for btn in row])

        await query.edit_message_text(
            "*Set Platform Wallet*\n\n"
            "Select the cryptocurrency:",
            parse_mode='Markdown',
            reply_markup=markup
        )

    elif action == "wallet_currency" and len(parts) >= 3:
        currency = parts[2].upper()
        context.user_data['awaiting_input'] = 'platform_wallet'
        context.user_data['platform_wallet_currency'] = currency

        currency_names = {"XMR": "Monero", "BTC": "Bitcoin", "ETH": "Ethereum"}
        await query.edit_message_text(
            f"*Set Platform {currency} Wallet*\n\n"
            f"Enter your {currency_names.get(currency, currency)} address:",
            parse_mode='Markdown'
        )

    elif action == "payouts" and payout:
        results = await payout.process_payouts()
        await query.edit_message_text(
            f"*Payouts Processed*\n\n"
            f"*Total:* {results['processed']}\n"
            f"*Sent:* {results['sent']}\n"
            f"*Failed:* {results['failed']}\n"
            f"*Skipped:* {results['skipped']}",
            parse_mode='Markdown',
            reply_markup=super_admin_keyboard()
        )

    elif action == "pending" and payout:
        pending = payout.get_pending_payouts()
        if not pending:
            await query.edit_message_text(
                "*Pending Payouts*\n\nNo pending payouts.",
                parse_mode='Markdown',
                reply_markup=super_admin_keyboard()
            )
        else:
            lines = []
            for p in pending[:10]:
                lines.append(f"Order #{p.order_id}: {p.amount_xmr:.6f} XMR")
            await query.edit_message_text(
                f"*Pending Payouts*\n\n" + "\n".join(lines),
                parse_mode='Markdown',
                reply_markup=super_admin_keyboard()
            )

    elif action == "vendors":
        await query.edit_message_text(
            "*Vendor Management*\n\n"
            "Use /vendors to list all vendors.\n"
            "Use /commission <vendor_id> <rate> to set vendor rates.",
            parse_mode='Markdown',
            reply_markup=super_admin_keyboard()
        )


# Vendor order management callback handler
@handle_callback_errors
async def handle_vendor_order_callback(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    orders: OrderService = None,
    vendors: VendorService = None,
) -> None:
    """Handle vendor order management callbacks."""
    query = update.callback_query
    await query.answer()

    user_id = update.effective_user.id
    if not vendors:
        return

    vendor = vendors.get_by_telegram_id(user_id)
    if not vendor:
        await query.edit_message_text(
            "You need to be a vendor to manage orders.",
            reply_markup=main_menu_keyboard()
        )
        return

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    if action == "view" and len(parts) >= 3 and orders:
        order_id = int(parts[2])
        order = orders.get_order(order_id)
        if order and order.vendor_id == vendor.id:
            delivery_addr = orders.get_address(order)
            addr_display = delivery_addr[:40] + "..." if len(delivery_addr) > 40 else delivery_addr

            shipped_info = ""
            if order.shipped_at:
                shipped_info = f"\n*Shipped:* {order.shipped_at.strftime('%Y-%m-%d %H:%M')}"
            if order.shipping_note:
                shipped_info += f"\n*Note:* {order.shipping_note}"

            await query.edit_message_text(
                f"*Order #{order_id}*\n\n"
                f"*Status:* {order.state}\n"
                f"*Quantity:* {order.quantity}\n"
                f"*Address:* {addr_display}{shipped_info}",
                parse_mode='Markdown',
                reply_markup=vendor_order_detail_keyboard(order_id, order.state)
            )
        else:
            await query.answer("Order not found", show_alert=True)

    elif action == "ship" and len(parts) >= 3:
        order_id = int(parts[2])
        context.user_data['awaiting_input'] = 'shipping_note'
        context.user_data['shipping_order'] = order_id
        await query.edit_message_text(
            f"*Ship Order #{order_id}*\n\n"
            f"Enter a shipping note (or 'skip' for none):\n"
            f"(e.g., tracking number, carrier, estimated delivery)",
            parse_mode='Markdown'
        )

    elif action == "complete" and len(parts) >= 3 and orders:
        order_id = int(parts[2])
        try:
            order = orders.mark_completed(order_id)
            await query.edit_message_text(
                f"*Order #{order_id} Completed!*\n\n"
                f"The order has been marked as completed.",
                parse_mode='Markdown',
                reply_markup=vendor_order_detail_keyboard(order_id, order.state)
            )
        except Exception as e:
            await query.edit_message_text(
                f"Error: {str(e)}",
                reply_markup=main_menu_keyboard()
            )
