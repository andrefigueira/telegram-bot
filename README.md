# Telegram E-commerce Bot

Minimal example of a privacy-first Telegram shop.

## Setup

```bash
make setup
```

Create `.env` from `.env.template` and fill values. Add your Telegram ID to
`ADMIN_IDS` for vendor commands and to `SUPER_ADMIN_IDS` for platform control.

## Usage

Run the bot:

```bash
make run
```

The bot stores minimal order metadata in SQLite. Old orders are automatically
purged after the interval configured via `DATA_RETENTION_DAYS`.

## Testing

```bash
make test
```

## Security

All personal data is encrypted using libsodium. Replace the payment and Telegram integrations with production-ready logic.
