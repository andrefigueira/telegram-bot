"""
E2E Tests: Multitenant API Flow

Tests the complete tenant journey through the REST API.
"""

import pytest
import tempfile
import os
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import MagicMock, AsyncMock, patch

from fastapi.testclient import TestClient


class TestTenantRegistrationFlow:
    """
    E2E Test: Tenant registration and authentication.

    Flow tested:
    1. Register new tenant
    2. Login and get JWT token
    3. Access protected endpoints
    4. Update profile
    """

    @pytest.fixture
    def mock_platform(self):
        """Create mock platform."""
        platform = MagicMock()
        platform.platform_encryption_key = "test_key"
        platform.bot_manager = MagicMock()
        platform.bot_manager.health_check = AsyncMock(return_value={})
        platform.start = AsyncMock()
        platform.stop = AsyncMock()
        return platform

    @pytest.fixture
    def mock_services(self):
        """Create mock services with actual database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        from bot.models_multitenant import MultiTenantDatabase
        db = MultiTenantDatabase(f"sqlite:///{path}")

        from bot.services.tenant import TenantService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        from bot.services.crypto_swap import CryptoSwapService

        swap_service = CryptoSwapService(testnet=True)
        tenant_service = TenantService(db)
        order_service = MultiCryptoOrderService(db, swap_service)
        commission_service = CommissionService(db, "4PlatformAddress")

        services = {
            "db": db,
            "tenant_service": tenant_service,
            "order_service": order_service,
            "commission_service": commission_service,
            "bot_manager": MagicMock(),
            "swap_service": swap_service,
            "_db_path": path  # For cleanup
        }

        services["bot_manager"].start_bot = AsyncMock()
        services["bot_manager"].stop_bot = AsyncMock()

        return services

    @pytest.fixture
    def client(self, mock_platform, mock_services):
        """Create test client."""
        mock_platform.get_services.return_value = mock_services

        with patch("bot.api.main.create_platform") as mock_create:
            with patch("bot.api.main.get_platform") as mock_get:
                with patch("bot.api.main.get_services") as mock_get_services:
                    mock_create.return_value = mock_platform
                    mock_get.return_value = mock_platform
                    mock_get_services.return_value = mock_services

                    from bot.api.main import app
                    with TestClient(app, raise_server_exceptions=False) as test_client:
                        yield test_client, mock_services

        # Cleanup
        if "_db_path" in mock_services:
            try:
                os.unlink(mock_services["_db_path"])
            except:
                pass

    def test_complete_registration_flow(self, client):
        """Test complete tenant registration and profile setup."""
        test_client, services = client

        # Step 1: Register
        response = test_client.post("/api/auth/register", json={
            "email": "newshop@example.com",
            "password": "securepass123",
            "accept_terms": True
        })
        assert response.status_code == 200
        data = response.json()
        assert "access_token" in data

        token = data["access_token"]
        headers = {"Authorization": f"Bearer {token}"}

        # Step 2: Get profile
        response = test_client.get("/api/me", headers=headers)
        assert response.status_code == 200
        profile = response.json()
        assert profile["email"] == "newshop@example.com"

        # Step 3: Update profile
        response = test_client.put("/api/me", headers=headers, json={
            "shop_name": "My Awesome Shop",
            "monero_wallet_address": "4" + "A" * 94
        })
        assert response.status_code == 200
        updated = response.json()
        assert updated["shop_name"] == "My Awesome Shop"

    def test_login_flow(self, client):
        """Test login with existing account."""
        test_client, services = client

        # Register first
        test_client.post("/api/auth/register", json={
            "email": "logintest@example.com",
            "password": "testpass",
            "accept_terms": True
        })

        # Login
        response = test_client.post("/api/auth/login", json={
            "email": "logintest@example.com",
            "password": "testpass"
        })
        assert response.status_code == 200
        assert "access_token" in response.json()

    def test_invalid_login_rejected(self, client):
        """Test that invalid credentials are rejected."""
        test_client, _ = client

        response = test_client.post("/api/auth/login", json={
            "email": "nonexistent@example.com",
            "password": "wrongpass"
        })
        assert response.status_code == 401

    def test_protected_endpoint_without_auth(self, client):
        """Test that protected endpoints require authentication."""
        test_client, _ = client

        response = test_client.get("/api/me")
        assert response.status_code in [401, 403]


class TestProductAPIFlow:
    """
    E2E Test: Product management via API.

    Flow tested:
    1. Create products
    2. List products
    3. Update products
    4. Delete products
    """

    @pytest.fixture
    def authenticated_client(self):
        """Create authenticated client with tenant."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        from bot.models_multitenant import MultiTenantDatabase
        db = MultiTenantDatabase(f"sqlite:///{path}")

        # Create tenant
        tenant = db.create_tenant("shop@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94,
            shop_name="Test Shop"
        )

        mock_platform = MagicMock()
        mock_platform.platform_encryption_key = "test_key"
        mock_platform.start = AsyncMock()
        mock_platform.stop = AsyncMock()
        mock_platform.bot_manager = MagicMock()
        mock_platform.bot_manager.health_check = AsyncMock(return_value={})

        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        from bot.services.tenant import TenantService

        services = {
            "db": db,
            "tenant_service": TenantService(db),
            "order_service": MultiCryptoOrderService(db, CryptoSwapService(testnet=True)),
            "commission_service": CommissionService(db, "4Platform"),
            "bot_manager": MagicMock(),
            "swap_service": CryptoSwapService(testnet=True),
        }
        services["bot_manager"].start_bot = AsyncMock()
        services["bot_manager"].stop_bot = AsyncMock()

        mock_platform.get_services.return_value = services

        with patch("bot.api.main.create_platform") as mock_create:
            with patch("bot.api.main.get_platform") as mock_get:
                with patch("bot.api.main.get_services") as mock_get_services:
                    mock_create.return_value = mock_platform
                    mock_get.return_value = mock_platform
                    mock_get_services.return_value = services

                    from bot.api.main import app
                    from bot.api.auth import create_access_token

                    token = create_access_token(tenant.id, tenant.email)
                    headers = {"Authorization": f"Bearer {token.access_token}"}

                    with TestClient(app, raise_server_exceptions=False) as test_client:
                        yield test_client, headers, tenant, services

        os.unlink(path)

    def test_create_product(self, authenticated_client):
        """Test creating a product via API."""
        test_client, headers, tenant, services = authenticated_client

        response = test_client.post("/api/products", headers=headers, json={
            "name": "API Product",
            "description": "Created via API",
            "category": "Electronics",
            "price_xmr": "1.5",
            "inventory": 50
        })

        assert response.status_code == 200
        product = response.json()
        assert product["name"] == "API Product"
        assert product["inventory"] == 50

    def test_list_products(self, authenticated_client):
        """Test listing products via API."""
        test_client, headers, tenant, services = authenticated_client

        # Create products first
        for i in range(3):
            services["db"].create_product(
                tenant.id, f"Product {i}", Decimal("1.0"), 10,
                description=f"Product {i} description"
            )

        response = test_client.get("/api/products", headers=headers)
        assert response.status_code == 200
        products = response.json()
        assert len(products) == 3

    def test_update_product(self, authenticated_client):
        """Test updating a product via API."""
        test_client, headers, tenant, services = authenticated_client

        # Create product
        product = services["db"].create_product(
            tenant.id, "Original", Decimal("1.0"), 10
        )

        response = test_client.put(
            f"/api/products/{product.id}",
            headers=headers,
            json={"name": "Updated", "inventory": 25}
        )

        assert response.status_code == 200
        updated = response.json()
        assert updated["name"] == "Updated"
        assert updated["inventory"] == 25

    def test_delete_product(self, authenticated_client):
        """Test deleting (deactivating) a product via API."""
        test_client, headers, tenant, services = authenticated_client

        product = services["db"].create_product(
            tenant.id, "To Delete", Decimal("1.0"), 10
        )

        response = test_client.delete(
            f"/api/products/{product.id}",
            headers=headers
        )

        assert response.status_code == 200
        assert "deactivated" in response.json()["message"].lower()


