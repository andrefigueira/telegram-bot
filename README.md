# Telegram E-commerce Bot

A privacy-focused, self-contained Telegram e-commerce bot with Monero (XMR) cryptocurrency payments. Designed for discreet commerce, this bot allows group owners to deploy their own instances to sell products while maintaining user privacy.

## Features

- 🔐 **Privacy-First**: All sensitive data encrypted using libsodium
- 💰 **Monero Payments**: Accept XMR for maximum transaction privacy  
- 👥 **Multi-Vendor Support**: Platform supports multiple vendors with commission system
- 🔑 **TOTP Authentication**: Optional two-factor authentication for admin commands
- 📦 **Self-Contained**: Easy deployment with Docker
- 🏥 **Health Monitoring**: Built-in health check endpoints
- 📊 **Production Ready**: Comprehensive logging, error handling, and monitoring

## Quick Start

### Prerequisites

- Python 3.12+ (for local development)
- Docker & Docker Compose (for deployment)
- Telegram Bot Token (from [@BotFather](https://t.me/botfather))
- Monero Wallet RPC (optional for development)

### Local Development Setup

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd telegram-bot
   ```

2. **Install dependencies**
   ```bash
   make setup
   ```

   If the command fails on macOS, install required build tools:
   ```bash
   brew install openssl readline sqlite3 xz zlib tcl-tk
   ```

3. **Configure environment**
   ```bash
   cp .env.template .env
   ```

   Edit `.env` with your configuration:
   ```bash
   # Required
   TELEGRAM_TOKEN=your_bot_token_here
   ENCRYPTION_KEY=your_32_byte_base64_key_here
   
   # Admin Setup
   ADMIN_IDS=123456789  # Your Telegram ID
   SUPER_ADMIN_IDS=123456789  # Platform admin ID
   
   # Optional
   TOTP_SECRET=your_totp_secret  # For 2FA
   MONERO_RPC_URL=http://127.0.0.1:18082  # Monero wallet
   ```

4. **Generate encryption key**
   ```bash
   python -c "import base64, os; print(base64.b64encode(os.urandom(32)).decode())"
   ```

5. **Run the bot**
   ```bash
   make run
   ```

## Testing

### Run Tests
```bash
make test
```

### Run Linting
```bash
make lint
```

### Test Coverage
The project maintains 100% test coverage. New features must include tests.

### Integration Testing

1. **Set up test environment**
   ```bash
   cp .env.template .env.test
   # Configure with test bot token and test wallet
   ```

2. **Run integration tests**
   ```bash
   ENVIRONMENT=test python -m pytest tests/integration/
   ```

3. **Manual testing checklist**
   - [ ] User can view products with `/list`
   - [ ] User can search products with `/list <search>`
   - [ ] User can place order with `/order <id> <quantity>`
   - [ ] Admin can add products with `/add <name> <price> <inventory>`
   - [ ] TOTP authentication works (if enabled)
   - [ ] Orders are encrypted in database
   - [ ] Health check responds at http://localhost:8080/health

## Deployment

### Using Docker Compose (Recommended)

1. **Prepare environment**
   ```bash
   # Create required directories
   mkdir -p data logs
   
   # Set up production environment
   cp .env.template .env.production
   # Edit .env.production with production values
   ```

2. **Build and deploy**
   ```bash
   # Build the image
   make build
   
   # Start with docker-compose
   docker-compose up -d
   
   # View logs
   docker-compose logs -f bot
   
   # Check health
   curl http://localhost:8080/health
   ```

3. **Production environment variables**
   ```bash
   # Required
   TELEGRAM_TOKEN=production_bot_token
   ENCRYPTION_KEY=production_32_byte_base64_key
   MONERO_RPC_URL=http://monero-wallet:18082
   
   # Security
   ADMIN_IDS=admin1_id,admin2_id
   SUPER_ADMIN_IDS=platform_admin_id
   TOTP_SECRET=production_totp_secret
   
   # Configuration
   ENVIRONMENT=production
   LOG_LEVEL=INFO
   DATABASE_URL=sqlite:////app/data/db.sqlite3
   LOG_FILE=/app/logs/bot.log
   DATA_RETENTION_DAYS=30
   DEFAULT_COMMISSION_RATE=0.05
   
   # Monitoring
   HEALTH_CHECK_ENABLED=true
   HEALTH_CHECK_PORT=8080
   ```

### Manual Docker Deployment

```bash
# Build image
docker build -t telegram-bot .

# Run container
docker run -d \
  --name telegram-bot \
  --env-file .env.production \
  -v $(pwd)/data:/app/data \
  -v $(pwd)/logs:/app/logs \
  -p 8080:8080 \
  --restart unless-stopped \
  telegram-bot
```

### Terraform Deployment (DigitalOcean)

Automate your infrastructure with Terraform:

1. **Prerequisites**
   ```bash
   # Install Terraform
   brew install terraform  # macOS
   # or download from https://terraform.io

   # Get DigitalOcean API token from:
   # https://cloud.digitalocean.com/account/api/tokens
   ```

2. **Configure**
   ```bash
   cd terraform
   cp terraform.tfvars.example terraform.tfvars
   ```

   Edit `terraform.tfvars`:
   ```hcl
   do_token       = "your-digitalocean-api-token"
   github_repo    = "your-username/telegram-bot"
   telegram_token = "your-telegram-bot-token"
   encryption_key = "your-base64-encryption-key"
   admin_ids      = "123456789"

   # Optional
   region       = "lon1"           # nyc1, sfo3, ams3, sgp1, etc.
   droplet_size = "s-1vcpu-1gb"    # $6/month
   environment  = "production"
   ```

3. **Deploy**
   ```bash
   terraform init    # Download providers
   terraform plan    # Preview changes
   terraform apply   # Create infrastructure
   ```

4. **Outputs**
   After deployment, Terraform shows:
   ```
   droplet_ip       = "123.45.67.89"
   health_check_url = "http://123.45.67.89:8080/health"
   ssh_command      = "ssh root@123.45.67.89"
   ```

5. **Manage**
   ```bash
   # View current state
   terraform show

   # Update infrastructure
   terraform apply

   # Destroy everything
   terraform destroy
   ```

6. **What gets created**
   - Ubuntu 24.04 droplet with Docker
   - Firewall (SSH + port 8080 only)
   - Bot auto-starts via systemd
   - Project grouping in DO dashboard

### Kubernetes Deployment

See `k8s/` directory for Kubernetes manifests (if available).

## Production Setup Guide

### 1. Monero Wallet Setup

For production, you need a Monero wallet with RPC enabled:

```bash
# Option 1: Use existing Monero node
monero-wallet-rpc \
  --rpc-bind-ip 0.0.0.0 \
  --rpc-bind-port 18082 \
  --disable-rpc-login \
  --wallet-file /path/to/wallet

# Option 2: Use Docker (uncomment in docker-compose.yml)
docker-compose up -d monero
```

### 2. Security Hardening

1. **Generate secure keys**
   ```bash
   # Encryption key
   openssl rand -base64 32
   
   # TOTP secret
   python -c "import pyotp; print(pyotp.random_base32())"
   ```

2. **Enable TOTP for all admins**
   - Set `TOTP_SECRET` in environment
   - Share secret with admins securely
   - Test with authenticator app

3. **Network security**
   - Use firewall to restrict access
   - Enable TLS for Monero RPC
   - Use VPN for admin access

### 3. Monitoring Setup

1. **Health checks**
   ```bash
   # Liveness check
   curl http://localhost:8080/health
   
   # Readiness check (includes DB check)
   curl http://localhost:8080/ready
   ```

2. **Log monitoring**
   ```bash
   # View logs
   tail -f logs/bot.log
   
   # Log rotation is automatic (10MB, 5 files)
   ```

3. **Metrics** (future enhancement)
   - Orders per day
   - Payment success rate
   - Response times

### 4. Backup Strategy

1. **Database backup**
   ```bash
   # Backup database
   docker exec telegram-bot sqlite3 /app/data/db.sqlite3 ".backup /app/data/backup.db"
   
   # Automated daily backup
   0 2 * * * docker exec telegram-bot sqlite3 /app/data/db.sqlite3 ".backup /app/data/backup-$(date +\%Y\%m\%d).db"
   ```

2. **Configuration backup**
   - Keep `.env` files in secure location
   - Version control for code changes
   - Document all customizations

## Usage Guide

### For Users

1. **Browse products**
   ```
   /list - Show all products
   /list laptop - Search for "laptop"
   ```

2. **Place order**
   ```
   /order 1 2 - Order 2 units of product ID 1
   ```

3. **Make payment**
   - Send exact XMR amount to provided address
   - Include payment ID if shown
   - Wait for confirmation

### For Vendors

1. **Add products** (requires vendor status)
   ```
   /add "Gaming Laptop" 0.5 10 - Add product with 0.5 XMR price, 10 in stock
   /add "Gaming Laptop" 0.5 10 123456 - With TOTP code if enabled
   ```

### For Platform Admins

1. **Manage vendors** (super admin only)
   ```
   /addvendor 987654321 "John's Store" - Add new vendor
   /vendors - List all vendors
   /commission 1 0.10 - Set 10% commission for vendor ID 1
   ```

## Troubleshooting

### Bot Not Responding

1. Check bot token is correct
2. Verify network connectivity
3. Check logs: `docker-compose logs bot`
4. Ensure bot is not blocked by Telegram

### Payment Issues

1. Verify Monero wallet RPC is running
2. Check wallet is synchronized
3. Ensure wallet has view key access
4. Review payment service logs

### Database Errors

1. Check disk space: `df -h`
2. Verify permissions: `ls -la data/`
3. Test database: `sqlite3 data/db.sqlite3 "SELECT 1;"`

### Debug Mode

For detailed debugging:
```bash
LOG_LEVEL=DEBUG docker-compose up bot
```

## Maintenance

### Regular Tasks

- **Daily**: Check logs for errors
- **Weekly**: Verify backups are working
- **Monthly**: Review disk usage, update dependencies
- **Quarterly**: Security audit, performance review

### Updates

```bash
# Update dependencies
cd telegram-bot
git pull
make build
docker-compose down
docker-compose up -d
```

## Architecture

See [agents.md](agents.md) for detailed architecture documentation.

## Security Considerations

- All sensitive data is encrypted at rest
- No personal information is logged
- Orders auto-delete after retention period
- TOTP required for admin actions (when enabled)
- Non-root Docker container
- Health checks don't expose sensitive data

## Contributing

See [agents.md](agents.md) for AI agent contributing guidelines.

## License

[Your License Here]

## Support

For issues and questions:
1. Check troubleshooting section
2. Review logs for error details
3. Create issue with reproduction steps
4. Include relevant log excerpts (sanitized)