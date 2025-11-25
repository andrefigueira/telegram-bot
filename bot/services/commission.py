"""Commission tracking and invoicing service."""

import logging
import secrets
from datetime import datetime, date, timedelta
from decimal import Decimal
from typing import Optional

from bot.models_multitenant import (
    MultiTenantDatabase, CommissionInvoice, InvoiceState, OrderState
)

logger = logging.getLogger(__name__)


class CommissionService:
    """Service for handling commission invoicing and collection."""

    COMMISSION_RATE = Decimal("0.05")  # 5% default
    INVOICE_DUE_DAYS = 7
    SUSPENSION_DAYS = 7
    TERMINATION_DAYS = 14

    def __init__(
        self,
        db: MultiTenantDatabase,
        platform_xmr_address: str
    ):
        self.db = db
        self.platform_xmr_address = platform_xmr_address

    def generate_weekly_invoices(self) -> list[CommissionInvoice]:
        """Generate commission invoices for all tenants (run weekly)."""
        invoices = []
        period_end = date.today()
        period_start = period_end - timedelta(days=7)

        tenants = self.db.get_active_tenants()

        for tenant in tenants:
            invoice = self._generate_invoice_for_tenant(
                tenant.id,
                tenant.commission_rate,
                period_start,
                period_end
            )
            if invoice:
                invoices.append(invoice)
                logger.info(
                    f"Generated invoice for tenant {tenant.id}: "
                    f"{invoice.commission_due_xmr} XMR"
                )

        return invoices

    def _generate_invoice_for_tenant(
        self,
        tenant_id: str,
        commission_rate: Decimal,
        period_start: date,
        period_end: date
    ) -> Optional[CommissionInvoice]:
        """Generate invoice for a single tenant."""
        # Get completed orders for the period
        orders = self.db.get_completed_orders_for_period(
            tenant_id=tenant_id,
            start_date=period_start,
            end_date=period_end
        )

        if not orders:
            return None

        total_sales = sum(o.total_xmr for o in orders)
        commission_due = total_sales * commission_rate

        if commission_due <= Decimal("0"):
            return None

        # Generate unique payment address (subaddress of platform wallet)
        # In production, this would call the Monero RPC
        payment_address = self.platform_xmr_address

        due_date = datetime.utcnow() + timedelta(days=self.INVOICE_DUE_DAYS)

        invoice = self.db.create_commission_invoice(
            tenant_id=tenant_id,
            period_start=period_start,
            period_end=period_end,
            order_count=len(orders),
            total_sales_xmr=total_sales,
            commission_rate=commission_rate,
            commission_due_xmr=commission_due,
            payment_address=payment_address,
            due_date=due_date
        )

        self.db.log_action(
            action="invoice_generated",
            tenant_id=tenant_id,
            details=f'{{"invoice_id": {invoice.id}, "amount": "{commission_due}"}}'
        )

        return invoice

    def get_invoice(self, invoice_id: int) -> Optional[CommissionInvoice]:
        """Get invoice by ID."""
        with self.db.get_session() as session:
            return session.get(CommissionInvoice, invoice_id)

    def get_tenant_invoices(
        self,
        tenant_id: str,
        state: Optional[InvoiceState] = None
    ) -> list[CommissionInvoice]:
        """Get invoices for a tenant."""
        from sqlmodel import select
        with self.db.get_session() as session:
            statement = select(CommissionInvoice).where(
                CommissionInvoice.tenant_id == tenant_id
            )
            if state:
                statement = statement.where(CommissionInvoice.state == state)
            statement = statement.order_by(CommissionInvoice.created_at.desc())
            return list(session.exec(statement).all())

    def check_payment(
        self,
        invoice_id: int,
        received_amount: Decimal
    ) -> bool:
        """Check if invoice payment has been received."""
        invoice = self.get_invoice(invoice_id)
        if not invoice:
            return False

        if received_amount >= invoice.commission_due_xmr:
            self.db.mark_invoice_paid(invoice_id)
            self.db.log_action(
                action="invoice_paid",
                tenant_id=invoice.tenant_id,
                details=f'{{"invoice_id": {invoice_id}, "amount": "{received_amount}"}}'
            )
            logger.info(f"Invoice {invoice_id} marked as paid")
            return True

        return False

    def process_overdue_invoices(self) -> dict:
        """Process overdue invoices (run daily)."""
        results = {
            "marked_overdue": 0,
            "suspended": 0,
            "terminated": 0
        }

        pending_invoices = self.db.get_pending_invoices()

        for invoice in pending_invoices:
            if datetime.utcnow() > invoice.due_date:
                self.db.mark_invoice_overdue(invoice.id)
                results["marked_overdue"] += 1
                logger.warning(
                    f"Invoice {invoice.id} marked overdue for tenant {invoice.tenant_id}"
                )

        overdue_invoices = self.db.get_overdue_invoices()

        for invoice in overdue_invoices:
            days_overdue = (datetime.utcnow() - invoice.due_date).days

            if days_overdue >= self.TERMINATION_DAYS:
                # Terminate account
                self.db.update_tenant(invoice.tenant_id, bot_active=False)
                results["terminated"] += 1
                self.db.log_action(
                    action="tenant_terminated_nonpayment",
                    tenant_id=invoice.tenant_id,
                    details=f'{{"invoice_id": {invoice.id}, "days_overdue": {days_overdue}}}'
                )
                logger.error(
                    f"Tenant {invoice.tenant_id} terminated for non-payment"
                )

            elif days_overdue >= self.SUSPENSION_DAYS:
                # Suspend bot
                self.db.update_tenant(invoice.tenant_id, bot_active=False)
                results["suspended"] += 1
                self.db.log_action(
                    action="tenant_suspended_nonpayment",
                    tenant_id=invoice.tenant_id,
                    details=f'{{"invoice_id": {invoice.id}, "days_overdue": {days_overdue}}}'
                )
                logger.warning(
                    f"Tenant {invoice.tenant_id} suspended for non-payment"
                )

        return results

    def waive_invoice(self, invoice_id: int, reason: str) -> bool:
        """Waive an invoice (admin action)."""
        with self.db.get_session() as session:
            invoice = session.get(CommissionInvoice, invoice_id)
            if not invoice:
                return False

            invoice.state = InvoiceState.WAIVED
            session.add(invoice)
            session.commit()

            self.db.log_action(
                action="invoice_waived",
                tenant_id=invoice.tenant_id,
                details=f'{{"invoice_id": {invoice_id}, "reason": "{reason}"}}'
            )
            logger.info(f"Invoice {invoice_id} waived: {reason}")
            return True

    def calculate_platform_revenue(
        self,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> dict:
        """Calculate platform revenue from commissions."""
        from sqlmodel import select
        with self.db.get_session() as session:
            statement = select(CommissionInvoice).where(
                CommissionInvoice.state == InvoiceState.PAID
            )

            if start_date:
                statement = statement.where(
                    CommissionInvoice.paid_at >= datetime.combine(
                        start_date, datetime.min.time()
                    )
                )
            if end_date:
                statement = statement.where(
                    CommissionInvoice.paid_at <= datetime.combine(
                        end_date, datetime.max.time()
                    )
                )

            invoices = list(session.exec(statement).all())

            total_revenue = sum(i.commission_due_xmr for i in invoices)
            total_sales = sum(i.total_sales_xmr for i in invoices)

            return {
                "invoice_count": len(invoices),
                "total_commission_xmr": total_revenue,
                "total_sales_volume_xmr": total_sales,
                "average_commission_rate": (
                    total_revenue / total_sales if total_sales > 0 else Decimal("0")
                )
            }
