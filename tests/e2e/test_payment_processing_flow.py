"""
E2E Tests: Payment Processing Flow

Tests the complete payment processing journey including multi-crypto payments.
"""

import pytest
import tempfile
import os
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from bot.models_multitenant import (
    MultiTenantDatabase, OrderState, SwapState
)
from bot.services.crypto_swap import CryptoSwapService, SwapOrder, SwapStatus
from bot.services.multicrypto_orders import MultiCryptoOrderService
from bot.services.commission import CommissionService


class TestXMRDirectPaymentFlow:
    """
    E2E Test: Direct XMR payment flow.

    Flow tested:
    1. Create order with XMR payment
    2. Verify payment address generated
    3. Detect payment
    4. Order marked as paid
    """

    @pytest.fixture
    def db(self):
        """Create test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def services(self, db):
        """Create services."""
        swap = CryptoSwapService(testnet=True)
        orders = MultiCryptoOrderService(db, swap)
        return db, swap, orders

    @pytest.fixture
    def tenant_with_product(self, db):
        """Create tenant with product."""
        tenant = db.create_tenant("xmr@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94,
            shop_name="XMR Shop"
        )
        # Fetch updated tenant
        tenant = db.get_tenant(tenant.id)
        product = db.create_product(tenant.id, "XMR Product", Decimal("2.5"), 50)
        return tenant, product

    @pytest.mark.asyncio
    async def test_xmr_order_creation(self, services, tenant_with_product):
        """Test creating an order with direct XMR payment."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=2,
            delivery_address="123 Test Street",
            payment_coin="xmr"
        )

        assert result["order_id"] is not None
        assert result["payment_coin"] == "XMR"
        assert result["payment_address"] == tenant.monero_wallet_address
        assert result["swap_id"] is None
        assert Decimal(str(result["total_xmr"])) == Decimal("5.0")  # 2.5 * 2

    @pytest.mark.asyncio
    async def test_xmr_payment_detection(self, services, tenant_with_product):
        """Test XMR payment detection and order state change."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        # Create order
        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="Test Address",
            payment_coin="xmr"
        )

        order_id = result["order_id"]

        # Verify initial state
        order = db.get_order(order_id, tenant.id)
        assert order.state == OrderState.PENDING

        # Simulate payment detection
        db.update_order_state(order_id, tenant.id, OrderState.PAID, datetime.utcnow())

        # Verify paid state
        order = db.get_order(order_id, tenant.id)
        assert order.state == OrderState.PAID
        assert order.paid_at is not None

    @pytest.mark.asyncio
    async def test_xmr_inventory_decrement(self, services, tenant_with_product):
        """Test that inventory is decremented on order creation."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        original_inventory = product.inventory

        await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=5,
            delivery_address="Test",
            payment_coin="xmr"
        )

        updated = db.get_product(product.id, tenant.id)
        assert updated.inventory == original_inventory - 5


class TestMultiCryptoSwapFlow:
    """
    E2E Test: Multi-crypto payment with swap.

    Flow tested:
    1. Create order with non-XMR payment (BTC, ETH, etc.)
    2. Swap service creates deposit address
    3. Customer sends crypto
    4. Swap completes
    5. Order marked as paid
    """

    @pytest.fixture
    def db(self):
        """Create test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def services(self, db):
        """Create services with mock swap."""
        swap = CryptoSwapService(testnet=True)
        orders = MultiCryptoOrderService(db, swap)
        return db, swap, orders

    @pytest.fixture
    def tenant_with_product(self, db):
        """Create tenant with product."""
        tenant = db.create_tenant("swap@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94
        )
        product = db.create_product(tenant.id, "Swap Product", Decimal("1.0"), 100)
        return tenant, product

    @pytest.mark.asyncio
    async def test_btc_order_with_swap(self, services, tenant_with_product):
        """Test creating order with BTC payment (requires swap)."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="BTC Buyer Address",
            payment_coin="btc"
        )

        assert result["payment_coin"] == "BTC"
        assert result["swap_id"] is not None
        assert result["payment_address"].startswith("bc1qtest")  # Mock address

    @pytest.mark.asyncio
    async def test_eth_order_with_swap(self, services, tenant_with_product):
        """Test creating order with ETH payment (requires swap)."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="ETH Buyer Address",
            payment_coin="eth"
        )

        assert result["payment_coin"] == "ETH"
        assert result["swap_id"] is not None
        assert result["payment_address"].startswith("0x")

    @pytest.mark.asyncio
    async def test_swap_status_progression(self, services, tenant_with_product):
        """Test swap status progression from waiting to complete."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        # Create BTC order
        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="Test",
            payment_coin="btc"
        )

        order_id = result["order_id"]

        # Check initial status (mock returns complete)
        status = await orders.check_order_payment(order_id, tenant.id)

        # Mock swap service returns complete status
        assert status["state"] == "paid"

    @pytest.mark.asyncio
    async def test_swap_failure_handling(self, services, tenant_with_product):
        """Test handling of failed swap."""
        db, swap, orders = services
        tenant, product = tenant_with_product

        result = await orders.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            delivery_address="Test",
            payment_coin="btc"
        )

        order_id = result["order_id"]

        # Mock failed swap status
        with patch.object(
            swap, 'check_swap_status',
            new_callable=AsyncMock,
            return_value=SwapStatus.FAILED
        ):
            status = await orders.check_order_payment(order_id, tenant.id)
            assert status["state"] == "cancelled"

    @pytest.mark.asyncio
    async def test_supported_payment_methods(self, services, tenant_with_product):
        """Test getting supported payment methods."""
        db, swap, orders = services

        methods = await orders.get_supported_payment_methods()

        assert "xmr" in methods
        assert "btc" in methods
        assert "eth" in methods
        assert "sol" in methods


