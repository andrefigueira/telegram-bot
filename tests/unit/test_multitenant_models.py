"""Tests for multi-tenant database models."""

import pytest
from datetime import datetime, date, timedelta
from decimal import Decimal
import tempfile
import os

from bot.models_multitenant import (
    MultiTenantDatabase, Tenant, TenantProduct, TenantOrder,
    CommissionInvoice, AuditLog, OrderState, InvoiceState, SwapState
)


class TestMultiTenantDatabase:
    """Test MultiTenantDatabase operations."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        # Use a temporary file for SQLite
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        # Cleanup
        os.unlink(path)

    @pytest.fixture
    def tenant(self, db):
        """Create a test tenant."""
        return db.create_tenant(
            email="test@example.com",
            password_hash="hashed_password",
            terms_version="1.0"
        )

    # ==================== TENANT TESTS ====================

    def test_create_tenant(self, db):
        """Test creating a tenant."""
        tenant = db.create_tenant(
            email="new@example.com",
            password_hash="hash123",
            terms_version="1.0"
        )

        assert tenant.id is not None
        assert tenant.email == "new@example.com"
        assert tenant.password_hash == "hash123"
        assert tenant.accepted_terms_version == "1.0"
        assert tenant.accepted_terms_at is not None
        assert tenant.commission_rate == Decimal("0.05")
        assert tenant.bot_active is False
        assert len(tenant.encryption_key) == 64  # hex string

    def test_get_tenant(self, db, tenant):
        """Test getting tenant by ID."""
        fetched = db.get_tenant(tenant.id)
        assert fetched is not None
        assert fetched.email == tenant.email

    def test_get_tenant_not_found(self, db):
        """Test getting non-existent tenant."""
        fetched = db.get_tenant("nonexistent-id")
        assert fetched is None

    def test_get_tenant_by_email(self, db, tenant):
        """Test getting tenant by email."""
        fetched = db.get_tenant_by_email("test@example.com")
        assert fetched is not None
        assert fetched.id == tenant.id

    def test_get_tenant_by_email_not_found(self, db):
        """Test getting tenant by non-existent email."""
        fetched = db.get_tenant_by_email("notfound@example.com")
        assert fetched is None

    def test_update_tenant(self, db, tenant):
        """Test updating tenant fields."""
        updated = db.update_tenant(
            tenant.id,
            shop_name="My Shop",
            monero_wallet_address="4AAAA...",
            bot_active=True
        )

        assert updated is not None
        assert updated.shop_name == "My Shop"
        assert updated.monero_wallet_address == "4AAAA..."
        assert updated.bot_active is True

    def test_get_active_tenants(self, db):
        """Test getting active tenants."""
        # Create inactive tenant
        db.create_tenant("inactive@test.com", "hash", "1.0")

        # Create active tenant
        active = db.create_tenant("active@test.com", "hash", "1.0")
        db.update_tenant(active.id, bot_active=True)

        active_tenants = db.get_active_tenants()
        assert len(active_tenants) == 1
        assert active_tenants[0].email == "active@test.com"

    # ==================== PRODUCT TESTS ====================

    def test_create_product(self, db, tenant):
        """Test creating a product."""
        product = db.create_product(
            tenant_id=tenant.id,
            name="Test Product",
            price_xmr=Decimal("0.5"),
            inventory=10,
            description="A test product",
            category="electronics"
        )

        assert product.id is not None
        assert product.name == "Test Product"
        assert product.price_xmr == Decimal("0.5")
        assert product.inventory == 10
        assert product.tenant_id == tenant.id
        assert product.active is True

    def test_get_products(self, db, tenant):
        """Test getting products for a tenant."""
        # Create multiple products
        db.create_product(tenant.id, "Product 1", Decimal("1.0"), 5)
        db.create_product(tenant.id, "Product 2", Decimal("2.0"), 3)

        # Create inactive product
        p3 = db.create_product(tenant.id, "Inactive", Decimal("3.0"), 0)
        db.update_product(p3.id, tenant.id, active=False)

        # Get active only
        products = db.get_products(tenant.id, active_only=True)
        assert len(products) == 2

        # Get all
        all_products = db.get_products(tenant.id, active_only=False)
        assert len(all_products) == 3

    def test_get_product(self, db, tenant):
        """Test getting a specific product."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 5)

        fetched = db.get_product(product.id, tenant.id)
        assert fetched is not None
        assert fetched.name == "Test"

    def test_get_product_wrong_tenant(self, db, tenant):
        """Test that product is not returned for wrong tenant."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 5)

        # Try to get with different tenant ID
        fetched = db.get_product(product.id, "wrong-tenant-id")
        assert fetched is None

    def test_update_product(self, db, tenant):
        """Test updating a product."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 5)

        updated = db.update_product(
            product.id,
            tenant.id,
            name="Updated Name",
            price_xmr=Decimal("2.0"),
            inventory=10
        )

        assert updated is not None
        assert updated.name == "Updated Name"
        assert updated.price_xmr == Decimal("2.0")
        assert updated.inventory == 10

    def test_decrement_inventory(self, db, tenant):
        """Test decrementing product inventory."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        # Successful decrement
        result = db.decrement_inventory(product.id, tenant.id, 3)
        assert result is True

        fetched = db.get_product(product.id, tenant.id)
        assert fetched.inventory == 7

    def test_decrement_inventory_insufficient(self, db, tenant):
        """Test decrementing with insufficient inventory."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 5)

        result = db.decrement_inventory(product.id, tenant.id, 10)
        assert result is False

        # Inventory unchanged
        fetched = db.get_product(product.id, tenant.id)
        assert fetched.inventory == 5

    # ==================== ORDER TESTS ====================

    def test_create_order(self, db, tenant):
        """Test creating an order."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        order = db.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=2,
            total_xmr=Decimal("2.0"),
            commission_xmr=Decimal("0.1"),
            payment_coin="btc",
            payment_amount=Decimal("0.008"),
            payment_address="bc1qtest...",
            address_encrypted="encrypted_address",
            swap_id="swap123",
            swap_provider="trocador"
        )

        assert order.id is not None
        assert order.tenant_id == tenant.id
        assert order.payment_coin == "btc"
        assert order.swap_id == "swap123"
        assert order.state == OrderState.SWAP_PENDING

    def test_create_order_xmr_direct(self, db, tenant):
        """Test creating direct XMR order (no swap)."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        order = db.create_order(
            tenant_id=tenant.id,
            product_id=product.id,
            customer_telegram_id=12345,
            quantity=1,
            total_xmr=Decimal("1.0"),
            commission_xmr=Decimal("0.05"),
            payment_coin="xmr",
            payment_amount=Decimal("1.0"),
            payment_address="4AAAA...",
            address_encrypted="encrypted"
        )

        assert order.state == OrderState.PENDING
        assert order.swap_id is None

    def test_get_order(self, db, tenant):
        """Test getting an order."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "addr", "enc"
        )

        fetched = db.get_order(order.id, tenant.id)
        assert fetched is not None
        assert fetched.id == order.id

    def test_get_order_by_payment_id(self, db, tenant):
        """Test getting order by payment ID."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "addr", "enc"
        )

        fetched = db.get_order_by_payment_id(order.payment_id)
        assert fetched is not None
        assert fetched.id == order.id

    def test_update_order_state(self, db, tenant):
        """Test updating order state."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "addr", "enc"
        )

        updated = db.update_order_state(
            order.id, tenant.id, OrderState.PAID, datetime.utcnow()
        )

        assert updated is not None
        assert updated.state == OrderState.PAID
        assert updated.paid_at is not None

    def test_update_order_swap_status(self, db, tenant):
        """Test updating order swap status."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "btc", Decimal("0.004"), "bc1q...", "enc",
            swap_id="swap123", swap_provider="trocador"
        )

        # Update to complete
        updated = db.update_order_swap_status(order.id, SwapState.COMPLETE)

        assert updated is not None
        assert updated.swap_status == SwapState.COMPLETE
        assert updated.state == OrderState.PAID
        assert updated.paid_at is not None

    def test_update_order_swap_failed(self, db, tenant):
        """Test updating order when swap fails."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "btc", Decimal("0.004"), "bc1q...", "enc",
            swap_id="swap123", swap_provider="trocador"
        )

        updated = db.update_order_swap_status(order.id, SwapState.FAILED)

        assert updated.swap_status == SwapState.FAILED
        assert updated.state == OrderState.CANCELLED

    def test_get_pending_swap_orders(self, db, tenant):
        """Test getting pending swap orders."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 10)

        # Create swap order
        db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "btc", Decimal("0.004"), "bc1q...", "enc",
            swap_id="swap123", swap_provider="trocador"
        )

        # Create direct XMR order
        db.create_order(
            tenant.id, product.id, 12346, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "4AAA...", "enc"
        )

        pending = db.get_pending_swap_orders()
        assert len(pending) == 1
        assert pending[0].payment_coin == "btc"

    # ==================== COMMISSION TESTS ====================

    def test_create_commission_invoice(self, db, tenant):
        """Test creating a commission invoice."""
        invoice = db.create_commission_invoice(
            tenant_id=tenant.id,
            period_start=date(2024, 1, 1),
            period_end=date(2024, 1, 7),
            order_count=10,
            total_sales_xmr=Decimal("50.0"),
            commission_rate=Decimal("0.05"),
            commission_due_xmr=Decimal("2.5"),
            payment_address="4AAAA...",
            due_date=datetime(2024, 1, 14)
        )

        assert invoice.id is not None
        assert invoice.commission_due_xmr == Decimal("2.5")
        assert invoice.state == InvoiceState.PENDING

    def test_get_pending_invoices(self, db, tenant):
        """Test getting pending invoices."""
        db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("25"), Decimal("0.05"), Decimal("1.25"),
            "4AAA...", datetime(2024, 1, 14)
        )

        pending = db.get_pending_invoices(tenant.id)
        assert len(pending) == 1

    def test_mark_invoice_paid(self, db, tenant):
        """Test marking invoice as paid."""
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("25"), Decimal("0.05"), Decimal("1.25"),
            "4AAA...", datetime(2024, 1, 14)
        )

        paid = db.mark_invoice_paid(invoice.id)
        assert paid.state == InvoiceState.PAID
        assert paid.paid_at is not None

    def test_mark_invoice_overdue(self, db, tenant):
        """Test marking invoice as overdue."""
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("25"), Decimal("0.05"), Decimal("1.25"),
            "4AAA...", datetime(2024, 1, 14)
        )

        overdue = db.mark_invoice_overdue(invoice.id)
        assert overdue.state == InvoiceState.OVERDUE

    def test_get_overdue_invoices(self, db, tenant):
        """Test getting overdue invoices."""
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("25"), Decimal("0.05"), Decimal("1.25"),
            "4AAA...", datetime(2024, 1, 14)
        )
        db.mark_invoice_overdue(invoice.id)

        overdue = db.get_overdue_invoices()
        assert len(overdue) == 1

    # ==================== AUDIT LOG TESTS ====================

    def test_log_action(self, db, tenant):
        """Test logging an action."""
        db.log_action(
            action="test_action",
            tenant_id=tenant.id,
            details='{"key": "value"}',
            ip_address="127.0.0.1"
        )

        # Verify log was created
        from sqlmodel import select
        with db.get_session() as session:
            statement = select(AuditLog).where(AuditLog.action == "test_action")
            log = session.exec(statement).first()

            assert log is not None
            assert log.tenant_id == tenant.id
            assert log.details == '{"key": "value"}'

    # ==================== COMPLETED ORDERS TESTS ====================

    def test_get_completed_orders_for_period(self, db, tenant):
        """Test getting completed orders for commission calculation."""
        product = db.create_product(tenant.id, "Test", Decimal("1.0"), 100)

        # Create and mark order as paid
        order1 = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "addr", "enc"
        )
        db.update_order_state(order1.id, tenant.id, OrderState.PAID, datetime.utcnow())

        # Create pending order (should not be included)
        db.create_order(
            tenant.id, product.id, 12346, 1, Decimal("1.0"),
            Decimal("0.05"), "xmr", Decimal("1.0"), "addr", "enc"
        )

        completed = db.get_completed_orders_for_period(
            tenant.id,
            date.today() - timedelta(days=7),
            date.today()
        )

        assert len(completed) == 1
        assert completed[0].id == order1.id
