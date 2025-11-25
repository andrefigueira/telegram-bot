# DarkPool.shop - SaaS Multi-Tenant Architecture

## Overview

Transform the single-tenant Telegram bot into a multi-tenant SaaS platform where customers can launch their own shops in minutes without any technical setup.

**Revenue Model**: Commission on all transactions (5%). No subscriptions.

**Liability Model**: Platform provides SOFTWARE ONLY. Shop owners operate independently. DarkPool never touches customer payments.

## Customer Journey

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           CUSTOMER ONBOARDING                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  1. VISIT              2. SIGN UP           3. CONNECT BOT                  │
│  darkpool.shop  ───►  Email/Password  ───►  Paste Telegram Token            │
│                                                                             │
│  4. CONFIGURE          5. DONE!                                             │
│  Add Monero wallet ───► Shop is LIVE                                        │
│                         Start adding products via Telegram                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Revenue Model

### Commission Only (5% on all transactions)

- **No subscription fees** - free to start
- **5% commission** on every completed sale
- **Weekly invoicing** - shop owners pay commission each Sunday
- **Unlimited products and orders** for everyone

### Commission Collection (Direct Split Model)

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        DIRECT SPLIT PAYMENT FLOW                            │
│                     (DarkPool NEVER holds customer funds)                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Customer                Shop Owner                  DarkPool               │
│  ────────                ──────────                  ────────               │
│      │                       │                           │                  │
│      │   Pays for product    │                           │                  │
│      │ ─────────────────────►│                           │                  │
│      │    (Direct to shop    │                           │                  │
│      │     owner's wallet)   │                           │                  │
│      │                       │                           │                  │
│      │                       │   Pays commission (weekly)│                  │
│      │                       │ ─────────────────────────►│                  │
│      │                       │   (From tracked sales)    │                  │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

**Why Direct Split?**
1. **Zero liability** - Customer payments go directly to shop owners
2. **No money transmission** - DarkPool is software, not a payment processor
3. **Trust** - Shop owners control their own funds
4. **Simple** - No complex escrow or holding wallets

### Commission Enforcement

Shop owners must pay weekly commission on tracked sales:
- System tracks all completed orders per tenant
- Weekly invoice generated (every Sunday)
- If unpaid after 7 days: bot suspended
- If unpaid after 14 days: account terminated

## System Architecture

```
                                   darkpool.shop
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │   Frontend   │   │   Backend    │   │  Bot Manager │
            │   (Next.js)  │   │   (FastAPI)  │   │   Service    │
            │              │   │              │   │              │
            │ - Landing    │   │ - Auth       │   │ - Spawns     │
            │ - Dashboard  │   │ - Billing    │   │   bot        │
            │ - Analytics  │   │ - API        │   │   workers    │
            └──────────────┘   └──────────────┘   └──────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                                        ▼
                               ┌──────────────────┐
                               │    PostgreSQL    │
                               │                  │
                               │ - Tenants        │
                               │ - Products       │
                               │ - Orders         │
                               │ - Subscriptions  │
                               │ - Commissions    │
                               └──────────────────┘
                                        │
                    ┌───────────────────┼───────────────────┐
                    │                   │                   │
                    ▼                   ▼                   ▼
            ┌──────────────┐   ┌──────────────┐   ┌──────────────┐
            │  Bot Worker  │   │  Bot Worker  │   │  Bot Worker  │
            │  (Shop A)    │   │  (Shop B)    │   │  (Shop C)    │
            │              │   │              │   │              │
            │ @shopabot    │   │ @shopbbot    │   │ @shopcbot    │
            │              │   │              │   │              │
            │ Uses owner's │   │ Uses owner's │   │ Uses owner's │
            │ Monero RPC   │   │ Monero RPC   │   │ Monero RPC   │
            └──────────────┘   └──────────────┘   └──────────────┘
                    │                   │                   │
                    └───────────────────┼───────────────────┘
                                        │
                                        ▼
                                   Telegram API
```

## Multi-Crypto Payments (Auto-Convert to XMR)

### Supported Payment Methods

Customers can pay in:
- **Monero (XMR)** - native, direct to shop owner
- **Bitcoin (BTC)** - auto-converted to XMR
- **Ethereum (ETH)** - auto-converted to XMR
- **Solana (SOL)** - auto-converted to XMR
- **Litecoin (LTC)** - auto-converted to XMR
- **USDT/USDC** - auto-converted to XMR

### Payment Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                     MULTI-CRYPTO PAYMENT FLOW                               │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  Customer selects        Swap Service              Shop Owner               │
│  payment method          (ChangeNow/Trocador)      (receives XMR)           │
│  ──────────────          ───────────────────       ─────────────            │
│        │                        │                        │                  │
│        │  "Pay with BTC"        │                        │                  │
│        │ ──────────────────────►│                        │                  │
│        │                        │                        │                  │
│        │  Returns temp BTC      │                        │                  │
│        │  address               │                        │                  │
│        │ ◄──────────────────────│                        │                  │
│        │                        │                        │                  │
│        │  Sends BTC             │                        │                  │
│        │ ──────────────────────►│                        │                  │
│        │                        │                        │                  │
│        │                        │  Converts BTC→XMR      │                  │
│        │                        │  Sends XMR             │                  │
│        │                        │ ──────────────────────►│                  │
│        │                        │                        │                  │
│                                                                             │
│  Result: Shop owner receives XMR regardless of what customer paid with      │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

### Swap Service Integration

Use aggregators for best rates and reliability:

```python
# services/crypto_swap.py

class CryptoSwapService:
    """Handle multi-crypto to XMR conversions."""

    SUPPORTED_COINS = ["btc", "eth", "sol", "ltc", "usdt", "usdc"]

    def __init__(self):
        # Trocador aggregates multiple swap services
        self.trocador_api = "https://trocador.app/api"
        # Fallback services
        self.changenow_api = "https://api.changenow.io/v2"
        self.sideshift_api = "https://sideshift.ai/api/v2"

    async def create_swap(
        self,
        from_coin: str,
        amount_usd: float,
        destination_xmr_address: str
    ) -> dict:
        """Create a swap from any coin to XMR."""

        # Get best rate from aggregator
        rate = await self._get_best_rate(from_coin, "xmr", amount_usd)

        # Create swap order
        swap = await self._create_order(
            from_coin=from_coin,
            to_coin="xmr",
            destination=destination_xmr_address,
            rate_id=rate["id"]
        )

        return {
            "deposit_address": swap["deposit_address"],  # Customer pays here
            "deposit_coin": from_coin,
            "expected_xmr": swap["expected_amount"],
            "expires_at": swap["expires_at"],
            "swap_id": swap["id"]
        }

    async def check_swap_status(self, swap_id: str) -> dict:
        """Check if swap completed."""
        status = await self._get_order_status(swap_id)
        return {
            "status": status["status"],  # waiting, confirming, exchanging, complete
            "received_xmr": status.get("received_amount")
        }
```

### Why This Approach?

1. **Shop owners only deal with XMR** - simple wallet management
2. **Customers have flexibility** - pay with what they have
3. **Untraceable receipts** - all conversions end in XMR
4. **No KYC for swaps** - services like Trocador don't require identity
5. **DarkPool never holds funds** - swaps go direct to shop owner

### Swap Service Options

| Service | KYC | Fees | Notes |
|---------|-----|------|-------|
| [Trocador](https://trocador.app) | No | Varies (aggregator) | Best rates, aggregates multiple services |
| [ChangeNow](https://changenow.io) | No (under limits) | ~0.5% | Popular, reliable |
| [SideShift](https://sideshift.ai) | No | ~1-2% | Good for privacy |
| [Exch.cx](https://exch.cx) | No | ~1% | XMR-focused |

## Platform Wallet

DarkPool operates ONE master wallet for **commission payments only**.

- Shop owners pay weekly commission **in XMR only**
- DarkPool never receives BTC/ETH/SOL - only XMR
- Commission payments are fully private

**NOT for customer purchase payments** - those go direct to shop owners via swap services.

## Database Schema (Multi-Tenant)

```sql
-- Tenants (Shop Owners)
CREATE TABLE tenants (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    email VARCHAR(255) UNIQUE NOT NULL,
    password_hash VARCHAR(255) NOT NULL,

    -- Telegram Bot Config
    bot_token_encrypted TEXT,  -- Encrypted with platform key
    bot_username VARCHAR(100),
    bot_active BOOLEAN DEFAULT FALSE,

    -- Shop Settings (owner provides their own)
    shop_name VARCHAR(100),
    monero_wallet_address VARCHAR(106),  -- Owner's wallet (subaddress)
    monero_view_key VARCHAR(64),         -- For payment verification only
    encryption_key VARCHAR(64) NOT NULL,  -- Auto-generated per tenant
    totp_secret VARCHAR(32),

    -- Subscription (paid in XMR)
    plan VARCHAR(20) DEFAULT 'free',
    plan_expires_at TIMESTAMP,
    commission_rate DECIMAL(4,3) DEFAULT 0.08,  -- Based on plan

    -- Limits based on plan
    max_products INT DEFAULT 10,
    max_orders_per_month INT DEFAULT 50,

    -- Liability
    accepted_terms_at TIMESTAMP NOT NULL,
    accepted_terms_version VARCHAR(10) NOT NULL,

    created_at TIMESTAMP DEFAULT NOW(),
    updated_at TIMESTAMP DEFAULT NOW()
);

-- Subscription payments (XMR)
CREATE TABLE subscription_payments (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    plan VARCHAR(20) NOT NULL,
    amount_xmr DECIMAL(18,12) NOT NULL,
    payment_address VARCHAR(106) NOT NULL,
    payment_id VARCHAR(64) NOT NULL,
    state VARCHAR(20) DEFAULT 'pending',  -- pending, confirmed, expired
    expires_at TIMESTAMP NOT NULL,
    confirmed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Products (scoped to tenant)
CREATE TABLE products (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    name VARCHAR(100) NOT NULL,
    description TEXT,
    category VARCHAR(50),
    price_xmr DECIMAL(18,12) NOT NULL,
    media_id VARCHAR(255),
    inventory INT DEFAULT 0,
    active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Orders (scoped to tenant) - payments go DIRECT to shop owner
CREATE TABLE orders (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id) ON DELETE CASCADE,
    product_id INT REFERENCES products(id),
    customer_telegram_id BIGINT NOT NULL,
    quantity INT NOT NULL,
    total_xmr DECIMAL(18,12) NOT NULL,

    -- Payment goes to SHOP OWNER's address, not DarkPool
    payment_address VARCHAR(106) NOT NULL,  -- Shop owner's subaddress
    payment_id VARCHAR(64) NOT NULL,

    address_encrypted TEXT NOT NULL,  -- Delivery address
    state VARCHAR(20) DEFAULT 'pending',
    created_at TIMESTAMP DEFAULT NOW(),
    paid_at TIMESTAMP
);

-- Commission invoices (weekly)
CREATE TABLE commission_invoices (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    period_start DATE NOT NULL,
    period_end DATE NOT NULL,

    -- Sales tracking
    order_count INT NOT NULL,
    total_sales_xmr DECIMAL(18,12) NOT NULL,

    -- Commission calculation
    commission_rate DECIMAL(4,3) NOT NULL,
    commission_due_xmr DECIMAL(18,12) NOT NULL,

    -- Payment to DarkPool
    payment_address VARCHAR(106),  -- DarkPool's address
    payment_id VARCHAR(64),

    state VARCHAR(20) DEFAULT 'pending',  -- pending, paid, overdue, waived
    due_date TIMESTAMP NOT NULL,
    paid_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT NOW(),

    UNIQUE(tenant_id, period_start)
);

-- Usage tracking
CREATE TABLE usage_logs (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    month DATE NOT NULL,
    orders_count INT DEFAULT 0,
    revenue_xmr DECIMAL(18,12) DEFAULT 0,
    UNIQUE(tenant_id, month)
);

-- Audit log (for compliance)
CREATE TABLE audit_log (
    id SERIAL PRIMARY KEY,
    tenant_id UUID REFERENCES tenants(id),
    action VARCHAR(50) NOT NULL,
    details JSONB,
    ip_address INET,
    created_at TIMESTAMP DEFAULT NOW()
);

-- Indexes
CREATE INDEX idx_products_tenant ON products(tenant_id);
CREATE INDEX idx_orders_tenant ON orders(tenant_id);
CREATE INDEX idx_orders_payment_id ON orders(payment_id);
CREATE INDEX idx_commission_tenant_period ON commission_invoices(tenant_id, period_start);
CREATE INDEX idx_subscription_payments_state ON subscription_payments(state);
```

## Liability Protection

### Legal Structure

1. **Terms of Service** - Shop owners must accept:
   - They are solely responsible for their products/services
   - They comply with all applicable laws
   - DarkPool is a software provider only
   - DarkPool has no control over shop content
   - Indemnification clause

2. **Platform Architecture**:
   - DarkPool NEVER receives customer payments
   - Payments go direct from buyer to shop owner
   - DarkPool only receives subscription + commission from shop owner
   - No escrow, no holding of funds

3. **Data Minimization**:
   - Delivery addresses encrypted, only shop owner can decrypt
   - Customer data minimal (only Telegram ID)
   - Logs retained minimally (configurable by tenant)

4. **Compliance Features**:
   - Audit log for all admin actions
   - IP logging optional
   - Terms acceptance versioned and timestamped

### Terms of Service (Required Acceptance)

```
DARKPOOL.SHOP TERMS OF SERVICE

1. SERVICE DESCRIPTION
DarkPool provides software to operate Telegram shopping bots.
DarkPool does NOT:
- Sell products
- Process payments
- Hold customer funds
- Control shop content
- Verify product legality

2. SHOP OWNER RESPONSIBILITIES
You are solely responsible for:
- All products listed in your shop
- Compliance with applicable laws
- Payment processing via your own wallet
- Customer service and disputes
- Tax obligations

3. INDEMNIFICATION
You agree to indemnify and hold harmless DarkPool from any
claims arising from your use of the platform.

4. TERMINATION
DarkPool may terminate accounts that:
- Violate these terms
- Fail to pay commissions
- Receive legal complaints

By creating an account, you accept these terms.
Version: 1.0
```

## Bot Manager Service

```python
# bot_manager/manager.py

class BotManager:
    """Manages multiple bot instances for tenants."""

    def __init__(self, db: Database):
        self.db = db
        self.active_bots: dict[str, BotWorker] = {}

    async def start_bot(self, tenant_id: str) -> bool:
        """Start a bot for a tenant."""
        tenant = await self.db.get_tenant(tenant_id)

        # Verify subscription is active
        if not self._is_subscription_active(tenant):
            return False

        # Verify commission is paid
        if await self._has_overdue_commission(tenant_id):
            return False

        if not tenant or not tenant.bot_token_encrypted:
            return False

        # Decrypt bot token
        token = self._decrypt_token(tenant.bot_token_encrypted)

        worker = BotWorker(
            tenant_id=tenant_id,
            token=token,
            monero_address=tenant.monero_wallet_address,
            monero_view_key=tenant.monero_view_key,
            db=self.db
        )
        await worker.start()
        self.active_bots[tenant_id] = worker
        return True

    async def stop_bot(self, tenant_id: str):
        """Stop a tenant's bot."""
        if tenant_id in self.active_bots:
            await self.active_bots[tenant_id].stop()
            del self.active_bots[tenant_id]

    async def restart_all(self):
        """Restart all active bots (on deploy)."""
        tenants = await self.db.get_active_tenants()
        for tenant in tenants:
            await self.start_bot(tenant.id)

    def _is_subscription_active(self, tenant) -> bool:
        """Check if subscription is valid."""
        if tenant.plan == "free":
            return True
        return tenant.plan_expires_at > datetime.utcnow()

    async def _has_overdue_commission(self, tenant_id: str) -> bool:
        """Check for overdue commission invoices."""
        overdue = await self.db.get_overdue_invoices(tenant_id)
        return len(overdue) > 0
```

## Commission Service

```python
# services/commission.py

class CommissionService:
    """Handle weekly commission invoicing and collection."""

    def __init__(self, db: Database, monero_rpc: MoneroRPC):
        self.db = db
        self.rpc = monero_rpc

    async def generate_weekly_invoices(self):
        """Generate commission invoices for all tenants (run every Sunday)."""
        period_end = date.today()
        period_start = period_end - timedelta(days=7)

        tenants = await self.db.get_all_active_tenants()

        for tenant in tenants:
            # Get completed orders for the period
            orders = await self.db.get_completed_orders(
                tenant_id=tenant.id,
                start_date=period_start,
                end_date=period_end
            )

            if not orders:
                continue

            total_sales = sum(o.total_xmr for o in orders)
            commission_due = total_sales * tenant.commission_rate

            if commission_due <= 0:
                continue

            # Generate payment address
            address = await self.rpc.create_address()
            payment_id = secrets.token_hex(32)

            await self.db.create_commission_invoice(
                tenant_id=tenant.id,
                period_start=period_start,
                period_end=period_end,
                order_count=len(orders),
                total_sales_xmr=total_sales,
                commission_rate=tenant.commission_rate,
                commission_due_xmr=commission_due,
                payment_address=address,
                payment_id=payment_id,
                due_date=datetime.utcnow() + timedelta(days=7)
            )

            # Notify tenant via Telegram
            await self._notify_invoice(tenant, commission_due)

    async def check_commission_payments(self):
        """Check for paid commissions (run hourly)."""
        pending = await self.db.get_pending_invoices()

        for invoice in pending:
            received = await self.rpc.get_payments(invoice.payment_id)
            if received >= invoice.commission_due_xmr:
                await self.db.mark_invoice_paid(invoice.id)

    async def suspend_overdue_accounts(self):
        """Suspend bots with overdue commissions (run daily)."""
        overdue = await self.db.get_overdue_invoices()

        for invoice in overdue:
            days_overdue = (datetime.utcnow() - invoice.due_date).days

            if days_overdue >= 7:
                # Suspend bot
                await self.bot_manager.stop_bot(invoice.tenant_id)
                await self._notify_suspension(invoice.tenant_id)

            if days_overdue >= 14:
                # Terminate account
                await self.db.deactivate_tenant(invoice.tenant_id)
                await self._notify_termination(invoice.tenant_id)
```

## API Endpoints

### Auth
```
POST /api/auth/register     - Create account (requires terms acceptance)
POST /api/auth/login        - Login, get JWT
POST /api/auth/logout       - Invalidate token
```

### Tenant Dashboard
```
GET  /api/me                - Get tenant profile
PUT  /api/me                - Update profile
POST /api/me/bot            - Connect bot token
DELETE /api/me/bot          - Disconnect bot

GET  /api/products          - List products
POST /api/products          - Create product
PUT  /api/products/:id      - Update product
DELETE /api/products/:id    - Delete product

GET  /api/orders            - List orders
GET  /api/orders/:id        - Order details

GET  /api/analytics         - Dashboard stats
```

### Billing (Monero)
```
GET  /api/billing/plans              - Get available plans with XMR prices
POST /api/billing/subscribe          - Create subscription payment (returns XMR address)
GET  /api/billing/subscription       - Get current subscription status
GET  /api/billing/commissions        - List commission invoices
GET  /api/billing/commissions/:id    - Get invoice details with payment address
```

## Frontend Pages (darkpool.shop)

```
/                   - Landing page (marketing)
/pricing            - Pricing plans (XMR prices)
/terms              - Terms of Service
/login              - Login
/register           - Sign up (with terms checkbox)
/dashboard          - Main dashboard
/dashboard/products - Manage products
/dashboard/orders   - View orders
/dashboard/settings - Shop settings, bot token, wallet address
/dashboard/billing  - Subscription + commission payments
```

## Deployment Architecture

```yaml
# docker-compose.prod.yml
version: '3.8'

services:
  frontend:
    image: darkpool-frontend:latest
    ports:
      - "3000:3000"
    environment:
      - API_URL=http://backend:8000

  backend:
    image: darkpool-backend:latest
    ports:
      - "8000:8000"
    environment:
      - DATABASE_URL=postgresql://...
      - JWT_SECRET=...
      - PLATFORM_ENCRYPTION_KEY=...
    depends_on:
      - postgres
      - redis

  bot-manager:
    image: darkpool-bot-manager:latest
    environment:
      - DATABASE_URL=postgresql://...
      - PLATFORM_MONERO_RPC=http://monero-wallet-rpc:18082
    depends_on:
      - postgres
      - redis
      - monero-wallet-rpc

  # Platform wallet for subscriptions + commissions ONLY
  monero-wallet-rpc:
    image: sethsimmons/simple-monero-wallet-rpc:latest
    volumes:
      - monero_wallet:/wallet
    environment:
      - DAEMON_ADDRESS=node.moneroworld.com:18089
    command: --wallet-file=/wallet/darkpool --password=${WALLET_PASSWORD} --rpc-bind-port=18082

  postgres:
    image: postgres:15
    volumes:
      - postgres_data:/var/lib/postgresql/data
    environment:
      - POSTGRES_DB=darkpool
      - POSTGRES_USER=darkpool
      - POSTGRES_PASSWORD=${DB_PASSWORD}

  redis:
    image: redis:7
    volumes:
      - redis_data:/data

volumes:
  postgres_data:
  redis_data:
  monero_wallet:
```

## Implementation Phases

### Phase 1: Core Multi-Tenancy
- [ ] PostgreSQL schema migration
- [ ] Tenant model with terms acceptance
- [ ] Bot Manager service
- [ ] Multi-tenant bot workers
- [ ] Each tenant uses their own Monero wallet

### Phase 2: Dashboard
- [ ] Next.js frontend setup
- [ ] Landing page
- [ ] Terms of Service page
- [ ] Auth pages (login/register with terms)
- [ ] Dashboard with product/order management
- [ ] Wallet configuration

### Phase 3: Monero Billing
- [ ] Platform Monero wallet setup
- [ ] Subscription payment flow (XMR)
- [ ] Commission invoice generation
- [ ] Commission payment verification
- [ ] Auto-suspension for overdue accounts

### Phase 4: Polish
- [ ] Analytics dashboard
- [ ] Email/Telegram notifications
- [ ] Audit logging
- [ ] Rate limiting

## Security Considerations

1. **Tenant Isolation**: All queries scoped by tenant_id
2. **Bot Token Security**: Encrypted with platform key, never exposed
3. **Rate Limiting**: Per-tenant rate limits
4. **Encryption Keys**: Auto-generated per tenant for their data
5. **Payment Security**: Shop owners control their own wallets
6. **Audit Trail**: All admin actions logged

## Liability Summary

| Concern | Protection |
|---------|------------|
| Illegal products | Shop owner responsibility, terms acceptance |
| Payment disputes | Direct to shop owner, DarkPool not involved |
| Customer data | Encrypted, only shop owner can decrypt |
| Money transmission | DarkPool receives software fees only |
| Content moderation | Shop owner responsibility |
