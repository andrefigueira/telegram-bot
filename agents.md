# AI Agent Contributing Guide for Telegram E-commerce Bot

> **Context Documentation**: For detailed domain knowledge, see the [`.context/`](.context/substrate.md) directory which follows the [Substrate Methodology](https://github.com/andrefigueira/.context/).

## Quick Context Navigation

| Domain | Documentation |
|--------|---------------|
| System Architecture | [.context/architecture/](.context/architecture/overview.md) |
| Authentication & Security | [.context/auth/](.context/auth/overview.md) |
| Bot Commands | [.context/commands/](.context/commands/user.md) |
| Database & Models | [.context/database/](.context/database/schema.md) |
| Monero Payments | [.context/payments/](.context/payments/overview.md) |
| Development Guidelines | [.context/guidelines.md](.context/guidelines.md) |

## Project Overview

This is a privacy-focused Telegram e-commerce bot designed for discreet commerce with Monero (XMR) cryptocurrency payments. The bot allows group owners to deploy their own instances to sell products while maintaining user privacy.

### Key Features
- **Privacy-First**: All sensitive data is encrypted using libsodium
- **Monero Integration**: Accepts XMR payments for maximum privacy
- **Multi-Vendor Support**: Platform supports multiple vendors with commission system
- **TOTP Authentication**: Optional two-factor authentication for admin commands
- **Self-Contained**: Designed to be easily deployable by non-technical users

## Architecture

### Technology Stack
- **Language**: Python 3.12
- **Framework**: python-telegram-bot (v20.3)
- **Database**: SQLModel (SQLAlchemy) with SQLite
- **Encryption**: PyNaCl (libsodium)
- **Authentication**: pyotp for TOTP
- **Payment**: Monero Python library
- **Testing**: pytest with 100% coverage requirement
- **Containerization**: Docker with health checks

### Project Structure
```
telegram-bot/
├── bot/
│   ├── __init__.py
│   ├── main.py           # Application entry point
│   ├── config.py         # Configuration management
│   ├── models.py         # Database models
│   ├── logging_config.py # Logging setup
│   ├── error_handler.py  # Error handling utilities
│   ├── health.py         # Health check server
│   ├── tasks.py          # Background tasks
│   ├── handlers/         # Command handlers
│   │   ├── admin.py      # Admin commands
│   │   └── user.py       # User commands
│   └── services/         # Business logic
│       ├── catalog.py    # Product management
│       ├── orders.py     # Order processing
│       ├── payments.py   # Monero payments
│       └── vendors.py    # Vendor management
├── tests/                # Test suite
├── Dockerfile           # Production container
├── docker-compose.yml   # Orchestration
└── pyproject.toml      # Dependencies
```

## Key Components

### 1. Security Layer

#### Encryption (models.py)
- Uses PyNaCl for encrypting sensitive data
- All personal data (addresses) is encrypted at rest
- Encryption key must be 32-byte base64-encoded

#### Authentication (handlers/admin.py)
- Two-tier admin system: regular admins and super admins
- Optional TOTP 2FA for all admin commands
- Super admins can manage vendors and commissions

### 2. Payment System (services/payments.py)

The payment service handles Monero transactions:
- Creates unique payment addresses with payment IDs
- Verifies incoming payments
- Falls back to mock mode in development

**Important**: The current implementation needs a running Monero wallet RPC. Agents should ensure proper error handling when the wallet is unavailable.

### 3. Data Models (models.py)

- **Product**: Items for sale with inventory tracking
- **Vendor**: Store owners with commission rates
- **Order**: Encrypted order data with payment tracking

### 4. Command Handlers

#### User Commands (handlers/user.py)
- `/start` - Welcome message
- `/list [search]` - Browse products
- `/order <product_id> <quantity>` - Place order

#### Admin Commands (handlers/admin.py)
- `/add <name> <price> <inventory> [totp]` - Add product
- `/addvendor <telegram_id> <name> [totp]` - Register vendor (super admin)
- `/vendors [totp]` - List all vendors (super admin)
- `/commission <vendor_id> <rate> [totp]` - Set commission (super admin)

## Development Guidelines

### 1. Code Style
- Follow PEP 8 standards
- Use type hints for all functions
- No comments unless specifically requested
- Keep functions focused and testable

### 2. Testing Requirements
- Maintain 100% test coverage
- Write unit tests for all new features
- Use pytest fixtures for test data
- Mock external services (Telegram, Monero)

### 3. Security Considerations
- Never log sensitive information
- Always validate user input
- Use parameterized queries (SQLModel handles this)
- Implement rate limiting for commands
- Sanitize all user-provided text

### 4. Error Handling
- Use the error_handler module for consistent error responses
- Log errors with appropriate levels
- Provide user-friendly error messages
- Implement retry logic for transient failures

## Common Tasks for AI Agents

### 1. Adding New Features

When adding features:
1. Update models.py if new data structures are needed
2. Create/update service classes in services/
3. Add command handlers in handlers/
4. Write comprehensive tests
5. Update this documentation

### 2. Improving Payment Integration

Current areas for enhancement:
- Add payment timeout handling
- Implement partial payment detection
- Add refund functionality
- Create payment confirmation webhooks

### 3. Enhancing Security

Potential improvements:
- Add rate limiting per user
- Implement message deletion after processing
- Add IP-based access control
- Enhance audit logging

### 4. Performance Optimization

Consider:
- Implement caching for product listings
- Add database connection pooling
- Optimize order queries
- Add pagination for large catalogs

## Environment Configuration

Required environment variables:
```bash
# Core Settings
TELEGRAM_TOKEN=           # Bot token from @BotFather
ENCRYPTION_KEY=          # 32-byte base64 key
MONERO_RPC_URL=         # Monero wallet RPC URL

# Admin Configuration  
ADMIN_IDS=              # Comma-separated Telegram IDs
SUPER_ADMIN_IDS=        # Platform admin IDs
TOTP_SECRET=            # Optional 2FA secret

# Production Settings
ENVIRONMENT=production
DATABASE_URL=sqlite:////app/data/db.sqlite3
LOG_LEVEL=INFO
LOG_FILE=/app/logs/bot.log

# Features
DATA_RETENTION_DAYS=30
DEFAULT_COMMISSION_RATE=0.05
HEALTH_CHECK_ENABLED=true
HEALTH_CHECK_PORT=8080
```

## Testing the Bot

### Local Development
```bash
# Install dependencies
make setup

# Run tests
make test

# Run linting
make lint

# Start bot locally
make run
```

### Integration Testing
1. Create a test Telegram bot via @BotFather
2. Set up test environment variables
3. Use test Monero wallets (stagenet)
4. Verify all commands work correctly

## Deployment Considerations

### Production Checklist
- [ ] Generate secure encryption key
- [ ] Set up Monero wallet RPC
- [ ] Configure TOTP secret
- [ ] Set appropriate admin IDs
- [ ] Enable health checks
- [ ] Configure log rotation
- [ ] Set up monitoring
- [ ] Plan backup strategy

### Security Hardening
- Run as non-root user
- Use environment variables (never hardcode secrets)
- Enable TOTP for all admin operations
- Regular security updates
- Monitor logs for suspicious activity

## Contributing Guidelines

### Before Making Changes
1. Review existing code patterns
2. Check test coverage requirements
3. Understand security implications
4. Plan database migrations if needed

### Submitting Changes
1. Ensure all tests pass
2. Maintain 100% coverage
3. Update documentation
4. Test in Docker environment
5. Verify production readiness

### Code Review Focus
- Security vulnerabilities
- Performance impact
- Error handling completeness
- Test coverage
- Documentation updates

## Troubleshooting

### Common Issues

1. **Monero Connection Failed**
   - Check MONERO_RPC_URL is correct
   - Ensure wallet RPC is running
   - Verify network connectivity

2. **Database Errors**
   - Check file permissions
   - Ensure directory exists
   - Verify disk space

3. **Telegram API Errors**
   - Validate bot token
   - Check rate limits
   - Verify network access

### Debug Mode
Set `LOG_LEVEL=DEBUG` for detailed logging

## Future Enhancements

### High Priority
- Database migrations system
- Advanced product search
- Order status tracking
- Automated payment confirmations
- Multi-language support

### Medium Priority  
- Product categories and tags
- Inventory alerts
- Sales analytics
- Bulk operations
- Export functionality

### Nice to Have
- Web dashboard
- Backup automation
- A/B testing framework
- Plugin system
- API for external integrations

## Resources

- [python-telegram-bot Documentation](https://docs.python-telegram-bot.org/)
- [Monero RPC Documentation](https://www.getmonero.org/resources/developer-guides/wallet-rpc.html)
- [SQLModel Documentation](https://sqlmodel.tiangolo.com/)
- [PyNaCl Documentation](https://pynacl.readthedocs.io/)

## Contact

For questions about the architecture or implementation details not covered here, refer to the inline code documentation or create an issue in the repository.