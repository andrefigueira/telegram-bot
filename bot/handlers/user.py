"""User command handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..services.orders import OrderService
from ..error_handler import handle_errors, handle_callback_errors
from ..keyboards import (
    main_menu_keyboard,
    help_keyboard,
    setup_keyboard,
    products_keyboard,
    product_detail_keyboard,
    quantity_keyboard,
    payment_coin_keyboard,
    order_confirmation_keyboard,
    payment_methods_keyboard,
    vendor_products_keyboard,
    currency_keyboard,
    postage_management_keyboard,
    postage_edit_keyboard,
    postage_selection_keyboard,
    SUPPORTED_COINS,
    SUPPORTED_CURRENCIES,
)
from ..services.vendors import VendorService
from ..services.postage import PostageService
from ..models import Vendor, Database
from decimal import Decimal


HELP_TEXT = """
*Available Commands*

*Shopping*
/start - Main menu
/products - Browse products
/order <id> <qty> <address> - Quick order
/orders - View your orders
/status <order_id> - Check order status

*Account Setup*
/setup - Configure your shop settings
/help - Show this help message

*Payment Methods*
We accept the following cryptocurrencies:
- Monero (XMR)
- Bitcoin (BTC)
- Ethereum (ETH)
- Solana (SOL)
- Litecoin (LTC)
- Tether (USDT)
- USD Coin (USDC)

Non-XMR payments are automatically converted.
"""

SETUP_INTRO = """
*Shop Setup*

Configure your account settings below.

Use the buttons to:
- Set which payment methods you accept
- Configure your shop name
- Set your wallet address for payouts
- View your current settings
"""


@handle_errors
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user with main menu."""
    welcome_msg = (
        "*Welcome to the Shop!*\n\n"
        "Browse products, place orders, and pay with your preferred cryptocurrency.\n\n"
        "What would you like to do?"
    )
    await update.message.reply_text(
        welcome_msg,
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


@handle_errors
async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show help message with all commands."""
    await update.message.reply_text(
        HELP_TEXT,
        parse_mode='Markdown',
        reply_markup=help_keyboard()
    )


@handle_errors
async def setup_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show setup menu for configuring account."""
    await update.message.reply_text(
        SETUP_INTRO,
        parse_mode='Markdown',
        reply_markup=setup_keyboard()
    )


@handle_errors
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService) -> None:
    """List available products with buttons."""
    query = context.args[0] if context.args else ""
    products = catalog.search(query) if query else catalog.list_products()

    if not products:
        await update.message.reply_text(
            "No products found.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Store products in context for pagination
    context.user_data['products'] = products

    header = "*Available Products*\n\nSelect a product to view details:"
    await update.message.reply_text(
        header,
        parse_mode='Markdown',
        reply_markup=products_keyboard(products, page=0)
    )


@handle_errors
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService) -> None:
    """Create an order (text command fallback)."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "*Quick Order*\n\n"
            "Usage: `/order <product_id> <quantity> <delivery_address>`\n\n"
            "Example: `/order 1 2 My delivery address here`\n\n"
            "Or use /products to browse and order with buttons.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
        return

    try:
        prod_id = int(args[0])
        qty = int(args[1])
    except ValueError:
        await update.message.reply_text(
            "Invalid product ID or quantity. Please use numbers.",
            reply_markup=main_menu_keyboard()
        )
        return

    # Join all remaining args as address
    addr = " ".join(args[2:])

    # Create order
    order_data = orders.create_order(prod_id, qty, addr)

    # Send payment instructions with buttons
    payment_msg = (
        f"*Order #{order_data['order_id']} Created!*\n\n"
        f"*Amount:* `{order_data['total_xmr']}` XMR\n"
        f"*Send to:* `{order_data['payment_address']}`\n"
        f"*Payment ID:* `{order_data['payment_id']}`\n\n"
        f"Include the Payment ID in your transaction.\n"
        f"Your order will be processed once payment is confirmed."
    )

    await update.message.reply_text(
        payment_msg,
        parse_mode='Markdown',
        reply_markup=order_confirmation_keyboard(order_data['order_id'])
    )


@handle_errors
async def orders_list(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService) -> None:
    """List user's orders."""
    # For now, show a message - in full implementation would fetch user's orders
    await update.message.reply_text(
        "*Your Orders*\n\n"
        "Use `/status <order_id>` to check a specific order.\n\n"
        "Order history coming soon!",
        parse_mode='Markdown',
        reply_markup=main_menu_keyboard()
    )


