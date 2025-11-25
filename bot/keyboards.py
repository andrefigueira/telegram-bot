"""Inline keyboard builders for Telegram bot UI."""

from telegram import InlineKeyboardButton, InlineKeyboardMarkup
from typing import List, Optional

# Supported cryptocurrencies for payment
SUPPORTED_COINS = [
    ("XMR", "Monero"),
    ("BTC", "Bitcoin"),
    ("ETH", "Ethereum"),
    ("SOL", "Solana"),
    ("LTC", "Litecoin"),
    ("USDT", "Tether"),
    ("USDC", "USD Coin"),
]


def main_menu_keyboard() -> InlineKeyboardMarkup:
    """Main menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Browse Products", callback_data="menu:products"),
            InlineKeyboardButton("My Orders", callback_data="menu:orders"),
        ],
        [
            InlineKeyboardButton("Setup Shop", callback_data="menu:setup"),
            InlineKeyboardButton("Help", callback_data="menu:help"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def help_keyboard() -> InlineKeyboardMarkup:
    """Help menu keyboard."""
    keyboard = [
        [InlineKeyboardButton("Back to Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def setup_keyboard(is_vendor: bool = False) -> InlineKeyboardMarkup:
    """Setup menu keyboard."""
    keyboard = []

    if not is_vendor:
        keyboard.append([InlineKeyboardButton("Become a Vendor", callback_data="setup:become_vendor")])
    else:
        keyboard.append([InlineKeyboardButton("Manage My Products", callback_data="admin:products")])

    keyboard.extend([
        [InlineKeyboardButton("Set Payment Methods", callback_data="setup:payments")],
        [InlineKeyboardButton("Set Shop Name", callback_data="setup:shopname")],
        [InlineKeyboardButton("Set Wallet Address", callback_data="setup:wallet")],
        [InlineKeyboardButton("View My Settings", callback_data="setup:view")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu:main")],
    ])
    return InlineKeyboardMarkup(keyboard)


def payment_methods_keyboard(selected: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    """Payment method selection keyboard with checkboxes."""
    if selected is None:
        selected = ["XMR"]  # XMR is always enabled by default

    keyboard = []
    for coin_code, coin_name in SUPPORTED_COINS:
        check = "[x]" if coin_code in selected else "[ ]"
        keyboard.append([
            InlineKeyboardButton(
                f"{check} {coin_name} ({coin_code})",
                callback_data=f"pay:toggle:{coin_code}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("Save", callback_data="pay:save"),
        InlineKeyboardButton("Cancel", callback_data="setup:main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def products_keyboard(products: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Product listing with pagination."""
    keyboard = []

    start = page * per_page
    end = start + per_page
    page_products = products[start:end]

    for p in page_products:
        stock = "In Stock" if p.inventory > 0 else "Out of Stock"
        keyboard.append([
            InlineKeyboardButton(
                f"{p.name} - {p.price_xmr} XMR ({stock})",
                callback_data=f"product:view:{p.id}"
            )
        ])

    # Pagination buttons
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("< Prev", callback_data=f"products:page:{page-1}"))
    if end < len(products):
        nav_buttons.append(InlineKeyboardButton("Next >", callback_data=f"products:page:{page+1}"))
    if nav_buttons:
        keyboard.append(nav_buttons)

    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(keyboard)


def product_detail_keyboard(product_id: int, in_stock: bool = True) -> InlineKeyboardMarkup:
    """Product detail view keyboard."""
    keyboard = []

    if in_stock:
        keyboard.append([
            InlineKeyboardButton("Order Now", callback_data=f"order:start:{product_id}")
        ])

    keyboard.append([
        InlineKeyboardButton("Back to Products", callback_data="menu:products")
    ])
    return InlineKeyboardMarkup(keyboard)


def quantity_keyboard(product_id: int, max_qty: int = 10) -> InlineKeyboardMarkup:
    """Quantity selection keyboard."""
    keyboard = []

    # Show quantities in rows of 5
    row = []
    for qty in range(1, min(max_qty + 1, 11)):
        row.append(InlineKeyboardButton(str(qty), callback_data=f"order:qty:{product_id}:{qty}"))
        if len(row) == 5:
            keyboard.append(row)
            row = []
    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("Cancel", callback_data=f"product:view:{product_id}")])
    return InlineKeyboardMarkup(keyboard)


