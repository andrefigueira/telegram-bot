"""User command handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..services.orders import OrderService


async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user."""
    await update.message.reply_text("Welcome to the shop!")


async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService) -> None:
    """List available products or search results."""
    query = context.args[0] if context.args else ""
    products = catalog.search(query) if query else catalog.list_products()
    if not products:
        await update.message.reply_text("No products.")
        return
    lines = [f"{p.id}: {p.name} ({p.price_xmr} XMR)" for p in products]
    await update.message.reply_text("\n".join(lines))


async def order(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService) -> None:
    """Create an order."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text("Usage: /order <product_id> <qty> <address>")
        return
    prod_id, qty, addr = int(args[0]), int(args[1]), args[2]
    order = orders.create_order(prod_id, qty, addr)
    await update.message.reply_text(f"Order {order.id} created. Pay to {order.payment_id}")