@handle_errors
async def order_status(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService) -> None:
    """Check order status."""
    args = context.args
    if not args:
        await update.message.reply_text(
            "Usage: `/status <order_id>`",
            parse_mode='Markdown'
        )
        return

    try:
        order_id = int(args[0])
    except ValueError:
        await update.message.reply_text("Invalid order ID.")
        return

    # This would fetch the order status
    await update.message.reply_text(
        f"*Order #{order_id}*\n\n"
        f"Checking status...\n\n"
        f"Use the buttons below to track your order.",
        parse_mode='Markdown',
        reply_markup=order_confirmation_keyboard(order_id)
    )


# Callback query handlers for button interactions

@handle_callback_errors
async def handle_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService = None) -> None:
    """Handle main menu button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    action = data.split(":")[1] if ":" in data else data

    if action == "main":
        await query.edit_message_text(
            "*Main Menu*\n\nWhat would you like to do?",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    elif action == "products":
        if catalog:
            products = catalog.list_products()
            context.user_data['products'] = products
            if products:
                await query.edit_message_text(
                    "*Available Products*\n\nSelect a product to view details:",
                    parse_mode='Markdown',
                    reply_markup=products_keyboard(products, page=0)
                )
            else:
                await query.edit_message_text(
                    "No products available.",
                    reply_markup=main_menu_keyboard()
                )
        else:
            await query.edit_message_text(
                "Products loading...",
                reply_markup=main_menu_keyboard()
            )
    elif action == "orders":
        await query.edit_message_text(
            "*Your Orders*\n\n"
            "Use `/status <order_id>` to check a specific order.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )
    elif action == "setup":
        await query.edit_message_text(
            SETUP_INTRO,
            parse_mode='Markdown',
            reply_markup=setup_keyboard()
        )
    elif action == "help":
        await query.edit_message_text(
            HELP_TEXT,
            parse_mode='Markdown',
            reply_markup=help_keyboard()
        )
    elif action == "admin":
        # Show vendor's product management
        user_id = update.effective_user.id
        from ..keyboards import vendor_products_keyboard
        # This requires vendors and catalog from context - redirect to setup for now
        await query.edit_message_text(
            "*Vendor Panel*\n\n"
            "Use /setup to manage your products and settings.",
            parse_mode='Markdown',
            reply_markup=main_menu_keyboard()
        )


@handle_callback_errors
async def handle_setup_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, vendors: VendorService = None, postage: PostageService = None) -> None:
    """Handle setup menu button callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    action = data.split(":")[1] if ":" in data else data

    user_id = update.effective_user.id
    is_vendor = False
    vendor = None
    if vendors:
        vendor = vendors.get_by_telegram_id(user_id)
        is_vendor = vendor is not None

    if action == "main":
        await query.edit_message_text(
            SETUP_INTRO,
            parse_mode='Markdown',
            reply_markup=setup_keyboard(is_vendor)
        )
    elif action == "become_vendor" and vendors:
        if is_vendor:
            await query.edit_message_text(
                "*You're already a vendor!*\n\n"
                "Use 'Manage My Products' to add and edit products.",
                parse_mode='Markdown',
                reply_markup=setup_keyboard(True)
            )
        else:
            # Register user as vendor
            user = update.effective_user
            vendor_name = user.full_name or user.username or f"Vendor_{user_id}"
            new_vendor = Vendor(telegram_id=user_id, name=vendor_name)
            vendors.add_vendor(new_vendor)

            await query.edit_message_text(
                "*Congratulations!*\n\n"
                f"You are now registered as a vendor: *{vendor_name}*\n\n"
                "You can now:\n"
                "- Add and manage products\n"
                "- Set your payment preferences\n"
                "- Configure your shop\n\n"
                "Start by adding your first product!",
                parse_mode='Markdown',
                reply_markup=setup_keyboard(True)
            )
    elif action == "payments" and vendors:
        # Get current payment methods from database
        selected = ["XMR"]
        if vendor:
            selected = vendors.get_accepted_payments_list(vendor)
        await query.edit_message_text(
            "*Payment Methods*\n\n"
            "Select which cryptocurrencies you want to accept.\n"
            "XMR (Monero) is always enabled.\n\n"
            "Tap to toggle:",
            parse_mode='Markdown',
            reply_markup=payment_methods_keyboard(selected)
        )
    elif action == "shopname":
        context.user_data['awaiting_input'] = 'shopname'
        await query.edit_message_text(
            "*Set Shop Name*\n\n"
            "Please type your shop name and send it as a message.",
            parse_mode='Markdown'
        )
    elif action == "wallet":
        context.user_data['awaiting_input'] = 'wallet'
        await query.edit_message_text(
            "*Set Wallet Address*\n\n"
            "Please send your Monero (XMR) wallet address.\n\n"
            "This is where you'll receive payments.",
            parse_mode='Markdown'
        )
    elif action == "currency":
        # Get current currency from database
        current_currency = "USD"
        if vendor:
            current_currency = vendor.pricing_currency or "USD"
        await query.edit_message_text(
            "*Pricing Currency*\n\n"
            "Select the currency you want to use for product prices.\n\n"
            "Customers will see prices in your currency, and we'll automatically\n"
            "convert to crypto when they pay.",
            parse_mode='Markdown',
            reply_markup=currency_keyboard(current_currency)
        )
    elif action == "postage" and postage and vendor:
        # Show vendor's postage options
        postage_types = postage.list_by_vendor(vendor.id)
        await query.edit_message_text(
            "*Postage Options*\n\n"
            "Manage your shipping/delivery options.\n"
            "Customers will choose from these when ordering.",
            parse_mode='Markdown',
            reply_markup=postage_management_keyboard(postage_types)
        )
    elif action == "view":
        # Get settings from database
        vendor_status = "Yes" if is_vendor else "No"
        if vendor:
            shop_name = vendor.shop_name or "Not set"
            wallet = vendor.wallet_address or "Not set"
            payments = vendors.get_accepted_payments_list(vendor)
            pricing_currency = vendor.pricing_currency or "USD"
        else:
            shop_name = "Not set"
            wallet = "Not set"
            payments = ["XMR"]
            pricing_currency = "USD"

        payments_str = ", ".join(payments)
        wallet_display = f"`{wallet[:20]}...`" if wallet != "Not set" and len(wallet) > 20 else wallet
        await query.edit_message_text(
            f"*Your Settings*\n\n"
            f"*Vendor:* {vendor_status}\n"
            f"*Shop Name:* {shop_name}\n"
            f"*Pricing Currency:* {pricing_currency}\n"
            f"*Wallet:* {wallet_display}\n"
            f"*Payment Methods:* {payments_str}",
            parse_mode='Markdown',
            reply_markup=setup_keyboard(is_vendor)
        )