def payment_coin_keyboard(order_id: int, accepted_coins: Optional[List[str]] = None) -> InlineKeyboardMarkup:
    """Payment coin selection keyboard."""
    if accepted_coins is None:
        accepted_coins = ["XMR"]

    keyboard = []
    row = []

    for coin_code, coin_name in SUPPORTED_COINS:
        if coin_code in accepted_coins:
            row.append(InlineKeyboardButton(
                f"{coin_name}",
                callback_data=f"order:pay:{order_id}:{coin_code}"
            ))
            if len(row) == 2:
                keyboard.append(row)
                row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("Cancel Order", callback_data=f"order:cancel:{order_id}")])
    return InlineKeyboardMarkup(keyboard)


def order_confirmation_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Order confirmation keyboard."""
    keyboard = [
        [InlineKeyboardButton("Check Payment Status", callback_data=f"order:status:{order_id}")],
        [InlineKeyboardButton("My Orders", callback_data="menu:orders")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def orders_keyboard(orders: list) -> InlineKeyboardMarkup:
    """Orders list keyboard."""
    keyboard = []

    for order in orders[:10]:  # Show max 10 recent orders
        status_emoji = {
            "pending": "...",
            "paid": "Paid",
            "fulfilled": "Done",
            "cancelled": "X",
            "expired": "Exp",
        }.get(order.state, "?")

        keyboard.append([
            InlineKeyboardButton(
                f"#{order.id} - {status_emoji}",
                callback_data=f"order:view:{order.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="menu:main")])
    return InlineKeyboardMarkup(keyboard)


def confirm_cancel_keyboard(order_id: int) -> InlineKeyboardMarkup:
    """Confirm order cancellation keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Yes, Cancel", callback_data=f"order:confirm_cancel:{order_id}"),
            InlineKeyboardButton("No, Keep It", callback_data=f"order:view:{order_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)


def admin_menu_keyboard() -> InlineKeyboardMarkup:
    """Admin menu keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Add Product", callback_data="admin:add_product"),
            InlineKeyboardButton("My Products", callback_data="admin:products"),
        ],
        [
            InlineKeyboardButton("View Orders", callback_data="admin:orders"),
            InlineKeyboardButton("Shop Settings", callback_data="admin:settings"),
        ],
        [InlineKeyboardButton("Back to Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def vendor_products_keyboard(products: list) -> InlineKeyboardMarkup:
    """Vendor's product management keyboard."""
    keyboard = []

    for p in products[:10]:
        status = "Active" if p.inventory > 0 else "Out"
        keyboard.append([
            InlineKeyboardButton(
                f"{p.name} ({p.inventory}) - {status}",
                callback_data=f"vendor:edit:{p.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("+ Add New Product", callback_data="vendor:add")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="menu:admin")])
    return InlineKeyboardMarkup(keyboard)


def product_edit_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Product edit options keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Edit Name", callback_data=f"vendor:edit_name:{product_id}"),
            InlineKeyboardButton("Edit Price", callback_data=f"vendor:edit_price:{product_id}"),
        ],
        [
            InlineKeyboardButton("Edit Stock", callback_data=f"vendor:edit_stock:{product_id}"),
            InlineKeyboardButton("Edit Description", callback_data=f"vendor:edit_desc:{product_id}"),
        ],
        [
            InlineKeyboardButton("Delete Product", callback_data=f"vendor:delete:{product_id}"),
        ],
        [InlineKeyboardButton("Back to Products", callback_data="admin:products")],
    ]
    return InlineKeyboardMarkup(keyboard)


def confirm_delete_keyboard(product_id: int) -> InlineKeyboardMarkup:
    """Confirm product deletion keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Yes, Delete", callback_data=f"vendor:confirm_delete:{product_id}"),
            InlineKeyboardButton("Cancel", callback_data=f"vendor:edit:{product_id}"),
        ],
    ]
    return InlineKeyboardMarkup(keyboard)
