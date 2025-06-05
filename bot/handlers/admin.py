"""Admin command handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..models import Product


async def add(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService) -> None:
    """Add a new product from command arguments."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /add <name> <price> <inventory>")
        return
    name, price, inventory = args[0], float(args[1]), int(args[2])
    product = Product(name=name, description="", price_xmr=price, inventory=inventory)
    catalog.add_product(product)
    await update.message.reply_text(f"Added {product.name}")