@handle_callback_errors
async def handle_payment_toggle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, vendors: VendorService = None) -> None:
    """Handle payment method toggle callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]
    coin = parts[2] if len(parts) > 2 else None

    user_id = update.effective_user.id
    vendor = vendors.get_by_telegram_id(user_id) if vendors else None

    if action == "toggle" and coin and len(parts) >= 3:
        # Get current payments from database
        if vendor and vendors:
            selected = vendors.get_accepted_payments_list(vendor)
        else:
            selected = ["XMR"]

        # XMR cannot be disabled
        if coin == "XMR":
            await query.answer("Monero (XMR) is always enabled.", show_alert=True)
            return

        if coin in selected:
            selected.remove(coin)
        else:
            selected.append(coin)

        # Save to database immediately
        if vendor and vendors:
            vendors.update_settings(vendor.id, accepted_payments=selected)

        await query.edit_message_text(
            "*Payment Methods*\n\n"
            "Select which cryptocurrencies you want to accept.\n"
            "XMR (Monero) is always enabled.\n\n"
            "Tap to toggle:",
            parse_mode='Markdown',
            reply_markup=payment_methods_keyboard(selected)
        )
    elif action == "save":
        # Get current payments from database
        if vendor and vendors:
            selected = vendors.get_accepted_payments_list(vendor)
        else:
            selected = ["XMR"]
        is_vendor = vendor is not None
        await query.edit_message_text(
            f"*Payment Methods Saved!*\n\n"
            f"You now accept: {', '.join(selected)}",
            parse_mode='Markdown',
            reply_markup=setup_keyboard(is_vendor)
        )


@handle_callback_errors
async def handle_currency_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, vendors: VendorService = None) -> None:
    """Handle currency selection callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]
    currency = parts[2]

    user_id = update.effective_user.id
    vendor = vendors.get_by_telegram_id(user_id) if vendors else None
    is_vendor = vendor is not None

    if action == "select":
        # Save to database
        if vendor and vendors:
            vendors.update_settings(vendor.id, pricing_currency=currency)

        # Get currency symbol
        symbol = "$"
        for code, name, sym in SUPPORTED_CURRENCIES:
            if code == currency:
                symbol = sym
                break

        await query.edit_message_text(
            f"*Currency Set!*\n\n"
            f"Your products will be priced in {symbol} ({currency}).\n\n"
            f"When customers pay, we'll convert to their chosen crypto automatically.",
            parse_mode='Markdown',
            reply_markup=setup_keyboard(is_vendor)
        )


