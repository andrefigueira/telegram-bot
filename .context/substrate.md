# Telegram E-commerce Bot - Context Substrate

> Documentation as Code as Context

This directory contains structured documentation following the Substrate Methodology. It provides AI agents and developers with comprehensive, Git-native context for building and maintaining this privacy-focused Telegram e-commerce bot.

## Quick Navigation

| Domain | Description |
|--------|-------------|
| [Architecture](./architecture/) | System design, dependencies, and code patterns |
| [Auth](./auth/) | TOTP authentication and admin authorization |
| [Commands](./commands/) | Telegram bot command reference |
| [Database](./database/) | Schema, models, and encryption |
| [Payments](./payments/) | Monero integration and payment flows |
| [Guidelines](./guidelines.md) | Development standards and workflows |

## Project Summary

**Name**: Privacy-First Telegram E-commerce Bot
**Tech Stack**: Python 3.12, python-telegram-bot, SQLModel, PyNaCl, Monero
**Architecture**: Modular service-oriented design with handler/service separation
**Database**: SQLite with SQLModel ORM
**Authentication**: TOTP-based admin 2FA
**Payments**: Monero (XMR) cryptocurrency

## Key Design Decisions

1. **Privacy-First Architecture**: All sensitive data encrypted at rest using libsodium
2. **Self-Contained Deployment**: Single Docker container with SQLite for easy deployment
3. **Two-Tier Admin System**: Regular admins and super admins with TOTP protection
4. **Mock Mode Support**: Development without Monero wallet RPC dependency

## Context Usage

### For AI Agents

Reference the full context documentation in `agents.md` at project root, which links to this substrate for detailed domain knowledge.

```bash
# Concatenate all context for comprehensive AI assistance
cat .context/**/*.md > full-context.txt
```

### For Developers

Start with this file, then explore domain-specific documentation based on your task:

- **Adding features**: Start with [architecture/patterns.md](./architecture/patterns.md)
- **Security work**: Review [auth/security.md](./auth/security.md) and [payments/security.md](./payments/security.md)
- **Database changes**: See [database/schema.md](./database/schema.md)

## File Structure

```
.context/
├── substrate.md              # This file - entry point
├── architecture/
│   ├── overview.md          # System design with diagrams
│   ├── dependencies.md      # External dependencies
│   └── patterns.md          # Code patterns and conventions
├── auth/
│   ├── overview.md          # Authentication system
│   ├── integration.md       # Telegram integration
│   └── security.md          # Security model
├── commands/
│   ├── user.md              # User command reference
│   ├── admin.md             # Admin command reference
│   └── examples.md          # Usage examples
├── database/
│   ├── schema.md            # Database schema
│   ├── models.md            # SQLModel definitions
│   └── encryption.md        # Encryption at rest
├── payments/
│   ├── overview.md          # Payment system design
│   ├── integration.md       # Monero RPC integration
│   └── security.md          # Payment security
└── guidelines.md            # Development standards
```

## Versioning

This documentation follows the codebase version. Update context files when making architectural changes.

---

*Generated following the [Substrate Methodology](https://github.com/andrefigueira/.context/)*
