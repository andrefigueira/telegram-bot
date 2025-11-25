"""Multi-tenant database models for DarkPool SaaS platform."""

import secrets
from datetime import datetime, date
from decimal import Decimal
from enum import Enum
from typing import Optional
from uuid import uuid4

from sqlmodel import SQLModel, Field, Relationship


class OrderState(str, Enum):
    """Order state enum."""
    PENDING = "pending"
    SWAP_PENDING = "swap_pending"
    PAID = "paid"
    FULFILLED = "fulfilled"
    CANCELLED = "cancelled"
    EXPIRED = "expired"


class InvoiceState(str, Enum):
    """Commission invoice state."""
    PENDING = "pending"
    PAID = "paid"
    OVERDUE = "overdue"
    WAIVED = "waived"


class SwapState(str, Enum):
    """Swap transaction state."""
    WAITING = "waiting"
    CONFIRMING = "confirming"
    EXCHANGING = "exchanging"
    COMPLETE = "complete"
    FAILED = "failed"
    EXPIRED = "expired"


# ============================================================================
# TENANT MODELS
# ============================================================================

class Tenant(SQLModel, table=True):
    """Shop owner / tenant account."""
    __tablename__ = "tenants"

    id: str = Field(default_factory=lambda: str(uuid4()), primary_key=True)
    email: str = Field(unique=True, index=True)
    password_hash: str

    # Telegram Bot Config
    bot_token_encrypted: Optional[str] = None
    bot_username: Optional[str] = None
    bot_active: bool = Field(default=False)

    # Shop Settings
    shop_name: Optional[str] = None
    monero_wallet_address: Optional[str] = None
    monero_view_key: Optional[str] = None
    encryption_key: str = Field(default_factory=lambda: secrets.token_hex(32))
    totp_secret: Optional[str] = None

    # Commission (5% default)
    commission_rate: Decimal = Field(default=Decimal("0.05"))

    # Liability
    accepted_terms_at: Optional[datetime] = None
    accepted_terms_version: Optional[str] = None

    # Timestamps
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    products: list["TenantProduct"] = Relationship(back_populates="tenant")
    orders: list["TenantOrder"] = Relationship(back_populates="tenant")
    invoices: list["CommissionInvoice"] = Relationship(back_populates="tenant")


class TenantProduct(SQLModel, table=True):
    """Product scoped to a tenant."""
    __tablename__ = "tenant_products"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    name: str
    description: Optional[str] = None
    category: Optional[str] = None
    price_xmr: Decimal
    media_id: Optional[str] = None
    inventory: int = Field(default=0)
    active: bool = Field(default=True)
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    tenant: Optional[Tenant] = Relationship(back_populates="products")
    orders: list["TenantOrder"] = Relationship(back_populates="product")


class TenantOrder(SQLModel, table=True):
    """Order scoped to a tenant with multi-crypto support."""
    __tablename__ = "tenant_orders"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)
    product_id: Optional[int] = Field(foreign_key="tenant_products.id")
    customer_telegram_id: int
    quantity: int

    # Pricing
    total_xmr: Decimal
    commission_xmr: Decimal = Field(default=Decimal("0"))

    # Payment info (customer pays in any crypto)
    payment_coin: str = Field(default="xmr")  # btc, eth, sol, etc.
    payment_amount: Decimal  # Amount in payment_coin
    payment_address: str  # Deposit address (swap service or direct XMR)
    payment_id: str = Field(default_factory=lambda: secrets.token_hex(32), index=True)

    # Swap tracking (if not XMR)
    swap_id: Optional[str] = None
    swap_provider: Optional[str] = None
    swap_status: SwapState = Field(default=SwapState.WAITING)

    # Delivery
    address_encrypted: str

    # State
    state: OrderState = Field(default=OrderState.PENDING)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    paid_at: Optional[datetime] = None

    # Relationships
    tenant: Optional[Tenant] = Relationship(back_populates="orders")
    product: Optional[TenantProduct] = Relationship(back_populates="orders")


# ============================================================================
# COMMISSION TRACKING
# ============================================================================