class TestOrderAPIFlow:
    """
    E2E Test: Order management via API.

    Flow tested:
    1. List orders
    2. View order details
    3. Fulfill orders
    4. Cancel orders
    """

    @pytest.fixture
    def client_with_orders(self):
        """Create client with tenant and orders."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        from bot.models_multitenant import MultiTenantDatabase, OrderState
        db = MultiTenantDatabase(f"sqlite:///{path}")

        # Create tenant
        tenant = db.create_tenant("orders@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94
        )

        # Create product
        product = db.create_product(tenant.id, "Test Product", Decimal("1.0"), 100)

        # Create orders
        orders = []
        for i in range(3):
            order = db.create_order(
                tenant.id, product.id, 2001 + i, 1 + i,
                Decimal(str(1 + i)), Decimal("0.05"),
                "xmr", Decimal(str(1 + i)), f"addr{i}", f"enc{i}"
            )
            orders.append(order)

        mock_platform = MagicMock()
        mock_platform.start = AsyncMock()
        mock_platform.stop = AsyncMock()
        mock_platform.bot_manager = MagicMock()
        mock_platform.bot_manager.health_check = AsyncMock(return_value={})

        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        from bot.services.tenant import TenantService

        services = {
            "db": db,
            "tenant_service": TenantService(db),
            "order_service": MultiCryptoOrderService(db, CryptoSwapService(testnet=True)),
            "commission_service": CommissionService(db, "4Platform"),
            "bot_manager": MagicMock(),
            "swap_service": CryptoSwapService(testnet=True),
        }
        services["bot_manager"].start_bot = AsyncMock()
        services["bot_manager"].stop_bot = AsyncMock()

        mock_platform.get_services.return_value = services

        with patch("bot.api.main.create_platform") as mock_create:
            with patch("bot.api.main.get_platform") as mock_get:
                with patch("bot.api.main.get_services") as mock_get_services:
                    mock_create.return_value = mock_platform
                    mock_get.return_value = mock_platform
                    mock_get_services.return_value = services

                    from bot.api.main import app
                    from bot.api.auth import create_access_token

                    token = create_access_token(tenant.id, tenant.email)
                    headers = {"Authorization": f"Bearer {token.access_token}"}

                    with TestClient(app, raise_server_exceptions=False) as test_client:
                        yield test_client, headers, tenant, orders, services

        os.unlink(path)

    def test_list_orders(self, client_with_orders):
        """Test listing orders via API."""
        test_client, headers, tenant, orders, services = client_with_orders

        response = test_client.get("/api/orders", headers=headers)
        assert response.status_code == 200
        order_list = response.json()
        assert len(order_list) == 3

    def test_get_order_details(self, client_with_orders):
        """Test getting order details via API."""
        test_client, headers, tenant, orders, services = client_with_orders

        response = test_client.get(
            f"/api/orders/{orders[0].id}",
            headers=headers
        )
        assert response.status_code == 200
        order = response.json()
        assert order["id"] == orders[0].id

    def test_fulfill_order(self, client_with_orders):
        """Test fulfilling an order via API."""
        test_client, headers, tenant, orders, services = client_with_orders

        # First mark as paid
        from bot.models_multitenant import OrderState
        services["db"].update_order_state(orders[0].id, tenant.id, OrderState.PAID)

        response = test_client.post(
            f"/api/orders/{orders[0].id}/fulfill",
            headers=headers
        )
        assert response.status_code == 200
        assert "fulfilled" in response.json()["message"].lower()

    def test_cancel_order(self, client_with_orders):
        """Test cancelling an order via API."""
        test_client, headers, tenant, orders, services = client_with_orders

        response = test_client.post(
            f"/api/orders/{orders[1].id}/cancel",
            headers=headers
        )
        assert response.status_code == 200
        assert "cancelled" in response.json()["message"].lower()


class TestBillingAPIFlow:
    """
    E2E Test: Billing and commission via API.

    Flow tested:
    1. View plan/commission rate
    2. List invoices
    3. View invoice details
    """

    @pytest.fixture
    def client_with_billing(self):
        """Create client with tenant and invoices."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        from bot.models_multitenant import MultiTenantDatabase
        from datetime import date

        db = MultiTenantDatabase(f"sqlite:///{path}")

        # Create tenant
        tenant = db.create_tenant("billing@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            commission_rate=Decimal("0.05")
        )

        # Create invoices
        invoices = []
        for i in range(2):
            invoice = db.create_commission_invoice(
                tenant.id,
                date(2024, 1, 1 + i*7), date(2024, 1, 7 + i*7),
                10, Decimal("100"), Decimal("0.05"), Decimal("5.0"),
                "4InvoiceAddr", datetime.utcnow() + timedelta(days=14)
            )
            invoices.append(invoice)

        mock_platform = MagicMock()
        mock_platform.start = AsyncMock()
        mock_platform.stop = AsyncMock()
        mock_platform.bot_manager = MagicMock()
        mock_platform.bot_manager.health_check = AsyncMock(return_value={})

        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        from bot.services.tenant import TenantService

        services = {
            "db": db,
            "tenant_service": TenantService(db),
            "order_service": MultiCryptoOrderService(db, CryptoSwapService(testnet=True)),
            "commission_service": CommissionService(db, "4Platform"),
            "bot_manager": MagicMock(),
            "swap_service": CryptoSwapService(testnet=True),
        }
        services["bot_manager"].start_bot = AsyncMock()
        services["bot_manager"].stop_bot = AsyncMock()

        mock_platform.get_services.return_value = services

        with patch("bot.api.main.create_platform") as mock_create:
            with patch("bot.api.main.get_platform") as mock_get:
                with patch("bot.api.main.get_services") as mock_get_services:
                    mock_create.return_value = mock_platform
                    mock_get.return_value = mock_platform
                    mock_get_services.return_value = services

                    from bot.api.main import app
                    from bot.api.auth import create_access_token

                    token = create_access_token(tenant.id, tenant.email)
                    headers = {"Authorization": f"Bearer {token.access_token}"}

                    with TestClient(app, raise_server_exceptions=False) as test_client:
                        yield test_client, headers, tenant, invoices, services

        os.unlink(path)

    def test_get_plan_info(self, client_with_billing):
        """Test getting plan/commission info via API."""
        test_client, headers, tenant, invoices, services = client_with_billing

        response = test_client.get("/api/billing/plan", headers=headers)
        assert response.status_code == 200
        plan = response.json()
        assert "commission_rate" in plan

    def test_list_invoices(self, client_with_billing):
        """Test listing invoices via API."""
        test_client, headers, tenant, invoices, services = client_with_billing

        response = test_client.get("/api/billing/invoices", headers=headers)
        assert response.status_code == 200
        invoice_list = response.json()
        assert len(invoice_list) == 2

    def test_get_invoice_details(self, client_with_billing):
        """Test getting invoice details via API."""
        test_client, headers, tenant, invoices, services = client_with_billing

        response = test_client.get(
            f"/api/billing/invoices/{invoices[0].id}",
            headers=headers
        )
        assert response.status_code == 200
        invoice = response.json()
        assert invoice["id"] == invoices[0].id


