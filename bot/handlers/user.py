"""User command handlers."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes

from ..services.catalog import CatalogService
from ..services.orders import OrderService
from ..error_handler import handle_errors


@handle_errors
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Greet the user."""
    welcome_msg = (
        "Welcome to the shop!\n\n"
        "Commands:\n"
        "/products - Browse products\n"
        "/order <id> <qty> <address> - Place order\n"
    )
    await update.message.reply_text(welcome_msg)


@handle_errors
async def list_products(update: Update, context: ContextTypes.DEFAULT_TYPE, catalog: CatalogService) -> None:
    """List available products or search results."""
    query = context.args[0] if context.args else ""
    products = catalog.search(query) if query else catalog.list_products()
    if not products:
        await update.message.reply_text("No products found.")
        return
    
    # Format product list
    lines = ["📦 Available Products:"]
    for p in products:
        stock_status = "✅ In Stock" if p.inventory > 0 else "❌ Out of Stock"
        lines.append(f"\nID: {p.id}\n{p.name}\nPrice: {p.price_xmr} XMR\n{stock_status}")
    
    await update.message.reply_text("\n".join(lines))


@handle_errors
async def order(update: Update, context: ContextTypes.DEFAULT_TYPE, orders: OrderService) -> None:
    """Create an order."""
    args = context.args
    if len(args) < 3:
        await update.message.reply_text(
            "Usage: /order <product_id> <quantity> <delivery_address>\n\n"
            "Example: /order 1 2 My delivery address here"
        )
        return
    
    try:
        prod_id = int(args[0])
        qty = int(args[1])
    except ValueError:
        await update.message.reply_text("Invalid product ID or quantity. Please use numbers.")
        return
    
    # Join all remaining args as address
    addr = " ".join(args[2:])
    
    # Create order
    order_data = orders.create_order(prod_id, qty, addr)
    
    # Send payment instructions
    payment_msg = (
        f"✅ Order #{order_data['order_id']} created!\n\n"
        f"💰 Amount: {order_data['total_xmr']} XMR\n"
        f"📍 Send to: `{order_data['payment_address']}`\n\n"
        f"Please send the exact amount to the address above.\n"
        f"Your order will be processed once payment is confirmed."
    )
    
    await update.message.reply_text(payment_msg, parse_mode='Markdown')
