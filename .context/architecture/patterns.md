# Code Patterns

## Handler Pattern

All command handlers follow this structure:

```python
from telegram import Update
from telegram.ext import ContextTypes

async def command_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # 1. Extract and validate input
    args = context.args
    if not args:
        await update.message.reply_text("Usage: /command <arg>")
        return

    # 2. Call service layer
    result = await service.do_something(args[0])

    # 3. Format and send response
    await update.message.reply_text(format_result(result))
```

## Service Pattern

Services encapsulate business logic and database operations:

```python
from sqlmodel import Session, select

class OrderService:
    def __init__(self, session: Session, payment_service: PaymentService):
        self.session = session
        self.payment_service = payment_service

    async def create_order(self, product_id: int, quantity: int, user_id: int) -> Order:
        # Business logic here
        product = self.session.get(Product, product_id)
        if not product or product.inventory < quantity:
            raise InsufficientInventoryError()

        # Coordinate with other services
        payment = await self.payment_service.create_payment(
            product.price * quantity
        )

        # Persist and return
        order = Order(product_id=product_id, quantity=quantity, ...)
        self.session.add(order)
        self.session.commit()
        return order
```

## Error Handling

Use custom exceptions for business errors:

```python
# bot/error_handler.py
class BotError(Exception):
    """Base exception for bot errors."""
    user_message: str = "An error occurred"

class InsufficientInventoryError(BotError):
    user_message = "Product is out of stock"

class PaymentError(BotError):
    user_message = "Payment processing failed"
```

Global error handler catches and formats errors:

```python
async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    error = context.error
    if isinstance(error, BotError):
        await update.message.reply_text(error.user_message)
    else:
        logger.exception("Unexpected error")
        await update.message.reply_text("Something went wrong")
```

## Encryption Pattern

Sensitive fields use encryption helpers:

```python
from nacl.secret import SecretBox
from nacl.encoding import Base64Encoder

def encrypt_field(value: str, key: bytes) -> str:
    box = SecretBox(key)
    encrypted = box.encrypt(value.encode(), encoder=Base64Encoder)
    return encrypted.decode()

def decrypt_field(encrypted: str, key: bytes) -> str:
    box = SecretBox(key)
    decrypted = box.decrypt(encrypted.encode(), encoder=Base64Encoder)
    return decrypted.decode()
```

## Testing Patterns

### Fixtures

```python
@pytest.fixture
def mock_update():
    update = MagicMock(spec=Update)
    update.message.reply_text = AsyncMock()
    update.effective_user.id = 12345
    return update

@pytest.fixture
def session():
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
```

### Service Tests

```python
async def test_create_order_success(session, mock_payment_service):
    service = OrderService(session, mock_payment_service)
    product = Product(name="Test", price=Decimal("10.00"), inventory=5)
    session.add(product)
    session.commit()

    order = await service.create_order(product.id, 2, user_id=123)

    assert order.quantity == 2
    assert product.inventory == 3  # Decremented
```

## Configuration Pattern

Environment-based configuration with validation:

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    telegram_token: str
    encryption_key: str
    monero_rpc_url: str | None = None
    admin_ids: list[int] = []

    class Config:
        env_file = ".env"
```