class TestTenantIsolation:
    """
    E2E Test: Multi-tenant data isolation.

    Tests that tenants cannot access each other's data.
    """

    @pytest.fixture
    def multi_tenant_client(self):
        """Create client with multiple tenants."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        from bot.models_multitenant import MultiTenantDatabase
        db = MultiTenantDatabase(f"sqlite:///{path}")

        # Create two tenants
        tenant1 = db.create_tenant("tenant1@test.com", "hash1", "1.0")
        tenant2 = db.create_tenant("tenant2@test.com", "hash2", "1.0")

        # Create products for each
        product1 = db.create_product(tenant1.id, "Tenant 1 Product", Decimal("1.0"), 10)
        product2 = db.create_product(tenant2.id, "Tenant 2 Product", Decimal("2.0"), 20)

        mock_platform = MagicMock()
        mock_platform.start = AsyncMock()
        mock_platform.stop = AsyncMock()
        mock_platform.bot_manager = MagicMock()
        mock_platform.bot_manager.health_check = AsyncMock(return_value={})

        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        from bot.services.tenant import TenantService

        services = {
            "db": db,
            "tenant_service": TenantService(db),
            "order_service": MultiCryptoOrderService(db, CryptoSwapService(testnet=True)),
            "commission_service": CommissionService(db, "4Platform"),
            "bot_manager": MagicMock(),
            "swap_service": CryptoSwapService(testnet=True),
        }
        services["bot_manager"].start_bot = AsyncMock()
        services["bot_manager"].stop_bot = AsyncMock()

        mock_platform.get_services.return_value = services

        with patch("bot.api.main.create_platform") as mock_create:
            with patch("bot.api.main.get_platform") as mock_get:
                with patch("bot.api.main.get_services") as mock_get_services:
                    mock_create.return_value = mock_platform
                    mock_get.return_value = mock_platform
                    mock_get_services.return_value = services

                    from bot.api.main import app
                    from bot.api.auth import create_access_token

                    token1 = create_access_token(tenant1.id, tenant1.email)
                    token2 = create_access_token(tenant2.id, tenant2.email)

                    headers1 = {"Authorization": f"Bearer {token1.access_token}"}
                    headers2 = {"Authorization": f"Bearer {token2.access_token}"}

                    with TestClient(app, raise_server_exceptions=False) as test_client:
                        yield test_client, headers1, headers2, tenant1, tenant2, product1, product2, services

        os.unlink(path)

    def test_tenant_can_only_see_own_products(self, multi_tenant_client):
        """Test that tenants can only see their own products."""
        (test_client, headers1, headers2,
         tenant1, tenant2, product1, product2, services) = multi_tenant_client

        # Tenant 1 lists products
        response = test_client.get("/api/products", headers=headers1)
        assert response.status_code == 200
        products = response.json()
        assert len(products) == 1
        assert products[0]["name"] == "Tenant 1 Product"

        # Tenant 2 lists products
        response = test_client.get("/api/products", headers=headers2)
        assert response.status_code == 200
        products = response.json()
        assert len(products) == 1
        assert products[0]["name"] == "Tenant 2 Product"

    def test_tenant_cannot_access_other_tenant_product(self, multi_tenant_client):
        """Test that tenant cannot access another tenant's product."""
        (test_client, headers1, headers2,
         tenant1, tenant2, product1, product2, services) = multi_tenant_client

        # Tenant 1 tries to access Tenant 2's product
        response = test_client.get(
            f"/api/products/{product2.id}",
            headers=headers1
        )
        assert response.status_code == 404

    def test_tenant_cannot_modify_other_tenant_product(self, multi_tenant_client):
        """Test that tenant cannot modify another tenant's product."""
        (test_client, headers1, headers2,
         tenant1, tenant2, product1, product2, services) = multi_tenant_client

        # Tenant 1 tries to update Tenant 2's product
        response = test_client.put(
            f"/api/products/{product2.id}",
            headers=headers1,
            json={"name": "Hacked!"}
        )
        assert response.status_code == 404

        # Verify product wasn't changed
        actual = services["db"].get_product(product2.id, tenant2.id)
        assert actual.name == "Tenant 2 Product"
