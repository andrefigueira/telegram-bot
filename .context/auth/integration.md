# Telegram Integration

## Bot Registration

### Creating the Bot

1. Message @BotFather on Telegram
2. Send `/newbot` and follow prompts
3. Save the bot token securely

### Required Bot Settings

Configure via @BotFather:

```
/setprivacy - Disable (to receive all group messages)
/setjoingroups - Enable (for group deployment)
/setcommands - Set command menu
```

### Command Menu

```
start - Welcome message and instructions
list - Browse available products
order - Place an order
help - Show help information
```

## python-telegram-bot Integration

### Application Setup

```python
from telegram.ext import Application, CommandHandler

def create_application(token: str) -> Application:
    app = Application.builder().token(token).build()

    # User commands
    app.add_handler(CommandHandler("start", start_handler))
    app.add_handler(CommandHandler("list", list_handler))
    app.add_handler(CommandHandler("order", order_handler))

    # Admin commands
    app.add_handler(CommandHandler("add", add_product_handler))
    app.add_handler(CommandHandler("addvendor", add_vendor_handler))

    # Error handler
    app.add_error_handler(error_handler)

    return app
```

### Message Handling

```python
from telegram import Update
from telegram.ext import ContextTypes

async def start_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    welcome = f"Welcome {user.first_name}! Use /list to browse products."
    await update.message.reply_text(welcome)
```

### Inline Keyboards

For product selection and order confirmation:

```python
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

def create_product_keyboard(products: list[Product]) -> InlineKeyboardMarkup:
    buttons = [
        [InlineKeyboardButton(
            f"{p.name} - {p.price} XMR",
            callback_data=f"order:{p.id}"
        )]
        for p in products
    ]
    return InlineKeyboardMarkup(buttons)
```

### Callback Queries

```python
from telegram.ext import CallbackQueryHandler

async def order_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()

    _, product_id = query.data.split(":")
    # Process order...

app.add_handler(CallbackQueryHandler(order_callback, pattern="^order:"))
```

## User Identity

Telegram provides user identity via `update.effective_user`:

```python
user = update.effective_user
user.id          # Unique numeric ID
user.username    # @username (may be None)
user.first_name  # First name
user.last_name   # Last name (may be None)
```

User IDs are stable and used for:
- Admin authorization checks
- Order attribution
- Rate limiting

## Group vs Private Chat

The bot supports both deployment modes:

```python
def is_private_chat(update: Update) -> bool:
    return update.effective_chat.type == "private"

async def handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if is_private_chat(update):
        # Full functionality
        pass
    else:
        # Limited group functionality
        pass
```

## Rate Limiting

Implement per-user rate limiting:

```python
from collections import defaultdict
from time import time

rate_limits: dict[int, list[float]] = defaultdict(list)
WINDOW = 60  # seconds
MAX_REQUESTS = 10

def check_rate_limit(user_id: int) -> bool:
    now = time()
    requests = rate_limits[user_id]
    requests[:] = [t for t in requests if now - t < WINDOW]

    if len(requests) >= MAX_REQUESTS:
        return False

    requests.append(now)
    return True
```
