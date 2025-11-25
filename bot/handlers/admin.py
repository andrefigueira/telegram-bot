"""Admin command handlers."""

from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..services.vendors import VendorService
from ..models import Product, Vendor
from ..config import get_settings
from ..error_handler import handle_errors
from ..keyboards import (
    admin_menu_keyboard,
    vendor_products_keyboard,
    product_edit_keyboard,
    confirm_delete_keyboard,
    main_menu_keyboard,
    SUPPORTED_CURRENCIES,
)
from ..services.currency import (
    fiat_to_xmr_accurate,
    format_price_simple,
    get_currency_symbol,
)
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

    elif action == "orders":
        await query.edit_message_text(
            "*Orders*\n\n"
            "Order management coming soon!\n\n"
            "Use `/status <order_id>` to check orders for now.",
            parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )

    elif action == "settings":
        await query.edit_message_text(
            "*Shop Settings*\n\n"
            "Use /setup to configure your shop settings.",
            parse_mode='Markdown',
            reply_markup=admin_menu_keyboard()
        )


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
                        'edit_name', 'edit_price', 'edit_stock', 'edit_desc']:
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