class TestCommissionCalculationFlow:
    """
    E2E Test: Commission calculation and invoice generation.

    Flow tested:
    1. Orders are created and paid
    2. Commission is calculated per order
    3. Weekly invoice is generated
    4. Invoice payment is tracked
    """

    @pytest.fixture
    def db(self):
        """Create test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def services(self, db):
        """Create services."""
        swap = CryptoSwapService(testnet=True)
        orders = MultiCryptoOrderService(db, swap)
        commission = CommissionService(db, "4PlatformAddress" + "A" * 80)
        return db, orders, commission

    @pytest.fixture
    def tenant_with_orders(self, db):
        """Create tenant with paid orders."""
        from datetime import timedelta

        tenant = db.create_tenant("commission@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94,
            bot_active=True,
            commission_rate=Decimal("0.05")  # 5% commission
        )

        product = db.create_product(tenant.id, "Commission Product", Decimal("10.0"), 1000)

        # Create paid orders
        orders = []
        for i in range(5):
            order = db.create_order(
                tenant.id, product.id, 12345 + i, 1,
                Decimal("10.0"), Decimal("0.5"),  # 5% of 10 = 0.5
                "xmr", Decimal("10.0"), "addr", "enc"
            )
            db.update_order_state(
                order.id, tenant.id, OrderState.PAID,
                datetime.utcnow() - timedelta(days=3)
            )
            orders.append(order)

        return tenant, product, orders

    def test_commission_per_order(self, services, tenant_with_orders):
        """Test that commission is calculated correctly per order."""
        db, orders, commission = services
        tenant, product, created_orders = tenant_with_orders

        for order in created_orders:
            fetched = db.get_order(order.id, tenant.id)
            assert fetched.commission_xmr == Decimal("0.5")  # 5% of 10.0

    def test_weekly_invoice_generation(self, services, tenant_with_orders):
        """Test weekly invoice generation."""
        db, orders, commission = services
        tenant, product, created_orders = tenant_with_orders

        invoices = commission.generate_weekly_invoices()

        assert len(invoices) == 1
        invoice = invoices[0]
        assert invoice.tenant_id == tenant.id
        assert invoice.order_count == 5
        assert invoice.total_sales_xmr == Decimal("50.0")  # 5 orders * 10.0
        assert invoice.commission_due_xmr == Decimal("2.5")  # 5% of 50.0

    def test_invoice_payment_tracking(self, services, tenant_with_orders):
        """Test tracking invoice payment."""
        db, orders, commission = services
        tenant, product, created_orders = tenant_with_orders

        # Generate invoice
        invoices = commission.generate_weekly_invoices()
        invoice = invoices[0]

        # Check payment (sufficient amount)
        result = commission.check_payment(invoice.id, Decimal("2.5"))
        assert result is True

        # Verify invoice is marked paid
        from bot.models_multitenant import InvoiceState
        updated = commission.get_invoice(invoice.id)
        assert updated.state == InvoiceState.PAID

    def test_platform_revenue_calculation(self, services, tenant_with_orders):
        """Test platform revenue calculation."""
        db, orders, commission = services
        tenant, product, created_orders = tenant_with_orders

        # Generate and pay invoice
        invoices = commission.generate_weekly_invoices()
        commission.check_payment(invoices[0].id, Decimal("2.5"))

        # Calculate revenue
        revenue = commission.calculate_platform_revenue()

        assert revenue["invoice_count"] == 1
        assert revenue["total_commission_xmr"] == Decimal("2.5")
        assert revenue["total_sales_volume_xmr"] == Decimal("50.0")


class TestPaymentEdgeCases:
    """
    E2E Test: Payment edge cases and error handling.
    """

    @pytest.fixture
    def db(self):
        """Create test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def services(self, db):
        """Create services."""
        swap = CryptoSwapService(testnet=True)
        orders = MultiCryptoOrderService(db, swap)
        return db, swap, orders

    @pytest.fixture
    def tenant(self, db):
        """Create tenant."""
        tenant = db.create_tenant("edge@test.com", "hash", "1.0")
        db.update_tenant(
            tenant.id,
            monero_wallet_address="4" + "A" * 94
        )
        return tenant

    @pytest.mark.asyncio
    async def test_order_with_unsupported_coin_rejected(self, services, tenant, db):
        """Test that unsupported payment coins are rejected."""
        db_inst, swap, orders = services

        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        with pytest.raises(ValueError, match="Unsupported"):
            await orders.create_order(
                tenant.id, product.id, 12345, 1, "Test", "doge"
            )

    @pytest.mark.asyncio
    async def test_order_without_wallet_rejected(self, services, db):
        """Test that orders are rejected when tenant has no wallet."""
        db_inst, swap, orders = services

        # Create tenant without wallet
        tenant = db.create_tenant("nowallet@test.com", "hash", "1.0")
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        with pytest.raises(ValueError, match="wallet"):
            await orders.create_order(
                tenant.id, product.id, 12345, 1, "Test", "xmr"
            )

    @pytest.mark.asyncio
    async def test_order_for_inactive_product_rejected(self, services, tenant, db):
        """Test that orders for inactive products are rejected."""
        db_inst, swap, orders = services

        product = db.create_product(tenant.id, "Inactive", Decimal("1.0"), 10)
        db.update_product(product.id, tenant.id, active=False)

        with pytest.raises(ValueError, match="not available"):
            await orders.create_order(
                tenant.id, product.id, 12345, 1, "Test", "xmr"
            )

    @pytest.mark.asyncio
    async def test_order_exceeding_inventory_rejected(self, services, tenant, db):
        """Test that orders exceeding inventory are rejected."""
        db_inst, swap, orders = services

        product = db.create_product(tenant.id, "Limited", Decimal("1.0"), 5)

        with pytest.raises(ValueError, match="Insufficient"):
            await orders.create_order(
                tenant.id, product.id, 12345, 10, "Test", "xmr"
            )

    @pytest.mark.asyncio
    async def test_order_cancellation_restores_inventory(self, services, tenant, db):
        """Test that cancelling order restores inventory."""
        db_inst, swap, orders = services

        product = db.create_product(tenant.id, "Restore", Decimal("1.0"), 20)
        original = product.inventory

        # Create order
        result = await orders.create_order(
            tenant.id, product.id, 12345, 5, "Test", "xmr"
        )

        # Verify decrement
        after_order = db.get_product(product.id, tenant.id)
        assert after_order.inventory == original - 5

        # Cancel order
        orders.cancel_order(result["order_id"], tenant.id)

        # Verify restoration
        after_cancel = db.get_product(product.id, tenant.id)
        assert after_cancel.inventory == original

    @pytest.mark.asyncio
    async def test_swap_expired_cancels_order(self, services, tenant, db):
        """Test that expired swap cancels the order."""
        db_inst, swap, orders = services

        product = db.create_product(tenant.id, "Expire", Decimal("1.0"), 10)

        result = await orders.create_order(
            tenant.id, product.id, 12345, 1, "Test", "btc"
        )

        # Mock expired swap status
        with patch.object(
            swap, 'check_swap_status',
            new_callable=AsyncMock,
            return_value=SwapStatus.EXPIRED
        ):
            status = await orders.check_order_payment(result["order_id"], tenant.id)
            assert status["state"] == "cancelled"
