"""Tests for FastAPI endpoints in bot/api/main.py."""

import sys
import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from decimal import Decimal
from datetime import date, datetime


class MockTenant:
    """Mock tenant object."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", "tenant-123")
        self.email = kwargs.get("email", "test@example.com")
        self.shop_name = kwargs.get("shop_name", "Test Shop")
        self.bot_username = kwargs.get("bot_username", "test_bot")
        self.bot_active = kwargs.get("bot_active", True)
        self.monero_wallet_address = kwargs.get("monero_wallet_address", "4TestWallet")
        self.commission_rate = kwargs.get("commission_rate", Decimal("0.05"))
        self.totp_secret = kwargs.get("totp_secret", None)


class MockProduct:
    """Mock product object."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.name = kwargs.get("name", "Test Product")
        self.description = kwargs.get("description", "A test product")
        self.category = kwargs.get("category", "test")
        self.price_xmr = kwargs.get("price_xmr", Decimal("1.5"))
        self.inventory = kwargs.get("inventory", 10)
        self.active = kwargs.get("active", True)


class MockOrder:
    """Mock order object."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.product_id = kwargs.get("product_id", 1)
        self.customer_telegram_id = kwargs.get("customer_telegram_id", 123456)
        self.quantity = kwargs.get("quantity", 1)
        self.total_xmr = kwargs.get("total_xmr", Decimal("1.5"))
        self.payment_coin = kwargs.get("payment_coin", "xmr")
        self.payment_amount = kwargs.get("payment_amount", Decimal("1.5"))
        self.payment_address = kwargs.get("payment_address", "4TestAddress")
        self.state = kwargs.get("state", "pending")
        self.swap_status = kwargs.get("swap_status", None)
        self.created_at = kwargs.get("created_at", datetime.now())
        self.paid_at = kwargs.get("paid_at", None)


class MockInvoice:
    """Mock invoice object."""
    def __init__(self, **kwargs):
        self.id = kwargs.get("id", 1)
        self.tenant_id = kwargs.get("tenant_id", "tenant-123")
        self.period_start = kwargs.get("period_start", date.today())
        self.period_end = kwargs.get("period_end", date.today())
        self.order_count = kwargs.get("order_count", 5)
        self.total_sales_xmr = kwargs.get("total_sales_xmr", Decimal("10.0"))
        self.commission_rate = kwargs.get("commission_rate", Decimal("0.05"))
        self.commission_due_xmr = kwargs.get("commission_due_xmr", Decimal("0.5"))
        self.payment_address = kwargs.get("payment_address", "4InvoiceAddress")
        self.state = kwargs.get("state", "pending")
        self.due_date = kwargs.get("due_date", date.today())


@pytest.fixture
def mock_services():
    """Create mock services."""
    services = {
        "db": MagicMock(),
        "tenant_service": MagicMock(),
        "order_service": MagicMock(),
        "commission_service": MagicMock(),
        "bot_manager": MagicMock(),
        "swap_service": MagicMock(),
    }

    services["bot_manager"].start_bot = AsyncMock()
    services["bot_manager"].stop_bot = AsyncMock()
    services["swap_service"].get_supported_coins = AsyncMock(return_value=["xmr", "btc", "eth"])

    return services


@pytest.fixture
def mock_platform():
    """Create mock platform."""
    platform = MagicMock()
    platform.platform_encryption_key = "test_key"
    platform.bot_manager = MagicMock()
    platform.bot_manager.health_check = AsyncMock(return_value={"bot1": "healthy"})
    platform.start = AsyncMock()
    platform.stop = AsyncMock()
    return platform


@pytest.fixture
def client(mock_platform, mock_services):
    """Create test client."""
    mock_platform.get_services.return_value = mock_services

    with patch("bot.api.main.create_platform") as mock_create:
        with patch("bot.api.main.get_platform") as mock_get:
            with patch("bot.api.main.get_services") as mock_get_services:
                mock_create.return_value = mock_platform
                mock_get.return_value = mock_platform
                mock_get_services.return_value = mock_services

                from fastapi.testclient import TestClient
                from bot.api.main import app

                with TestClient(app, raise_server_exceptions=False) as test_client:
                    yield test_client, mock_services


@pytest.fixture
def auth_headers():
    """Create auth headers with valid token."""
    from bot.api.auth import create_access_token
    token = create_access_token("tenant-123", "test@test.com")
    return {"Authorization": f"Bearer {token.access_token}"}


class TestHealthEndpoints:
    """Test health check endpoints."""

    def test_health_check(self, client):
        """Test health endpoint returns healthy."""
        test_client, _ = client
        response = test_client.get("/health")
        assert response.status_code == 200
        assert response.json() == {"status": "healthy"}

    def test_ready_check(self, client):
        """Test ready endpoint."""
        test_client, _ = client
        response = test_client.get("/ready")
        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "ready"


class TestAuthEndpoints:
    """Test authentication endpoints."""

    def test_register_success(self, client):
        """Test successful registration."""
        test_client, mock_services = client
        mock_tenant = MockTenant(id="new-tenant", email="new@test.com")
        mock_services["tenant_service"].register.return_value = mock_tenant

        response = test_client.post("/api/auth/register", json={
            "email": "new@test.com",
            "password": "securepass",
            "accept_terms": True
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data
        assert data["token_type"] == "bearer"

    def test_register_validation_error(self, client):
        """Test registration with validation error."""
        test_client, mock_services = client
        mock_services["tenant_service"].register.side_effect = ValueError("Email already exists")

        response = test_client.post("/api/auth/register", json={
            "email": "existing@test.com",
            "password": "pass",
            "accept_terms": True
        })

        assert response.status_code == 400
        assert "Email already exists" in response.json()["detail"]

    def test_login_success(self, client):
        """Test successful login."""
        test_client, mock_services = client
        mock_tenant = MockTenant(id="tenant-123", email="test@test.com")
        mock_services["tenant_service"].authenticate.return_value = mock_tenant

        response = test_client.post("/api/auth/login", json={
            "email": "test@test.com",
            "password": "password"
        })

        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

    def test_login_invalid_credentials(self, client):
        """Test login with invalid credentials."""
        test_client, mock_services = client
        mock_services["tenant_service"].authenticate.return_value = None

        response = test_client.post("/api/auth/login", json={
            "email": "wrong@test.com",
            "password": "wrongpass"
        })

        assert response.status_code == 401


class TestProfileEndpoints:
    """Test profile endpoints."""

    def test_get_profile(self, client, auth_headers):
        """Test getting profile."""
        test_client, mock_services = client
        mock_tenant = MockTenant()
        mock_services["tenant_service"].get_tenant.return_value = mock_tenant

        response = test_client.get("/api/me", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "tenant-123"

    def test_get_profile_not_found(self, client, auth_headers):
        """Test getting profile when tenant not found."""
        test_client, mock_services = client
        mock_services["tenant_service"].get_tenant.return_value = None

        response = test_client.get("/api/me", headers=auth_headers)

        assert response.status_code == 404

    def test_update_profile(self, client, auth_headers):
        """Test updating profile."""
        test_client, mock_services = client
        mock_tenant = MockTenant(shop_name="Updated Shop")
        mock_services["tenant_service"].update_profile.return_value = mock_tenant

        response = test_client.put("/api/me", headers=auth_headers, json={
            "shop_name": "Updated Shop"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["shop_name"] == "Updated Shop"

    def test_update_profile_not_found(self, client, auth_headers):
        """Test updating profile when tenant not found."""
        test_client, mock_services = client
        mock_services["tenant_service"].update_profile.return_value = None

        response = test_client.put("/api/me", headers=auth_headers, json={
            "shop_name": "Test"
        })

        assert response.status_code == 404

    def test_get_stats(self, client, auth_headers):
        """Test getting stats."""
        test_client, mock_services = client
        mock_services["tenant_service"].get_tenant_stats.return_value = {
            "total_products": 10,
            "active_products": 8,
            "total_orders": 50,
            "paid_orders": 45,
            "pending_orders": 5,
            "total_revenue_xmr": Decimal("100.0"),
            "total_commission_xmr": Decimal("5.0"),
            "net_revenue_xmr": Decimal("95.0")
        }

        response = test_client.get("/api/me/stats", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["total_products"] == 10


class TestBotEndpoints:
    """Test bot management endpoints."""

    def test_connect_bot(self, client, auth_headers):
        """Test connecting a bot."""
        test_client, mock_services = client
        mock_tenant = MockTenant(bot_active=True)
        mock_services["tenant_service"].connect_bot.return_value = mock_tenant

        response = test_client.post("/api/me/bot", headers=auth_headers, json={
            "bot_token": "123456:ABC-DEF"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["bot_active"] is True

    def test_connect_bot_failure(self, client, auth_headers):
        """Test bot connection failure."""
        test_client, mock_services = client
        mock_services["tenant_service"].connect_bot.return_value = None

        response = test_client.post("/api/me/bot", headers=auth_headers, json={
            "bot_token": "invalid"
        })

        assert response.status_code == 400

    def test_disconnect_bot(self, client, auth_headers):
        """Test disconnecting a bot."""
        test_client, mock_services = client
        mock_tenant = MockTenant(bot_active=False, bot_username=None)
        mock_services["tenant_service"].disconnect_bot.return_value = mock_tenant

        response = test_client.delete("/api/me/bot", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["bot_active"] is False

    def test_disconnect_bot_not_found(self, client, auth_headers):
        """Test disconnecting bot when tenant not found."""
        test_client, mock_services = client
        mock_services["tenant_service"].disconnect_bot.return_value = None

        response = test_client.delete("/api/me/bot", headers=auth_headers)

        assert response.status_code == 404


class TestProductEndpoints:
    """Test product management endpoints."""

    def test_list_products(self, client, auth_headers):
        """Test listing products."""
        test_client, mock_services = client
        mock_services["db"].get_products.return_value = [
            MockProduct(id=1, name="Product 1"),
            MockProduct(id=2, name="Product 2")
        ]

        response = test_client.get("/api/products", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_create_product(self, client, auth_headers):
        """Test creating a product."""
        test_client, mock_services = client
        mock_product = MockProduct(name="New Product")
        mock_services["db"].create_product.return_value = mock_product

        response = test_client.post("/api/products", headers=auth_headers, json={
            "name": "New Product",
            "price_xmr": "1.5",
            "inventory": 10
        })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "New Product"

    def test_get_product(self, client, auth_headers):
        """Test getting a product."""
        test_client, mock_services = client
        mock_product = MockProduct(id=1)
        mock_services["db"].get_product.return_value = mock_product

        response = test_client.get("/api/products/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    def test_get_product_not_found(self, client, auth_headers):
        """Test getting non-existent product."""
        test_client, mock_services = client
        mock_services["db"].get_product.return_value = None

        response = test_client.get("/api/products/999", headers=auth_headers)

        assert response.status_code == 404

    def test_update_product(self, client, auth_headers):
        """Test updating a product."""
        test_client, mock_services = client
        mock_product = MockProduct(name="Updated")
        mock_services["db"].update_product.return_value = mock_product

        response = test_client.put("/api/products/1", headers=auth_headers, json={
            "name": "Updated"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated"

    def test_update_product_not_found(self, client, auth_headers):
        """Test updating non-existent product."""
        test_client, mock_services = client
        mock_services["db"].update_product.return_value = None

        response = test_client.put("/api/products/999", headers=auth_headers, json={
            "name": "Test"
        })

        assert response.status_code == 404

    def test_delete_product(self, client, auth_headers):
        """Test deleting a product."""
        test_client, mock_services = client
        mock_product = MockProduct(active=False)
        mock_services["db"].update_product.return_value = mock_product

        response = test_client.delete("/api/products/1", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "Product deactivated"

    def test_delete_product_not_found(self, client, auth_headers):
        """Test deleting non-existent product."""
        test_client, mock_services = client
        mock_services["db"].update_product.return_value = None

        response = test_client.delete("/api/products/999", headers=auth_headers)

        assert response.status_code == 404


class TestOrderEndpoints:
    """Test order management endpoints."""

    def test_list_orders(self, client, auth_headers):
        """Test listing orders."""
        test_client, mock_services = client
        mock_services["order_service"].get_orders.return_value = [
            MockOrder(id=1),
            MockOrder(id=2)
        ]

        response = test_client.get("/api/orders", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_order(self, client, auth_headers):
        """Test getting an order."""
        test_client, mock_services = client
        mock_order = MockOrder(id=1)
        mock_services["order_service"].get_order.return_value = mock_order

        response = test_client.get("/api/orders/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    def test_get_order_not_found(self, client, auth_headers):
        """Test getting non-existent order."""
        test_client, mock_services = client
        mock_services["order_service"].get_order.return_value = None

        response = test_client.get("/api/orders/999", headers=auth_headers)

        assert response.status_code == 404

    def test_fulfill_order(self, client, auth_headers):
        """Test fulfilling an order."""
        test_client, mock_services = client
        mock_order = MockOrder(state="fulfilled")
        mock_services["order_service"].mark_order_fulfilled.return_value = mock_order

        response = test_client.post("/api/orders/1/fulfill", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "Order fulfilled"

    def test_fulfill_order_not_found(self, client, auth_headers):
        """Test fulfilling non-existent order."""
        test_client, mock_services = client
        mock_services["order_service"].mark_order_fulfilled.return_value = None

        response = test_client.post("/api/orders/999/fulfill", headers=auth_headers)

        assert response.status_code == 404

    def test_cancel_order(self, client, auth_headers):
        """Test cancelling an order."""
        test_client, mock_services = client
        mock_order = MockOrder(state="cancelled")
        mock_services["order_service"].cancel_order.return_value = mock_order

        response = test_client.post("/api/orders/1/cancel", headers=auth_headers)

        assert response.status_code == 200
        assert response.json()["message"] == "Order cancelled"

    def test_cancel_order_not_found(self, client, auth_headers):
        """Test cancelling non-existent order."""
        test_client, mock_services = client
        mock_services["order_service"].cancel_order.return_value = None

        response = test_client.post("/api/orders/999/cancel", headers=auth_headers)

        assert response.status_code == 404


class TestBillingEndpoints:
    """Test billing endpoints."""

    def test_get_plan(self, client, auth_headers):
        """Test getting plan info."""
        test_client, mock_services = client
        mock_tenant = MockTenant()
        mock_services["tenant_service"].get_tenant.return_value = mock_tenant

        response = test_client.get("/api/billing/plan", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert "commission_rate" in data

    def test_list_invoices(self, client, auth_headers):
        """Test listing invoices."""
        test_client, mock_services = client
        mock_services["commission_service"].get_tenant_invoices.return_value = [
            MockInvoice(id=1),
            MockInvoice(id=2)
        ]

        response = test_client.get("/api/billing/invoices", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data) == 2

    def test_get_invoice(self, client, auth_headers):
        """Test getting an invoice."""
        test_client, mock_services = client
        mock_invoice = MockInvoice(id=1, tenant_id="tenant-123")
        mock_services["commission_service"].get_invoice.return_value = mock_invoice

        response = test_client.get("/api/billing/invoices/1", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == 1

    def test_get_invoice_not_found(self, client, auth_headers):
        """Test getting non-existent invoice."""
        test_client, mock_services = client
        mock_services["commission_service"].get_invoice.return_value = None

        response = test_client.get("/api/billing/invoices/999", headers=auth_headers)

        assert response.status_code == 404

    def test_get_invoice_wrong_tenant(self, client, auth_headers):
        """Test getting invoice belonging to different tenant."""
        test_client, mock_services = client
        mock_invoice = MockInvoice(id=1, tenant_id="other-tenant")
        mock_services["commission_service"].get_invoice.return_value = mock_invoice

        response = test_client.get("/api/billing/invoices/1", headers=auth_headers)

        assert response.status_code == 404


class TestPaymentMethods:
    """Test payment methods endpoint."""

    def test_get_payment_methods(self, client):
        """Test getting payment methods."""
        test_client, _ = client
        response = test_client.get("/api/payment-methods")

        assert response.status_code == 200
        data = response.json()
        assert "methods" in data
        assert "XMR" in data["methods"]


class TestModels:
    """Test request/response models."""

    def test_product_create(self):
        """Test ProductCreate model."""
        from bot.api.main import ProductCreate

        product = ProductCreate(
            name="Test",
            price_xmr=Decimal("1.5"),
            inventory=10
        )

        assert product.name == "Test"
        assert product.inventory == 10

    def test_product_update(self):
        """Test ProductUpdate model."""
        from bot.api.main import ProductUpdate

        update = ProductUpdate(name="Updated")
        assert update.name == "Updated"
        assert update.price_xmr is None

    def test_order_create(self):
        """Test OrderCreate model."""
        from bot.api.main import OrderCreate

        order = OrderCreate(
            product_id=1,
            quantity=2,
            delivery_address="123 Test St"
        )

        assert order.product_id == 1
        assert order.payment_coin == "xmr"  # Default

    def test_profile_update(self):
        """Test ProfileUpdate model."""
        from bot.api.main import ProfileUpdate

        profile = ProfileUpdate(shop_name="New Shop")
        assert profile.shop_name == "New Shop"
        assert profile.monero_wallet_address is None

    def test_tenant_response(self):
        """Test TenantResponse model."""
        from bot.api.main import TenantResponse

        response = TenantResponse(
            id="test",
            email="test@test.com",
            shop_name="Shop",
            bot_username=None,
            bot_active=False,
            monero_wallet_address=None,
            commission_rate=Decimal("0.05"),
            has_totp=False
        )

        assert response.id == "test"

    def test_stats_response(self):
        """Test StatsResponse model."""
        from bot.api.main import StatsResponse

        stats = StatsResponse(
            total_products=10,
            active_products=8,
            total_orders=50,
            paid_orders=45,
            pending_orders=5,
            total_revenue_xmr=Decimal("100.0"),
            total_commission_xmr=Decimal("5.0"),
            net_revenue_xmr=Decimal("95.0")
        )

        assert stats.total_products == 10

    def test_plan_info(self):
        """Test PlanInfo model."""
        from bot.api.main import PlanInfo

        plan = PlanInfo(
            commission_rate=Decimal("0.05"),
            description="5% commission"
        )

        assert plan.commission_rate == Decimal("0.05")

    def test_register_request(self):
        """Test RegisterRequest model."""
        from bot.api.main import RegisterRequest

        req = RegisterRequest(
            email="test@test.com",
            password="pass123",
            accept_terms=True
        )

        assert req.email == "test@test.com"

    def test_login_request(self):
        """Test LoginRequest model."""
        from bot.api.main import LoginRequest

        req = LoginRequest(
            email="test@test.com",
            password="pass123"
        )

        assert req.email == "test@test.com"

    def test_bot_connect_request(self):
        """Test BotConnectRequest model."""
        from bot.api.main import BotConnectRequest

        req = BotConnectRequest(bot_token="123456:ABC")
        assert req.bot_token == "123456:ABC"

    def test_product_response(self):
        """Test ProductResponse model."""
        from bot.api.main import ProductResponse

        resp = ProductResponse(
            id=1,
            name="Test",
            description="Desc",
            category="cat",
            price_xmr=Decimal("1.5"),
            inventory=10,
            active=True
        )

        assert resp.id == 1

    def test_order_response(self):
        """Test OrderResponse model."""
        from bot.api.main import OrderResponse

        resp = OrderResponse(
            id=1,
            product_id=1,
            customer_telegram_id=123,
            quantity=2,
            total_xmr=Decimal("3.0"),
            payment_coin="xmr",
            payment_amount=Decimal("3.0"),
            payment_address="4Test",
            state="pending",
            swap_status=None,
            created_at="2025-01-01T00:00:00",
            paid_at=None
        )

        assert resp.id == 1

    def test_invoice_response(self):
        """Test InvoiceResponse model."""
        from bot.api.main import InvoiceResponse

        resp = InvoiceResponse(
            id=1,
            period_start="2025-01-01",
            period_end="2025-01-31",
            order_count=10,
            total_sales_xmr=Decimal("50.0"),
            commission_rate=Decimal("0.05"),
            commission_due_xmr=Decimal("2.5"),
            payment_address="4Test",
            state="pending",
            due_date="2025-02-15"
        )

        assert resp.id == 1

    def test_payment_methods_response(self):
        """Test PaymentMethodsResponse model."""
        from bot.api.main import PaymentMethodsResponse

        resp = PaymentMethodsResponse(methods=["XMR", "BTC"])
        assert "XMR" in resp.methods
