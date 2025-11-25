# Development Guidelines

## Code Standards

### Python Style

- Follow PEP 8
- Use type hints for all function signatures
- Maximum line length: 100 characters
- Use `ruff` for linting and formatting

```python
# Good
async def create_order(
    product_id: int,
    quantity: int,
    user_id: int
) -> Order:
    ...

# Avoid
def create_order(product_id, quantity, user_id):
    ...
```

### Naming Conventions

| Type | Convention | Example |
|------|------------|---------|
| Functions | snake_case | `create_order` |
| Classes | PascalCase | `OrderService` |
| Constants | UPPER_SNAKE | `MAX_QUANTITY` |
| Private | _prefix | `_validate_input` |
| Modules | snake_case | `payment_service.py` |

### Import Organization

```python
# Standard library
import asyncio
from datetime import datetime

# Third-party
from sqlmodel import Session, select
from telegram import Update

# Local
from bot.models import Order, Product
from bot.services.payments import PaymentService
```

## Project Structure

```
bot/
├── __init__.py
├── main.py              # Entry point, application setup
├── config.py            # Settings and configuration
├── models.py            # SQLModel definitions
├── handlers/            # Telegram command handlers
│   ├── __init__.py
│   ├── admin.py
│   └── user.py
└── services/            # Business logic
    ├── __init__.py
    ├── catalog.py
    ├── orders.py
    ├── payments.py
    └── vendors.py
```

### Adding New Features

1. **Models**: Add SQLModel classes to `models.py`
2. **Services**: Create service class in `services/`
3. **Handlers**: Add command handlers in `handlers/`
4. **Tests**: Write tests in `tests/unit/`

## Testing

### Test Requirements

- **Coverage**: 100% required
- **Framework**: pytest with pytest-asyncio
- **Mocking**: Use unittest.mock for external dependencies

### Test Structure

```python
# tests/unit/test_orders.py
import pytest
from unittest.mock import AsyncMock, MagicMock

@pytest.fixture
def mock_session():
    return MagicMock()

@pytest.fixture
def mock_payment_service():
    service = AsyncMock()
    service.create_payment.return_value = PaymentDetails(...)
    return service

async def test_create_order_success(mock_session, mock_payment_service):
    service = OrderService(mock_session, mock_payment_service)
    # ... test implementation
```

### Running Tests

```bash
# Run all tests
pytest

# With coverage
pytest --cov=bot --cov-report=html

# Specific test file
pytest tests/unit/test_orders.py

# Verbose output
pytest -v
```

## Error Handling

### Exception Hierarchy

```python
class BotError(Exception):
    """Base exception for bot errors."""
    user_message = "An error occurred"

class ValidationError(BotError):
    user_message = "Invalid input"

class NotFoundError(BotError):
    user_message = "Not found"

class PaymentError(BotError):
    user_message = "Payment processing failed"
```

### Handler Error Pattern

```python
async def order_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        # ... handler logic
    except ValidationError as e:
        await update.message.reply_text(e.user_message)
    except NotFoundError:
        await update.message.reply_text("Product not found")
    except Exception as e:
        logger.exception("Unexpected error in order_handler")
        await update.message.reply_text("Something went wrong")
```

## Logging

### Log Levels

| Level | Usage |
|-------|-------|
| DEBUG | Detailed diagnostic info |
| INFO | General operational events |
| WARNING | Unexpected but handled situations |
| ERROR | Errors requiring attention |
| CRITICAL | System failures |

### Logging Pattern

```python
import logging

logger = logging.getLogger(__name__)

async def process_payment(order_id: int):
    logger.info(f"Processing payment for order {order_id}")

    try:
        result = await payment_service.verify(order_id)
        logger.debug(f"Payment verification result: {result}")
    except PaymentError as e:
        logger.error(f"Payment failed for order {order_id}: {e}")
        raise
```

### Security Logging

Never log:
- Encryption keys
- User addresses
- Payment amounts (use order IDs instead)
- TOTP codes

## Git Workflow

### Branch Naming

```
feature/add-product-search
bugfix/fix-payment-timeout
hotfix/security-patch
```

### Commit Messages

```
feat: add product search functionality
fix: handle payment timeout correctly
docs: update payment documentation
test: add order service tests
refactor: simplify payment verification
```

### Pre-commit Checks

```yaml
# .pre-commit-config.yaml
repos:
  - repo: local
    hooks:
      - id: ruff
        name: ruff
        entry: ruff check --fix
        language: system
        types: [python]

      - id: pytest
        name: pytest
        entry: pytest --tb=short
        language: system
        pass_filenames: false
```

## Docker

### Development

```bash
# Build and run
docker-compose up --build

# Run tests in container
docker-compose run --rm bot pytest

# Shell access
docker-compose run --rm bot bash
```

### Production

```bash
# Build production image
docker build -t telegram-bot:latest .

# Run with environment file
docker run --env-file .env telegram-bot:latest
```

## Security Checklist

Before deploying:

- [ ] All secrets in environment variables
- [ ] TOTP enabled for admin commands
- [ ] Encryption key properly generated
- [ ] Database file permissions restricted
- [ ] Logs don't contain sensitive data
- [ ] Rate limiting enabled
- [ ] Error messages sanitized
- [ ] Dependencies up to date

## Performance

### Database

- Use indexes for frequently queried fields
- Implement connection pooling for high load
- Add pagination for large result sets

### Telegram

- Batch message updates when possible
- Implement request queuing for rate limits
- Use webhooks in production (vs polling)

### Payments

- Cache wallet balance (refresh periodically)
- Batch payment status checks
- Use background tasks for monitoring
