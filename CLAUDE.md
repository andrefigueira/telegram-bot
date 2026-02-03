# CLAUDE.md - Project Instructions

This is a privacy-focused Telegram e-commerce bot with Monero (XMR) payments. Read this file first, then consult the `.context/` directory for detailed documentation.

## Quick Reference

- **Language**: Python 3.12
- **Framework**: python-telegram-bot v20.3
- **Database**: SQLModel with SQLite (MySQL in production)
- **Encryption**: PyNaCl (libsodium)
- **Payments**: Monero cryptocurrency
- **Testing**: pytest with 100% coverage requirement

## Key Commands

```bash
make setup     # Install dependencies
make test      # Run tests
make lint      # Run linting
make run       # Start bot locally
docker-compose up --build  # Run in Docker
```

## Code Style

- Follow PEP 8, use type hints for all functions
- No comments unless specifically requested
- Use `ruff` for linting and formatting
- Never log sensitive data (keys, addresses, TOTP codes)

## Architecture Pattern

```
bot/
├── handlers/    # Telegram command handlers (admin.py, user.py)
├── services/    # Business logic (catalog, orders, payments, vendors)
├── models.py    # SQLModel definitions with encryption
├── config.py    # Settings management
└── tasks.py     # Background tasks
```

**Adding features**: Models -> Services -> Handlers -> Tests

## Security Requirements

- All sensitive data encrypted at rest using libsodium
- Two-tier admin system with TOTP 2FA protection
- Validate all user input, sanitize user-provided text
- Use parameterized queries (SQLModel handles this)
- Never hardcode secrets, use environment variables

## Testing Requirements

- Maintain 100% test coverage
- Mock external services (Telegram, Monero)
- Use pytest fixtures for test data
- Run `pytest --cov=bot --cov-report=html`

---

## .context/ Documentation Index

Consult these files for detailed domain knowledge when working on specific areas.

### Entry Point
| File | Description |
|------|-------------|
| `.context/substrate.md` | Main entry point, project summary, key design decisions |
| `.context/guidelines.md` | Development standards, code style, testing, git workflow |

### Architecture
| File | Description |
|------|-------------|
| `.context/architecture/overview.md` | System design and diagrams |
| `.context/architecture/dependencies.md` | External dependencies and versions |
| `.context/architecture/patterns.md` | Code patterns and conventions |
| `.context/architecture/saas-multi-tenant.md` | Multi-tenant SaaS architecture |

### Authentication & Security
| File | Description |
|------|-------------|
| `.context/auth/overview.md` | Authentication system design |
| `.context/auth/integration.md` | Telegram integration details |
| `.context/auth/security.md` | Security model and threat considerations |

### Bot Commands
| File | Description |
|------|-------------|
| `.context/commands/user.md` | User command reference (/start, /list, /order) |
| `.context/commands/admin.md` | Admin command reference (/add, /addvendor, /vendors) |
| `.context/commands/examples.md` | Usage examples and flows |

### Database
| File | Description |
|------|-------------|
| `.context/database/schema.md` | Database schema and relationships |
| `.context/database/models.md` | SQLModel class definitions |
| `.context/database/encryption.md` | Encryption at rest implementation |

### Payments
| File | Description |
|------|-------------|
| `.context/payments/overview.md` | Payment system design |
| `.context/payments/integration.md` | Monero RPC integration |
| `.context/payments/security.md` | Payment security considerations |

### Infrastructure
| File | Description |
|------|-------------|
| `.context/infrastructure/overview.md` | Infrastructure overview |
| `.context/infrastructure/terraform.md` | Terraform configuration |
| `.context/infrastructure/deployment.md` | Deployment procedures |

---

## When to Consult .context/

- **Adding a new command**: Read `.context/commands/admin.md` or `user.md`
- **Modifying database**: Read `.context/database/schema.md` and `models.md`
- **Payment work**: Read `.context/payments/overview.md` and `integration.md`
- **Security changes**: Read `.context/auth/security.md` and `.context/payments/security.md`
- **Deployment**: Read `.context/infrastructure/deployment.md`
- **Code patterns**: Read `.context/architecture/patterns.md`
