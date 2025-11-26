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

# Supported fiat currencies for product pricing
SUPPORTED_CURRENCIES = [
    ("USD", "US Dollar", "$"),
    ("GBP", "British Pound", "£"),
    ("EUR", "Euro", "€"),
    ("XMR", "Monero", "XMR"),
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
        keyboard.append([InlineKeyboardButton("Manage Postage Options", callback_data="setup:postage")])
        keyboard.append([InlineKeyboardButton("View My Orders", callback_data="admin:orders")])

    keyboard.extend([
        [InlineKeyboardButton("Set Payment Methods", callback_data="setup:payments")],
        [InlineKeyboardButton("Set Pricing Currency", callback_data="setup:currency")],
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


def currency_keyboard(current: str = "USD") -> InlineKeyboardMarkup:
    """Currency selection keyboard for product pricing."""
    keyboard = []
    for code, name, symbol in SUPPORTED_CURRENCIES:
        check = ">" if code == current else " "
        keyboard.append([
            InlineKeyboardButton(
                f"{check} {symbol} {name} ({code})",
                callback_data=f"currency:select:{code}"
            )
        ])

    keyboard.append([
        InlineKeyboardButton("Back", callback_data="setup:main"),
    ])
    return InlineKeyboardMarkup(keyboard)


def _format_product_price(product) -> str:
    """Format product price for display."""
    # If product has fiat price, show that
    if hasattr(product, 'price_fiat') and product.price_fiat and product.currency != "XMR":
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(product.currency, "$")
        return f"{symbol}{product.price_fiat:.2f}"
    # Otherwise show XMR price
    return f"{product.price_xmr} XMR"


def products_keyboard(products: list, page: int = 0, per_page: int = 5) -> InlineKeyboardMarkup:
    """Product listing with pagination."""
    keyboard = []

    start = page * per_page
    end = start + per_page
    page_products = products[start:end]

    for p in page_products:
        stock = "In Stock" if p.inventory > 0 else "Out of Stock"
        price_display = _format_product_price(p)
        keyboard.append([
            InlineKeyboardButton(
                f"{p.name} - {price_display} ({stock})",
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
        price_display = _format_product_price(p)
        keyboard.append([
            InlineKeyboardButton(
                f"{p.name} - {price_display} ({p.inventory}) {status}",
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


def postage_management_keyboard(postage_types: list) -> InlineKeyboardMarkup:
    """Vendor's postage type management keyboard."""
    keyboard = []

    for pt in postage_types[:10]:
        status = "Active" if pt.is_active else "Inactive"
        symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
        keyboard.append([
            InlineKeyboardButton(
                f"{pt.name} - {symbol}{pt.price_fiat:.2f} ({status})",
                callback_data=f"postage:edit:{pt.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("+ Add Postage Option", callback_data="postage:add")])
    keyboard.append([InlineKeyboardButton("Back to Setup", callback_data="setup:main")])
    return InlineKeyboardMarkup(keyboard)


def postage_edit_keyboard(postage_id: int) -> InlineKeyboardMarkup:
    """Postage type edit options keyboard."""
    keyboard = [
        [
            InlineKeyboardButton("Edit Name", callback_data=f"postage:edit_name:{postage_id}"),
            InlineKeyboardButton("Edit Price", callback_data=f"postage:edit_price:{postage_id}"),
        ],
        [
            InlineKeyboardButton("Edit Description", callback_data=f"postage:edit_desc:{postage_id}"),
            InlineKeyboardButton("Toggle Active", callback_data=f"postage:toggle:{postage_id}"),
        ],
        [
            InlineKeyboardButton("Delete", callback_data=f"postage:delete:{postage_id}"),
        ],
        [InlineKeyboardButton("Back to Postage", callback_data="setup:postage")],
    ]
    return InlineKeyboardMarkup(keyboard)


def postage_selection_keyboard(postage_types: list, product_id: int, quantity: int) -> InlineKeyboardMarkup:
    """Postage selection during order flow."""
    keyboard = []

    for pt in postage_types:
        if pt.is_active:
            symbol = {"USD": "$", "GBP": "£", "EUR": "€"}.get(pt.currency, "$")
            desc = f" - {pt.description}" if pt.description else ""
            keyboard.append([
                InlineKeyboardButton(
                    f"{pt.name} ({symbol}{pt.price_fiat:.2f}){desc}",
                    callback_data=f"order:postage:{product_id}:{quantity}:{pt.id}"
                )
            ])

    # Option for no postage (pickup/digital)
    keyboard.append([
        InlineKeyboardButton("No Postage Required", callback_data=f"order:postage:{product_id}:{quantity}:0")
    ])

    keyboard.append([InlineKeyboardButton("Cancel", callback_data=f"product:view:{product_id}")])
    return InlineKeyboardMarkup(keyboard)


def vendor_orders_keyboard(orders: list) -> InlineKeyboardMarkup:
    """Vendor's order management keyboard."""
    keyboard = []

    for order in orders[:10]:
        status_emoji = {
            "NEW": "New",
            "PAID": "Paid",
            "SHIPPED": "Shipped",
            "COMPLETED": "Done",
            "CANCELLED": "X",
        }.get(order.state, "?")

        keyboard.append([
            InlineKeyboardButton(
                f"#{order.id} - {status_emoji}",
                callback_data=f"vorder:view:{order.id}"
            )
        ])

    keyboard.append([InlineKeyboardButton("Back to Menu", callback_data="menu:admin")])
    return InlineKeyboardMarkup(keyboard)


def vendor_order_detail_keyboard(order_id: int, state: str) -> InlineKeyboardMarkup:
    """Vendor's order detail keyboard with actions."""
    keyboard = []

    if state == "PAID":
        keyboard.append([
            InlineKeyboardButton("Mark as Shipped", callback_data=f"vorder:ship:{order_id}")
        ])
    elif state == "SHIPPED":
        keyboard.append([
            InlineKeyboardButton("Mark as Completed", callback_data=f"vorder:complete:{order_id}")
        ])

    keyboard.append([InlineKeyboardButton("Back to Orders", callback_data="admin:orders")])
    return InlineKeyboardMarkup(keyboard)


def super_admin_keyboard() -> InlineKeyboardMarkup:
    """Super admin control panel keyboard."""
    keyboard = [
        [InlineKeyboardButton("Platform Stats", callback_data="sadmin:stats")],
        [InlineKeyboardButton("Set Commission Rate", callback_data="sadmin:commission")],
        [InlineKeyboardButton("Set Platform Wallet", callback_data="sadmin:wallet")],
        [InlineKeyboardButton("Process Payouts", callback_data="sadmin:payouts")],
        [InlineKeyboardButton("View Pending Payouts", callback_data="sadmin:pending")],
        [InlineKeyboardButton("Manage Vendors", callback_data="sadmin:vendors")],
        [InlineKeyboardButton("Back to Menu", callback_data="menu:main")],
    ]
    return InlineKeyboardMarkup(keyboard)


def commission_rate_keyboard(current_rate: str) -> InlineKeyboardMarkup:
    """Commission rate selection keyboard."""
    rates = [
        ("3%", "0.03"),
        ("5%", "0.05"),
        ("7%", "0.07"),
        ("10%", "0.10"),
        ("15%", "0.15"),
    ]

    keyboard = []
    row = []
    for label, value in rates:
        marker = ">" if value == current_rate else " "
        row.append(InlineKeyboardButton(
            f"{marker}{label}",
            callback_data=f"sadmin:set_commission:{value}"
        ))
        if len(row) == 3:
            keyboard.append(row)
            row = []

    if row:
        keyboard.append(row)

    keyboard.append([InlineKeyboardButton("Custom Rate", callback_data="sadmin:custom_commission")])
    keyboard.append([InlineKeyboardButton("Back", callback_data="sadmin:main")])
    return InlineKeyboardMarkup(keyboard)
