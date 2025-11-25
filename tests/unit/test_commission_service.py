"""Tests for commission tracking service."""

import pytest
import tempfile
import os
from datetime import date, datetime, timedelta
from decimal import Decimal

from bot.services.commission import CommissionService
from bot.models_multitenant import (
    MultiTenantDatabase, InvoiceState, OrderState
)


class TestCommissionService:
    """Test CommissionService functionality."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def commission_service(self, db):
        """Create commission service instance."""
        return CommissionService(
            db=db,
            platform_xmr_address="4PlatformAddress..."
        )

    @pytest.fixture
    def tenant_with_orders(self, db):
        """Create a tenant with completed orders."""
        tenant = db.create_tenant("shop@test.com", "hash", "1.0")
        db.update_tenant(tenant.id, bot_active=True, commission_rate=Decimal("0.05"))

        product = db.create_product(tenant.id, "Test Product", Decimal("10.0"), 100)

        # Create completed orders
        for i in range(5):
            order = db.create_order(
                tenant.id, product.id, 12345 + i, 1, Decimal("10.0"),
                Decimal("0.5"), "xmr", Decimal("10.0"), "addr", "enc"
            )
            db.update_order_state(
                order.id, tenant.id, OrderState.PAID,
                datetime.utcnow() - timedelta(days=3)
            )

        return tenant

    # ==================== INVOICE GENERATION TESTS ====================

    def test_generate_weekly_invoices(self, commission_service, tenant_with_orders):
        """Test generating weekly invoices."""
        invoices = commission_service.generate_weekly_invoices()

        assert len(invoices) == 1
        invoice = invoices[0]

        assert invoice.tenant_id == tenant_with_orders.id
        assert invoice.order_count == 5
        assert invoice.total_sales_xmr == Decimal("50.0")
        assert invoice.commission_rate == Decimal("0.05")
        assert invoice.commission_due_xmr == Decimal("2.5")
        assert invoice.state == InvoiceState.PENDING

    def test_generate_invoice_no_orders(self, commission_service, db):
        """Test invoice not generated when no orders."""
        tenant = db.create_tenant("empty@test.com", "hash", "1.0")
        db.update_tenant(tenant.id, bot_active=True)

        invoices = commission_service.generate_weekly_invoices()
        assert len(invoices) == 0

    def test_generate_invoice_inactive_tenant(self, commission_service, db):
        """Test inactive tenants don't get invoices."""
        tenant = db.create_tenant("inactive@test.com", "hash", "1.0")
        # bot_active defaults to False

        product = db.create_product(tenant.id, "Test", Decimal("10.0"), 10)
        order = db.create_order(
            tenant.id, product.id, 12345, 1, Decimal("10.0"),
            Decimal("0.5"), "xmr", Decimal("10.0"), "addr", "enc"
        )
        db.update_order_state(order.id, tenant.id, OrderState.PAID, datetime.utcnow())

        invoices = commission_service.generate_weekly_invoices()
        assert len(invoices) == 0

    # ==================== INVOICE RETRIEVAL TESTS ====================

    def test_get_invoice(self, commission_service, db):
        """Test getting an invoice by ID."""
        tenant = db.create_tenant("get@test.com", "hash", "1.0")
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        fetched = commission_service.get_invoice(invoice.id)
        assert fetched is not None
        assert fetched.id == invoice.id

    def test_get_tenant_invoices(self, commission_service, db):
        """Test getting invoices for a tenant."""
        tenant = db.create_tenant("list@test.com", "hash", "1.0")

        # Create multiple invoices
        for i in range(3):
            db.create_commission_invoice(
                tenant.id,
                date(2024, 1, 1 + i*7), date(2024, 1, 7 + i*7),
                5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
                "4AAA...", datetime(2024, 1, 14 + i*7)
            )

        invoices = commission_service.get_tenant_invoices(tenant.id)
        assert len(invoices) == 3

    def test_get_tenant_invoices_by_state(self, commission_service, db):
        """Test filtering invoices by state."""
        tenant = db.create_tenant("filter@test.com", "hash", "1.0")

        # Create pending invoice
        db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        # Create paid invoice
        paid = db.create_commission_invoice(
            tenant.id, date(2024, 1, 8), date(2024, 1, 14),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 21)
        )
        db.mark_invoice_paid(paid.id)

        pending = commission_service.get_tenant_invoices(
            tenant.id, state=InvoiceState.PENDING
        )
        assert len(pending) == 1

        paid_invoices = commission_service.get_tenant_invoices(
            tenant.id, state=InvoiceState.PAID
        )
        assert len(paid_invoices) == 1

    # ==================== PAYMENT CHECK TESTS ====================

    def test_check_payment_sufficient(self, commission_service, db):
        """Test checking payment with sufficient amount."""
        tenant = db.create_tenant("pay@test.com", "hash", "1.0")
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        result = commission_service.check_payment(invoice.id, Decimal("2.5"))
        assert result is True

        # Verify invoice is marked paid
        updated = commission_service.get_invoice(invoice.id)
        assert updated.state == InvoiceState.PAID

    def test_check_payment_insufficient(self, commission_service, db):
        """Test checking payment with insufficient amount."""
        tenant = db.create_tenant("short@test.com", "hash", "1.0")
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        result = commission_service.check_payment(invoice.id, Decimal("1.0"))
        assert result is False

        # Verify invoice is still pending
        updated = commission_service.get_invoice(invoice.id)
        assert updated.state == InvoiceState.PENDING

    def test_check_payment_overpayment(self, commission_service, db):
        """Test checking payment with overpayment (should accept)."""
        tenant = db.create_tenant("over@test.com", "hash", "1.0")
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        result = commission_service.check_payment(invoice.id, Decimal("5.0"))
        assert result is True

    # ==================== OVERDUE PROCESSING TESTS ====================

    def test_process_overdue_invoices(self, commission_service, db):
        """Test processing overdue invoices."""
        tenant = db.create_tenant("overdue@test.com", "hash", "1.0")
        db.update_tenant(tenant.id, bot_active=True)

        # Create overdue invoice (due date in the past)
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime.utcnow() - timedelta(days=1)
        )

        results = commission_service.process_overdue_invoices()

        assert results["marked_overdue"] == 1

        updated = commission_service.get_invoice(invoice.id)
        assert updated.state == InvoiceState.OVERDUE

    def test_process_overdue_suspension(self, commission_service, db):
        """Test that overdue invoices trigger suspension."""
        tenant = db.create_tenant("suspend@test.com", "hash", "1.0")
        db.update_tenant(tenant.id, bot_active=True)

        # Create invoice overdue by 8 days
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime.utcnow() - timedelta(days=8)
        )
        db.mark_invoice_overdue(invoice.id)

        results = commission_service.process_overdue_invoices()

        assert results["suspended"] == 1

        # Verify tenant is suspended
        tenant = db.get_tenant(tenant.id)
        assert tenant.bot_active is False

    def test_process_overdue_termination(self, commission_service, db):
        """Test that severely overdue invoices trigger termination."""
        tenant = db.create_tenant("terminate@test.com", "hash", "1.0")
        db.update_tenant(tenant.id, bot_active=True)

        # Create invoice overdue by 15 days
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime.utcnow() - timedelta(days=15)
        )
        db.mark_invoice_overdue(invoice.id)

        results = commission_service.process_overdue_invoices()

        assert results["terminated"] == 1

    # ==================== WAIVE INVOICE TESTS ====================

    def test_waive_invoice(self, commission_service, db):
        """Test waiving an invoice."""
        tenant = db.create_tenant("waive@test.com", "hash", "1.0")
        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("50"), Decimal("0.05"), Decimal("2.5"),
            "4AAA...", datetime(2024, 1, 14)
        )

        result = commission_service.waive_invoice(invoice.id, "Test waiver")
        assert result is True

        updated = commission_service.get_invoice(invoice.id)
        assert updated.state == InvoiceState.WAIVED

    def test_waive_nonexistent_invoice(self, commission_service):
        """Test waiving non-existent invoice."""
        result = commission_service.waive_invoice(99999, "Test")
        assert result is False

    # ==================== REVENUE CALCULATION TESTS ====================

    def test_calculate_platform_revenue(self, commission_service, db):
        """Test calculating platform revenue."""
        tenant = db.create_tenant("revenue@test.com", "hash", "1.0")

        # Create and pay multiple invoices
        for i in range(3):
            invoice = db.create_commission_invoice(
                tenant.id,
                date(2024, 1, 1 + i*7), date(2024, 1, 7 + i*7),
                5, Decimal("100"), Decimal("0.05"), Decimal("5.0"),
                "4AAA...", datetime(2024, 1, 14 + i*7)
            )
            db.mark_invoice_paid(invoice.id)

        revenue = commission_service.calculate_platform_revenue()

        assert revenue["invoice_count"] == 3
        assert revenue["total_commission_xmr"] == Decimal("15.0")
        assert revenue["total_sales_volume_xmr"] == Decimal("300")

    def test_calculate_platform_revenue_date_range(self, commission_service, db):
        """Test calculating revenue for date range."""
        tenant = db.create_tenant("range@test.com", "hash", "1.0")

        invoice = db.create_commission_invoice(
            tenant.id, date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("100"), Decimal("0.05"), Decimal("5.0"),
            "4AAA...", datetime(2024, 1, 14)
        )
        db.mark_invoice_paid(invoice.id)

        # Query for a date range that includes when the invoice was paid (today)
        today = date.today()
        revenue = commission_service.calculate_platform_revenue(
            start_date=today,
            end_date=today
        )

        # The invoice was paid today, so it should be included
        assert revenue["invoice_count"] == 1
        assert revenue["total_commission_xmr"] == Decimal("5.0")
