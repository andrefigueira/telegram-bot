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