@handle_callback_errors
async def handle_postage_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, vendors: VendorService = None, postage: PostageService = None) -> None:
    """Handle postage management callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 2:
        return

    action = parts[1]

    user_id = update.effective_user.id
    vendor = vendors.get_by_telegram_id(user_id) if vendors else None

    if not vendor or not postage:
        await query.edit_message_text(
            "You need to be a vendor to manage postage options.",
            reply_markup=main_menu_keyboard()
        )
        return

    if action == "add":
        context.user_data['awaiting_input'] = 'postage_name'
        context.user_data['new_postage'] = {'vendor_id': vendor.id}
        await query.edit_message_text(
            "*Add Postage Option*\n\n"
            "Step 1/3: Enter the postage name\n"
            "(e.g., Standard, Express, Next Day):",
            parse_mode='Markdown'
        )

    elif action == "edit" and len(parts) >= 3:
        postage_id = int(parts[2])
        pt = postage.get_postage_type(postage_id)
        if pt:
            symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
            status = "Active" if pt.is_active else "Inactive"
            desc = pt.description or "No description"
            await query.edit_message_text(
                f"*{pt.name}*\n\n"
                f"Price: {symbol}{pt.price_fiat:.2f}\n"
                f"Description: {desc}\n"
                f"Status: {status}",
                parse_mode='Markdown',
                reply_markup=postage_edit_keyboard(postage_id)
            )

    elif action == "edit_name" and len(parts) >= 3:
        postage_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_postage_name'
        context.user_data['editing_postage'] = postage_id
        await query.edit_message_text(
            "*Edit Postage Name*\n\n"
            "Enter the new name:",
            parse_mode='Markdown'
        )

    elif action == "edit_price" and len(parts) >= 3:
        postage_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_postage_price'
        context.user_data['editing_postage'] = postage_id
        await query.edit_message_text(
            "*Edit Postage Price*\n\n"
            "Enter the new price (e.g., 5.99):",
            parse_mode='Markdown'
        )

    elif action == "edit_desc" and len(parts) >= 3:
        postage_id = int(parts[2])
        context.user_data['awaiting_input'] = 'edit_postage_desc'
        context.user_data['editing_postage'] = postage_id
        await query.edit_message_text(
            "*Edit Postage Description*\n\n"
            "Enter the new description\n"
            "(e.g., '3-5 business days'):",
            parse_mode='Markdown'
        )

    elif action == "toggle" and len(parts) >= 3:
        postage_id = int(parts[2])
        pt = postage.toggle_active(postage_id)
        if pt:
            status = "Active" if pt.is_active else "Inactive"
            await query.answer(f"Postage is now {status}", show_alert=True)
            symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
            desc = pt.description or "No description"
            await query.edit_message_text(
                f"*{pt.name}*\n\n"
                f"Price: {symbol}{pt.price_fiat:.2f}\n"
                f"Description: {desc}\n"
                f"Status: {status}",
                parse_mode='Markdown',
                reply_markup=postage_edit_keyboard(postage_id)
            )

    elif action == "delete" and len(parts) >= 3:
        postage_id = int(parts[2])
        postage.delete_postage_type(postage_id)
        postage_types = postage.list_by_vendor(vendor.id)
        await query.edit_message_text(
            "*Postage Deleted*\n\n"
            "The postage option has been removed.",
            parse_mode='Markdown',
            reply_markup=postage_management_keyboard(postage_types)
        )


@handle_callback_errors
async def handle_products_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService = None) -> None:
    """Handle product browsing callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]

    if action == "page":
        page = int(parts[2])
        products = context.user_data.get('products', [])
        await query.edit_message_text(
            "*Available Products*\n\nSelect a product to view details:",
            parse_mode='Markdown',
            reply_markup=products_keyboard(products, page=page)
        )


