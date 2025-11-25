"""FastAPI application for DarkPool dashboard."""

import os
from contextlib import asynccontextmanager
from datetime import date
from decimal import Decimal
from typing import Optional, List

from fastapi import FastAPI, Depends, HTTPException, status, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, EmailStr

from bot.api.auth import (
    create_access_token, get_current_tenant, get_tenant_id,
    TokenData, TokenResponse
)
from bot.main_multitenant import create_platform, get_platform, DarkPoolPlatform
from bot.models_multitenant import OrderState, InvoiceState


# ============================================================================
# REQUEST/RESPONSE MODELS
# ============================================================================

class RegisterRequest(BaseModel):
    """Registration request."""
    email: EmailStr
    password: str
    accept_terms: bool = False


class LoginRequest(BaseModel):
    """Login request."""
    email: EmailStr
    password: str


class ProfileUpdate(BaseModel):
    """Profile update request."""
    shop_name: Optional[str] = None
    monero_wallet_address: Optional[str] = None
    monero_view_key: Optional[str] = None


class BotConnectRequest(BaseModel):
    """Bot connection request."""
    bot_token: str


class ProductCreate(BaseModel):
    """Product creation request."""
    name: str
    price_xmr: Decimal
    inventory: int = 0
    description: Optional[str] = None
    category: Optional[str] = None


class ProductUpdate(BaseModel):
    """Product update request."""
    name: Optional[str] = None
    price_xmr: Optional[Decimal] = None
    inventory: Optional[int] = None
    description: Optional[str] = None
    category: Optional[str] = None
    active: Optional[bool] = None


class OrderCreate(BaseModel):
    """Order creation request."""
    product_id: int
    quantity: int
    delivery_address: str
    payment_coin: str = "xmr"


class TenantResponse(BaseModel):
    """Tenant profile response."""
    id: str
    email: str
    shop_name: Optional[str]
    bot_username: Optional[str]
    bot_active: bool
    monero_wallet_address: Optional[str]
    commission_rate: Decimal
    has_totp: bool

    class Config:
        from_attributes = True


class ProductResponse(BaseModel):
    """Product response."""
    id: int
    name: str
    description: Optional[str]
    category: Optional[str]
    price_xmr: Decimal
    inventory: int
    active: bool

    class Config:
        from_attributes = True


class OrderResponse(BaseModel):
    """Order response."""
    id: int
    product_id: Optional[int]
    customer_telegram_id: int
    quantity: int
    total_xmr: Decimal
    payment_coin: str
    payment_amount: Decimal
    payment_address: str
    state: str
    swap_status: Optional[str]
    created_at: str
    paid_at: Optional[str]

    class Config:
        from_attributes = True


class InvoiceResponse(BaseModel):
    """Commission invoice response."""
    id: int
    period_start: str
    period_end: str
    order_count: int
    total_sales_xmr: Decimal
    commission_rate: Decimal
    commission_due_xmr: Decimal
    payment_address: Optional[str]
    state: str
    due_date: str

    class Config:
        from_attributes = True


class StatsResponse(BaseModel):
    """Dashboard stats response."""
    total_products: int
    active_products: int
    total_orders: int
    paid_orders: int
    pending_orders: int
    total_revenue_xmr: Decimal
    total_commission_xmr: Decimal
    net_revenue_xmr: Decimal


class PaymentMethodsResponse(BaseModel):
    """Supported payment methods."""
    methods: List[str]


class PlanInfo(BaseModel):
    """Pricing plan info."""
    commission_rate: Decimal
    description: str