class CommissionInvoice(SQLModel, table=True):
    """Weekly commission invoice for a tenant."""
    __tablename__ = "commission_invoices"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: str = Field(foreign_key="tenants.id", index=True)

    # Period
    period_start: date
    period_end: date

    # Sales tracking
    order_count: int
    total_sales_xmr: Decimal

    # Commission calculation
    commission_rate: Decimal
    commission_due_xmr: Decimal

    # Payment to DarkPool (XMR only)
    payment_address: Optional[str] = None
    payment_id: str = Field(default_factory=lambda: secrets.token_hex(32))

    # State
    state: InvoiceState = Field(default=InvoiceState.PENDING)
    due_date: datetime
    paid_at: Optional[datetime] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)

    # Relationships
    tenant: Optional[Tenant] = Relationship(back_populates="invoices")


# ============================================================================
# AUDIT LOG
# ============================================================================

class AuditLog(SQLModel, table=True):
    """Audit log for compliance."""
    __tablename__ = "audit_logs"

    id: Optional[int] = Field(default=None, primary_key=True)
    tenant_id: Optional[str] = Field(foreign_key="tenants.id", index=True)
    action: str
    details: Optional[str] = None  # JSON string
    ip_address: Optional[str] = None
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ============================================================================
# DATABASE WRAPPER
# ============================================================================

from sqlmodel import Session, create_engine