@handle_callback_errors
async def handle_product_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService = None) -> None:
    """Handle single product view callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]
    product_id = int(parts[2])

    if action == "view" and catalog:
        product = catalog.get_product(product_id)
        if product:
            in_stock = product.inventory > 0
            stock_status = f"{product.inventory} in stock" if in_stock else "Out of stock"

            # Format price display
            if product.price_fiat and product.currency and product.currency != "XMR":
                symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(product.currency, "$")
                price_display = f"`{symbol}{product.price_fiat:.2f}` ({product.currency})"
                xmr_note = f"\n_(~{product.price_xmr:.6f} XMR)_"
            else:
                price_display = f"`{product.price_xmr}` XMR"
                xmr_note = ""

            await query.edit_message_text(
                f"*{product.name}*\n\n"
                f"{product.description or 'No description'}\n\n"
                f"*Price:* {price_display}{xmr_note}\n"
                f"*Stock:* {stock_status}",
                parse_mode='Markdown',
                reply_markup=product_detail_keyboard(product_id, in_stock)
            )


@handle_callback_errors
async def handle_order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService = None, catalog: CatalogService = None, postage: PostageService = None, vendors: VendorService = None) -> None:
    """Handle order-related callbacks."""
    query = update.callback_query
    await query.answer()

    data = query.data
    parts = data.split(":")

    if len(parts) < 3:
        return

    action = parts[1]

    if action == "start" and catalog:
        product_id = int(parts[2])
        product = catalog.get_product(product_id)

        if not product or product.inventory <= 0:
            await query.edit_message_text(
                "Sorry, this product is no longer available.",
                reply_markup=main_menu_keyboard()
            )
            return

        context.user_data['ordering_product'] = product_id
        max_qty = min(product.inventory, 10)

        await query.edit_message_text(
            f"*Order: {product.name}*\n\n"
            f"Price: `{product.price_xmr}` XMR each\n\n"
            f"Select quantity:",
            parse_mode='Markdown',
            reply_markup=quantity_keyboard(product_id, max_qty)
        )

    elif action == "qty" and postage and catalog:
        product_id = int(parts[2])
        quantity = int(parts[3])

        context.user_data['order_quantity'] = quantity
        context.user_data['ordering_product'] = product_id

        # Get the vendor's postage options
        product = catalog.get_product(product_id)
        if product:
            postage_types = postage.list_by_vendor(product.vendor_id, active_only=True)
            if postage_types:
                await query.edit_message_text(
                    f"*Quantity: {quantity}*\n\n"
                    f"Select a delivery option:",
                    parse_mode='Markdown',
                    reply_markup=postage_selection_keyboard(postage_types, product_id, quantity)
                )
                return

        # No postage options available, go straight to address
        context.user_data['order_postage_id'] = None
        context.user_data['awaiting_input'] = 'delivery_address'

        await query.edit_message_text(
            f"*Quantity: {quantity}*\n\n"
            f"Please send your delivery address as a message.",
            parse_mode='Markdown'
        )

    elif action == "postage" and len(parts) >= 5:
        # order:postage:product_id:quantity:postage_id
        product_id = int(parts[2])
        quantity = int(parts[3])
        postage_id = int(parts[4])

        context.user_data['ordering_product'] = product_id
        context.user_data['order_quantity'] = quantity
        context.user_data['order_postage_id'] = postage_id if postage_id > 0 else None
        context.user_data['awaiting_input'] = 'delivery_address'

        postage_note = ""
        if postage_id > 0 and postage:
            pt = postage.get_postage_type(postage_id)
            if pt:
                symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
                postage_note = f"\n*Postage:* {pt.name} ({symbol}{pt.price_fiat:.2f})"

        await query.edit_message_text(
            f"*Quantity: {quantity}*{postage_note}\n\n"
            f"Please send your delivery address as a message.",
            parse_mode='Markdown'
        )

    elif action == "status" and orders:
        order_id = int(parts[2])
        order = orders.get_order(order_id)
        if order:
            status_emoji = {"NEW": "Awaiting payment", "PAID": "Payment received", "FULFILLED": "Completed", "CANCELLED": "Cancelled"}.get(order.state, order.state)
            try:
                await query.edit_message_text(
                    f"*Order #{order_id}*\n\n"
                    f"*Status:* {status_emoji}\n"
                    f"*Created:* {order.created_at.strftime('%Y-%m-%d %H:%M')}",
                    parse_mode='Markdown',
                    reply_markup=order_confirmation_keyboard(order_id)
                )
            except Exception:
                # Message unchanged, just answer the query
                await query.answer("Status unchanged", show_alert=False)
        else:
            await query.answer("Order not found", show_alert=True)

    elif action == "pay" and orders and len(parts) >= 4:
        order_id = int(parts[2])
        coin = parts[3]

        # Get payment details from order service
        try:
            payment_info = orders.get_payment_info(order_id, coin)
            await query.edit_message_text(
                f"*Order #{order_id} - Pay with {coin}*\n\n"
                f"*Amount:* `{payment_info.get('amount', 'N/A')}` {coin}\n"
                f"*Send to:* `{payment_info.get('address', 'N/A')}`\n\n"
                f"Please send the exact amount to complete your order.\n"
                f"Payment will be confirmed automatically.",
                parse_mode='Markdown',
                reply_markup=order_confirmation_keyboard(order_id)
            )
        except Exception:
            await query.edit_message_text(
                f"*Order #{order_id} - Pay with {coin}*\n\n"
                f"Payment address is being generated...\n"
                f"Please check back in a moment.",
                parse_mode='Markdown',
                reply_markup=order_confirmation_keyboard(order_id)
            )

    elif action == "cancel":
        order_id = int(parts[2])
        from ..keyboards import confirm_cancel_keyboard
        await query.edit_message_text(
            f"*Cancel Order #{order_id}?*\n\n"
            f"Are you sure you want to cancel this order?",
            parse_mode='Markdown',
            reply_markup=confirm_cancel_keyboard(order_id)
        )

    elif action == "confirm_cancel" and orders:
        order_id = int(parts[2])
        try:
            orders.cancel_order(order_id)
            await query.edit_message_text(
                f"*Order #{order_id} Cancelled*\n\n"
                f"Your order has been cancelled.",
                parse_mode='Markdown',
                reply_markup=main_menu_keyboard()
            )
        except Exception:
            await query.edit_message_text(
                f"Could not cancel order #{order_id}.",
                reply_markup=main_menu_keyboard()
            )

    elif action == "view" and orders:
        order_id = int(parts[2])
        try:
            order_info = orders.get_order(order_id)
            if order_info:
                # Get delivery address (decrypted)
                delivery_addr = orders.get_address(order_info)
                addr_display = delivery_addr[:30] + "..." if len(delivery_addr) > 30 else delivery_addr

                await query.edit_message_text(
                    f"*Order #{order_id}*\n\n"
                    f"*Status:* {order_info.state}\n"
                    f"*Quantity:* {order_info.quantity}\n"
                    f"*Address:* {addr_display}",
                    parse_mode='Markdown',
                    reply_markup=order_confirmation_keyboard(order_id)
                )
            else:
                await query.edit_message_text(
                    f"Order #{order_id} not found.",
                    reply_markup=main_menu_keyboard()
                )
        except Exception:
            await query.edit_message_text(
                f"Could not load order #{order_id}.",
                reply_markup=main_menu_keyboard()
            )


@handle_errors
async def handle_text_input(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService = None, catalog: CatalogService = None, vendors: VendorService = None, postage: PostageService = None) -> None:
    """Handle text input for setup flows."""
    awaiting = context.user_data.get('awaiting_input')

    if not awaiting:
        return

    text = update.message.text
    user_id = update.effective_user.id
    vendor = vendors.get_by_telegram_id(user_id) if vendors else None
    is_vendor = vendor is not None

    if awaiting == 'shopname':
        # Save to database
        if vendor and vendors:
            vendors.update_settings(vendor.id, shop_name=text)
        context.user_data['awaiting_input'] = None
        await update.message.reply_text(
            f"*Shop name set to:* {text}",
            parse_mode='Markdown',
            reply_markup=setup_keyboard(is_vendor)
        )

    elif awaiting == 'wallet':
        # Basic validation - Monero addresses start with 4 or 8 and are 95 chars
        if len(text) >= 95 and (text.startswith('4') or text.startswith('8')):
            # Save to database
            if vendor and vendors:
                vendors.update_settings(vendor.id, wallet_address=text)
            context.user_data['awaiting_input'] = None
            await update.message.reply_text(
                f"*Wallet address saved!*\n\n`{text[:30]}...`",
                parse_mode='Markdown',
                reply_markup=setup_keyboard(is_vendor)
            )
        else:
            await update.message.reply_text(
                "Invalid Monero address. Please send a valid XMR address.",
                reply_markup=setup_keyboard(is_vendor)
            )

    elif awaiting == 'delivery_address':
        product_id = context.user_data.get('ordering_product')
        quantity = context.user_data.get('order_quantity', 1)
        postage_id = context.user_data.get('order_postage_id')

        if orders and product_id:
            try:
                order_data = orders.create_order(product_id, quantity, text, postage_type_id=postage_id)
                context.user_data['awaiting_input'] = None
                context.user_data['ordering_product'] = None
                context.user_data['order_quantity'] = None
                context.user_data['order_postage_id'] = None

                # Build order summary
                postage_info = ""
                if postage_id and postage:
                    pt = postage.get_postage_type(postage_id)
                    if pt:
                        postage_info = f"\n*Postage:* {pt.name}"

                await update.message.reply_text(
                    f"*Order #{order_data['order_id']} Created!*\n\n"
                    f"*Amount:* `{order_data['total_xmr']:.6f}` XMR{postage_info}\n"
                    f"*Send to:*\n`{order_data['payment_address']}`\n\n"
                    f"*Payment ID:* `{order_data['payment_id']}`\n\n"
                    f"Send the exact amount to complete your order.",
                    parse_mode='Markdown',
                    reply_markup=order_confirmation_keyboard(order_data['order_id'])
                )
            except Exception as e:
                await update.message.reply_text(
                    f"Error creating order: {str(e)}",
                    reply_markup=main_menu_keyboard()
                )
        else:
            await update.message.reply_text(
                "Order session expired. Please try again.",
                reply_markup=main_menu_keyboard()
            )

    # Postage creation/editing inputs
    elif awaiting == 'postage_name' and postage and vendor:
        new_postage = context.user_data.get('new_postage', {})
        new_postage['name'] = text
        context.user_data['new_postage'] = new_postage
        context.user_data['awaiting_input'] = 'postage_price'
        await update.message.reply_text(
            "*Add Postage Option*\n\n"
            f"Name: {text}\n\n"
            "Step 2/3: Enter the price (e.g., 5.99):",
            parse_mode='Markdown'
        )

    elif awaiting == 'postage_price' and postage and vendor:
        try:
            price = float(text)
            new_postage = context.user_data.get('new_postage', {})
            new_postage['price'] = price
            context.user_data['new_postage'] = new_postage
            context.user_data['awaiting_input'] = 'postage_desc'
            await update.message.reply_text(
                "*Add Postage Option*\n\n"
                f"Name: {new_postage.get('name')}\n"
                f"Price: ${price:.2f}\n\n"
                "Step 3/3: Enter a description\n"
                "(e.g., '3-5 business days', or 'skip' for none):",
                parse_mode='Markdown'
            )
        except ValueError:
            await update.message.reply_text(
                "Invalid price. Please enter a number (e.g., 5.99):"
            )

    elif awaiting == 'postage_desc' and postage and vendor:
        new_postage = context.user_data.get('new_postage', {})
        desc = None if text.lower() == 'skip' else text

        pt = postage.add_postage_type(
            vendor_id=vendor.id,
            name=new_postage.get('name', 'Unnamed'),
            price_fiat=Decimal(str(new_postage.get('price', 0))),
            currency=vendor.pricing_currency or 'USD',
            description=desc
        )

        context.user_data['awaiting_input'] = None
        context.user_data['new_postage'] = None

        postage_types = postage.list_by_vendor(vendor.id)
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
        await update.message.reply_text(
            f"*Postage Option Added!*\n\n"
            f"*{pt.name}*\n"
            f"Price: {symbol}{pt.price_fiat:.2f}",
            parse_mode='Markdown',
            reply_markup=postage_management_keyboard(postage_types)
        )

    elif awaiting == 'edit_postage_name' and postage:
        postage_id = context.user_data.get('editing_postage')
        if postage_id:
            postage.update_postage_type(postage_id, name=text)
            context.user_data['awaiting_input'] = None
            context.user_data['editing_postage'] = None
            await update.message.reply_text(
                f"*Name Updated!*\n\nNew name: {text}",
                parse_mode='Markdown',
                reply_markup=postage_edit_keyboard(postage_id)
            )

    elif awaiting == 'edit_postage_price' and postage:
        postage_id = context.user_data.get('editing_postage')
        if postage_id:
            try:
                price = float(text)
                postage.update_postage_type(postage_id, price_fiat=Decimal(str(price)))
                context.user_data['awaiting_input'] = None
                context.user_data['editing_postage'] = None
                await update.message.reply_text(
                    f"*Price Updated!*\n\nNew price: ${price:.2f}",
                    parse_mode='Markdown',
                    reply_markup=postage_edit_keyboard(postage_id)
                )
            except ValueError:
                await update.message.reply_text(
                    "Invalid price. Please enter a number:"
                )

    elif awaiting == 'edit_postage_desc' and postage:
        postage_id = context.user_data.get('editing_postage')
        if postage_id:
            postage.update_postage_type(postage_id, description=text)
            context.user_data['awaiting_input'] = None
            context.user_data['editing_postage'] = None
            await update.message.reply_text(
                f"*Description Updated!*",
                parse_mode='Markdown',
                reply_markup=postage_edit_keyboard(postage_id)
            )