# ============================================================================
# LIFESPAN
# ============================================================================

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan handler."""
    # Startup
    platform = create_platform(testnet=os.getenv("TESTNET", "true").lower() == "true")
    await platform.start()
    yield
    # Shutdown
    await platform.stop()


# ============================================================================
# APPLICATION
# ============================================================================

app = FastAPI(
    title="DarkPool API",
    description="Multi-tenant Telegram shop platform API",
    version="1.0.0",
    lifespan=lifespan
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def get_services():
    """Get platform services."""
    return get_platform().get_services()


# ============================================================================
# AUTH ENDPOINTS
# ============================================================================

@app.post("/api/auth/register", response_model=TokenResponse, tags=["Auth"])
async def register(request: RegisterRequest):
    """Register a new tenant account."""
    services = get_services()
    tenant_service = services["tenant_service"]

    try:
        tenant = tenant_service.register(
            email=request.email,
            password=request.password,
            accept_terms=request.accept_terms
        )
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

    return create_access_token(tenant.id, tenant.email)


@app.post("/api/auth/login", response_model=TokenResponse, tags=["Auth"])
async def login(request: LoginRequest):
    """Login to tenant account."""
    services = get_services()
    tenant_service = services["tenant_service"]

    tenant = tenant_service.authenticate(request.email, request.password)
    if not tenant:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )

    return create_access_token(tenant.id, tenant.email)


# ============================================================================
# PROFILE ENDPOINTS
# ============================================================================

@app.get("/api/me", response_model=TenantResponse, tags=["Profile"])
async def get_profile(tenant_id: str = Depends(get_tenant_id)):
    """Get current tenant profile."""
    services = get_services()
    tenant = services["tenant_service"].get_tenant(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantResponse(
        id=tenant.id,
        email=tenant.email,
        shop_name=tenant.shop_name,
        bot_username=tenant.bot_username,
        bot_active=tenant.bot_active,
        monero_wallet_address=tenant.monero_wallet_address,
        commission_rate=tenant.commission_rate,
        has_totp=tenant.totp_secret is not None
    )


@app.put("/api/me", response_model=TenantResponse, tags=["Profile"])
async def update_profile(
    request: ProfileUpdate,
    tenant_id: str = Depends(get_tenant_id)
):
    """Update tenant profile."""
    services = get_services()
    tenant = services["tenant_service"].update_profile(
        tenant_id,
        shop_name=request.shop_name,
        monero_wallet_address=request.monero_wallet_address,
        monero_view_key=request.monero_view_key
    )
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantResponse(
        id=tenant.id,
        email=tenant.email,
        shop_name=tenant.shop_name,
        bot_username=tenant.bot_username,
        bot_active=tenant.bot_active,
        monero_wallet_address=tenant.monero_wallet_address,
        commission_rate=tenant.commission_rate,
        has_totp=tenant.totp_secret is not None
    )


@app.get("/api/me/stats", response_model=StatsResponse, tags=["Profile"])
async def get_stats(tenant_id: str = Depends(get_tenant_id)):
    """Get dashboard statistics."""
    services = get_services()
    stats = services["tenant_service"].get_tenant_stats(tenant_id)
    return StatsResponse(**stats)


# ============================================================================
# BOT ENDPOINTS
# ============================================================================

@app.post("/api/me/bot", response_model=TenantResponse, tags=["Bot"])
async def connect_bot(
    request: BotConnectRequest,
    tenant_id: str = Depends(get_tenant_id)
):
    """Connect a Telegram bot."""
    services = get_services()
    platform = get_platform()

    tenant = services["tenant_service"].connect_bot(
        tenant_id,
        request.bot_token,
        platform.platform_encryption_key
    )
    if not tenant:
        raise HTTPException(status_code=400, detail="Failed to connect bot")

    # Start the bot
    await services["bot_manager"].start_bot(tenant_id)

    return TenantResponse(
        id=tenant.id,
        email=tenant.email,
        shop_name=tenant.shop_name,
        bot_username=tenant.bot_username,
        bot_active=tenant.bot_active,
        monero_wallet_address=tenant.monero_wallet_address,
        commission_rate=tenant.commission_rate,
        has_totp=tenant.totp_secret is not None
    )


@app.delete("/api/me/bot", response_model=TenantResponse, tags=["Bot"])
async def disconnect_bot(tenant_id: str = Depends(get_tenant_id)):
    """Disconnect the Telegram bot."""
    services = get_services()

    # Stop the bot first
    await services["bot_manager"].stop_bot(tenant_id)

    tenant = services["tenant_service"].disconnect_bot(tenant_id)
    if not tenant:
        raise HTTPException(status_code=404, detail="Tenant not found")

    return TenantResponse(
        id=tenant.id,
        email=tenant.email,
        shop_name=tenant.shop_name,
        bot_username=tenant.bot_username,
        bot_active=tenant.bot_active,
        monero_wallet_address=tenant.monero_wallet_address,
        commission_rate=tenant.commission_rate,
        has_totp=tenant.totp_secret is not None
    )


# ============================================================================
# PRODUCT ENDPOINTS
# ============================================================================

@app.get("/api/products", response_model=List[ProductResponse], tags=["Products"])
async def list_products(
    active_only: bool = True,
    tenant_id: str = Depends(get_tenant_id)
):
    """List all products."""
    services = get_services()
    products = services["db"].get_products(tenant_id, active_only=active_only)
    return [ProductResponse(
        id=p.id,
        name=p.name,
        description=p.description,
        category=p.category,
        price_xmr=p.price_xmr,
        inventory=p.inventory,
        active=p.active
    ) for p in products]


@app.post("/api/products", response_model=ProductResponse, tags=["Products"])
async def create_product(
    request: ProductCreate,
    tenant_id: str = Depends(get_tenant_id)
):
    """Create a new product."""
    services = get_services()
    product = services["db"].create_product(
        tenant_id=tenant_id,
        name=request.name,
        price_xmr=request.price_xmr,
        inventory=request.inventory,
        description=request.description,
        category=request.category
    )
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        category=product.category,
        price_xmr=product.price_xmr,
        inventory=product.inventory,
        active=product.active
    )


@app.get("/api/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def get_product(
    product_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a specific product."""
    services = get_services()
    product = services["db"].get_product(product_id, tenant_id)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        category=product.category,
        price_xmr=product.price_xmr,
        inventory=product.inventory,
        active=product.active
    )