class MultiTenantDatabase:
    """Database wrapper for multi-tenant operations."""

    def __init__(self, database_url: str = "sqlite:///darkpool.db"):
        self.engine = create_engine(database_url)
        SQLModel.metadata.create_all(self.engine)

    def get_session(self) -> Session:
        """Get a new database session."""
        return Session(self.engine)

    # Tenant operations
    def create_tenant(
        self,
        email: str,
        password_hash: str,
        terms_version: str
    ) -> Tenant:
        """Create a new tenant."""
        with self.get_session() as session:
            tenant = Tenant(
                email=email,
                password_hash=password_hash,
                accepted_terms_at=datetime.utcnow(),
                accepted_terms_version=terms_version
            )
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
            return tenant

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        with self.get_session() as session:
            return session.get(Tenant, tenant_id)

    def get_tenant_by_email(self, email: str) -> Optional[Tenant]:
        """Get tenant by email."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(Tenant).where(Tenant.email == email)
            return session.exec(statement).first()

    def get_tenant_by_bot_username(self, username: str) -> Optional[Tenant]:
        """Get tenant by bot username."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(Tenant).where(Tenant.bot_username == username)
            return session.exec(statement).first()

    def get_active_tenants(self) -> list[Tenant]:
        """Get all tenants with active bots."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(Tenant).where(Tenant.bot_active == True)
            return list(session.exec(statement).all())

    def update_tenant(self, tenant_id: str, **kwargs) -> Optional[Tenant]:
        """Update tenant fields."""
        with self.get_session() as session:
            tenant = session.get(Tenant, tenant_id)
            if not tenant:
                return None
            for key, value in kwargs.items():
                if hasattr(tenant, key):
                    setattr(tenant, key, value)
            tenant.updated_at = datetime.utcnow()
            session.add(tenant)
            session.commit()
            session.refresh(tenant)
            return tenant

    # Product operations
    def create_product(
        self,
        tenant_id: str,
        name: str,
        price_xmr: Decimal,
        inventory: int = 0,
        description: Optional[str] = None,
        category: Optional[str] = None
    ) -> TenantProduct:
        """Create a product for a tenant."""
        with self.get_session() as session:
            product = TenantProduct(
                tenant_id=tenant_id,
                name=name,
                price_xmr=price_xmr,
                inventory=inventory,
                description=description,
                category=category
            )
            session.add(product)
            session.commit()
            session.refresh(product)
            return product

    def get_products(self, tenant_id: str, active_only: bool = True) -> list[TenantProduct]:
        """Get products for a tenant."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantProduct).where(
                TenantProduct.tenant_id == tenant_id
            )
            if active_only:
                statement = statement.where(TenantProduct.active == True)
            return list(session.exec(statement).all())

    def get_product(self, product_id: int, tenant_id: str) -> Optional[TenantProduct]:
        """Get a specific product ensuring tenant ownership."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantProduct).where(
                TenantProduct.id == product_id,
                TenantProduct.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def update_product(
        self,
        product_id: int,
        tenant_id: str,
        **kwargs
    ) -> Optional[TenantProduct]:
        """Update product fields."""
        with self.get_session() as session:
            from sqlmodel import select
            statement = select(TenantProduct).where(
                TenantProduct.id == product_id,
                TenantProduct.tenant_id == tenant_id
            )
            product = session.exec(statement).first()
            if not product:
                return None
            for key, value in kwargs.items():
                if hasattr(product, key):
                    setattr(product, key, value)
            session.add(product)
            session.commit()
            session.refresh(product)
            return product

    def decrement_inventory(
        self,
        product_id: int,
        tenant_id: str,
        quantity: int
    ) -> bool:
        """Decrement product inventory. Returns False if insufficient stock."""
        with self.get_session() as session:
            from sqlmodel import select
            statement = select(TenantProduct).where(
                TenantProduct.id == product_id,
                TenantProduct.tenant_id == tenant_id
            )
            product = session.exec(statement).first()
            if not product or product.inventory < quantity:
                return False
            product.inventory -= quantity
            session.add(product)
            session.commit()
            return True

    # Order operations
    def create_order(
        self,
        tenant_id: str,
        product_id: int,
        customer_telegram_id: int,
        quantity: int,
        total_xmr: Decimal,
        commission_xmr: Decimal,
        payment_coin: str,
        payment_amount: Decimal,
        payment_address: str,
        address_encrypted: str,
        swap_id: Optional[str] = None,
        swap_provider: Optional[str] = None
    ) -> TenantOrder:
        """Create an order."""
        with self.get_session() as session:
            order = TenantOrder(
                tenant_id=tenant_id,
                product_id=product_id,
                customer_telegram_id=customer_telegram_id,
                quantity=quantity,
                total_xmr=total_xmr,
                commission_xmr=commission_xmr,
                payment_coin=payment_coin,
                payment_amount=payment_amount,
                payment_address=payment_address,
                address_encrypted=address_encrypted,
                swap_id=swap_id,
                swap_provider=swap_provider,
                state=OrderState.SWAP_PENDING if swap_id else OrderState.PENDING
            )
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def get_order(self, order_id: int, tenant_id: str) -> Optional[TenantOrder]:
        """Get order by ID ensuring tenant ownership."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantOrder).where(
                TenantOrder.id == order_id,
                TenantOrder.tenant_id == tenant_id
            )
            return session.exec(statement).first()

    def get_order_by_payment_id(self, payment_id: str) -> Optional[TenantOrder]:
        """Get order by payment ID."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantOrder).where(
                TenantOrder.payment_id == payment_id
            )
            return session.exec(statement).first()

    def get_orders(
        self,
        tenant_id: str,
        state: Optional[OrderState] = None,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> list[TenantOrder]:
        """Get orders for a tenant with optional filters."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantOrder).where(
                TenantOrder.tenant_id == tenant_id
            )
            if state:
                statement = statement.where(TenantOrder.state == state)
            if start_date:
                statement = statement.where(
                    TenantOrder.created_at >= datetime.combine(start_date, datetime.min.time())
                )
            if end_date:
                statement = statement.where(
                    TenantOrder.created_at <= datetime.combine(end_date, datetime.max.time())
                )
            return list(session.exec(statement).all())

    def get_pending_swap_orders(self) -> list[TenantOrder]:
        """Get all orders with pending swaps."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantOrder).where(
                TenantOrder.state == OrderState.SWAP_PENDING
            )
            return list(session.exec(statement).all())

    def update_order_state(
        self,
        order_id: int,
        tenant_id: str,
        state: OrderState,
        paid_at: Optional[datetime] = None
    ) -> Optional[TenantOrder]:
        """Update order state."""
        with self.get_session() as session:
            from sqlmodel import select
            statement = select(TenantOrder).where(
                TenantOrder.id == order_id,
                TenantOrder.tenant_id == tenant_id
            )
            order = session.exec(statement).first()
            if not order:
                return None
            order.state = state
            if paid_at:
                order.paid_at = paid_at
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def update_order_swap_status(
        self,
        order_id: int,
        swap_status: SwapState
    ) -> Optional[TenantOrder]:
        """Update order swap status."""
        with self.get_session() as session:
            order = session.get(TenantOrder, order_id)
            if not order:
                return None
            order.swap_status = swap_status
            if swap_status == SwapState.COMPLETE:
                order.state = OrderState.PAID
                order.paid_at = datetime.utcnow()
            elif swap_status in [SwapState.FAILED, SwapState.EXPIRED]:
                order.state = OrderState.CANCELLED
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    # Commission operations
    def create_commission_invoice(
        self,
        tenant_id: str,
        period_start: date,
        period_end: date,
        order_count: int,
        total_sales_xmr: Decimal,
        commission_rate: Decimal,
        commission_due_xmr: Decimal,
        payment_address: str,
        due_date: datetime
    ) -> CommissionInvoice:
        """Create a commission invoice."""
        with self.get_session() as session:
            invoice = CommissionInvoice(
                tenant_id=tenant_id,
                period_start=period_start,
                period_end=period_end,
                order_count=order_count,
                total_sales_xmr=total_sales_xmr,
                commission_rate=commission_rate,
                commission_due_xmr=commission_due_xmr,
                payment_address=payment_address,
                due_date=due_date
            )
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice

    def get_pending_invoices(self, tenant_id: Optional[str] = None) -> list[CommissionInvoice]:
        """Get pending commission invoices."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(CommissionInvoice).where(
                CommissionInvoice.state == InvoiceState.PENDING
            )
            if tenant_id:
                statement = statement.where(CommissionInvoice.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def get_overdue_invoices(self, tenant_id: Optional[str] = None) -> list[CommissionInvoice]:
        """Get overdue commission invoices."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(CommissionInvoice).where(
                CommissionInvoice.state == InvoiceState.OVERDUE
            )
            if tenant_id:
                statement = statement.where(CommissionInvoice.tenant_id == tenant_id)
            return list(session.exec(statement).all())

    def mark_invoice_paid(self, invoice_id: int) -> Optional[CommissionInvoice]:
        """Mark an invoice as paid."""
        with self.get_session() as session:
            invoice = session.get(CommissionInvoice, invoice_id)
            if not invoice:
                return None
            invoice.state = InvoiceState.PAID
            invoice.paid_at = datetime.utcnow()
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice

    def mark_invoice_overdue(self, invoice_id: int) -> Optional[CommissionInvoice]:
        """Mark an invoice as overdue."""
        with self.get_session() as session:
            invoice = session.get(CommissionInvoice, invoice_id)
            if not invoice:
                return None
            invoice.state = InvoiceState.OVERDUE
            session.add(invoice)
            session.commit()
            session.refresh(invoice)
            return invoice

    # Audit log
    def log_action(
        self,
        action: str,
        tenant_id: Optional[str] = None,
        details: Optional[str] = None,
        ip_address: Optional[str] = None
    ):
        """Log an action for audit purposes."""
        with self.get_session() as session:
            log = AuditLog(
                tenant_id=tenant_id,
                action=action,
                details=details,
                ip_address=ip_address
            )
            session.add(log)
            session.commit()

    # Completed orders for commission calculation
    def get_completed_orders_for_period(
        self,
        tenant_id: str,
        start_date: date,
        end_date: date
    ) -> list[TenantOrder]:
        """Get completed orders for a period (for commission calculation)."""
        from sqlmodel import select
        with self.get_session() as session:
            statement = select(TenantOrder).where(
                TenantOrder.tenant_id == tenant_id,
                TenantOrder.state.in_([OrderState.PAID, OrderState.FULFILLED]),
                TenantOrder.paid_at >= datetime.combine(start_date, datetime.min.time()),
                TenantOrder.paid_at <= datetime.combine(end_date, datetime.max.time())
            )
            return list(session.exec(statement).all())