@app.put("/api/products/{product_id}", response_model=ProductResponse, tags=["Products"])
async def update_product(
    product_id: int,
    request: ProductUpdate,
    tenant_id: str = Depends(get_tenant_id)
):
    """Update a product."""
    services = get_services()
    updates = request.dict(exclude_unset=True)
    product = services["db"].update_product(product_id, tenant_id, **updates)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return ProductResponse(
        id=product.id,
        name=product.name,
        description=product.description,
        category=product.category,
        price_xmr=product.price_xmr,
        inventory=product.inventory,
        active=product.active
    )


@app.delete("/api/products/{product_id}", tags=["Products"])
async def delete_product(
    product_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Deactivate a product."""
    services = get_services()
    product = services["db"].update_product(product_id, tenant_id, active=False)
    if not product:
        raise HTTPException(status_code=404, detail="Product not found")
    return {"message": "Product deactivated"}


# ============================================================================
# ORDER ENDPOINTS
# ============================================================================

@app.get("/api/orders", response_model=List[OrderResponse], tags=["Orders"])
async def list_orders(
    state: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id)
):
    """List all orders."""
    services = get_services()
    order_state = OrderState(state) if state else None
    orders = services["order_service"].get_orders(tenant_id, state=order_state)

    return [OrderResponse(
        id=o.id,
        product_id=o.product_id,
        customer_telegram_id=o.customer_telegram_id,
        quantity=o.quantity,
        total_xmr=o.total_xmr,
        payment_coin=o.payment_coin,
        payment_amount=o.payment_amount,
        payment_address=o.payment_address,
        state=o.state if isinstance(o.state, str) else o.state.value,
        swap_status=o.swap_status if isinstance(o.swap_status, str) else (o.swap_status.value if o.swap_status else None),
        created_at=o.created_at.isoformat(),
        paid_at=o.paid_at.isoformat() if o.paid_at else None
    ) for o in orders]


@app.get("/api/orders/{order_id}", response_model=OrderResponse, tags=["Orders"])
async def get_order(
    order_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a specific order."""
    services = get_services()
    order = services["order_service"].get_order(order_id, tenant_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")

    return OrderResponse(
        id=order.id,
        product_id=order.product_id,
        customer_telegram_id=order.customer_telegram_id,
        quantity=order.quantity,
        total_xmr=order.total_xmr,
        payment_coin=order.payment_coin,
        payment_amount=order.payment_amount,
        payment_address=order.payment_address,
        state=order.state if isinstance(order.state, str) else order.state.value,
        swap_status=order.swap_status if isinstance(order.swap_status, str) else (order.swap_status.value if order.swap_status else None),
        created_at=order.created_at.isoformat(),
        paid_at=order.paid_at.isoformat() if order.paid_at else None
    )


@app.post("/api/orders/{order_id}/fulfill", tags=["Orders"])
async def fulfill_order(
    order_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Mark an order as fulfilled."""
    services = get_services()
    order = services["order_service"].mark_order_fulfilled(order_id, tenant_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": "Order fulfilled"}


@app.post("/api/orders/{order_id}/cancel", tags=["Orders"])
async def cancel_order(
    order_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Cancel an order."""
    services = get_services()
    order = services["order_service"].cancel_order(order_id, tenant_id)
    if not order:
        raise HTTPException(status_code=404, detail="Order not found")
    return {"message": "Order cancelled"}


# ============================================================================
# BILLING ENDPOINTS
# ============================================================================

@app.get("/api/billing/plan", response_model=PlanInfo, tags=["Billing"])
async def get_plan(tenant_id: str = Depends(get_tenant_id)):
    """Get current plan info."""
    services = get_services()
    tenant = services["tenant_service"].get_tenant(tenant_id)

    return PlanInfo(
        commission_rate=tenant.commission_rate,
        description="5% commission on all transactions"
    )


@app.get("/api/billing/invoices", response_model=List[InvoiceResponse], tags=["Billing"])
async def list_invoices(
    state: Optional[str] = None,
    tenant_id: str = Depends(get_tenant_id)
):
    """List commission invoices."""
    services = get_services()
    invoice_state = InvoiceState(state) if state else None
    invoices = services["commission_service"].get_tenant_invoices(
        tenant_id, state=invoice_state
    )

    return [InvoiceResponse(
        id=i.id,
        period_start=i.period_start.isoformat(),
        period_end=i.period_end.isoformat(),
        order_count=i.order_count,
        total_sales_xmr=i.total_sales_xmr,
        commission_rate=i.commission_rate,
        commission_due_xmr=i.commission_due_xmr,
        payment_address=i.payment_address,
        state=i.state if isinstance(i.state, str) else i.state.value,
        due_date=i.due_date.isoformat()
    ) for i in invoices]


@app.get("/api/billing/invoices/{invoice_id}", response_model=InvoiceResponse, tags=["Billing"])
async def get_invoice(
    invoice_id: int,
    tenant_id: str = Depends(get_tenant_id)
):
    """Get a specific invoice with payment address."""
    services = get_services()
    invoice = services["commission_service"].get_invoice(invoice_id)

    if not invoice or invoice.tenant_id != tenant_id:
        raise HTTPException(status_code=404, detail="Invoice not found")

    return InvoiceResponse(
        id=invoice.id,
        period_start=invoice.period_start.isoformat(),
        period_end=invoice.period_end.isoformat(),
        order_count=invoice.order_count,
        total_sales_xmr=invoice.total_sales_xmr,
        commission_rate=invoice.commission_rate,
        commission_due_xmr=invoice.commission_due_xmr,
        payment_address=invoice.payment_address,
        state=invoice.state if isinstance(invoice.state, str) else invoice.state.value,
        due_date=invoice.due_date.isoformat()
    )


# ============================================================================
# PAYMENT METHODS
# ============================================================================

@app.get("/api/payment-methods", response_model=PaymentMethodsResponse, tags=["Payments"])
async def get_payment_methods():
    """Get supported payment methods."""
    services = get_services()
    methods = await services["swap_service"].get_supported_coins()
    return PaymentMethodsResponse(methods=[m.upper() for m in methods])


# ============================================================================
# HEALTH CHECK
# ============================================================================

@app.get("/health", tags=["Health"])
async def health_check():
    """Health check endpoint."""
    return {"status": "healthy"}


@app.get("/ready", tags=["Health"])
async def ready_check():
    """Readiness check endpoint."""
    try:
        platform = get_platform()
        bot_health = await platform.bot_manager.health_check()
        return {
            "status": "ready",
            "bots": bot_health
        }
    except Exception as e:
        raise HTTPException(status_code=503, detail=str(e))
