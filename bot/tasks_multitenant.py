"""Background tasks for multi-tenant platform."""

import asyncio
import logging
from datetime import datetime, timedelta
from typing import Optional

from bot.models_multitenant import MultiTenantDatabase
from bot.services.commission import CommissionService
from bot.services.multicrypto_orders import MultiCryptoOrderService
from bot.services.crypto_swap import CryptoSwapService

logger = logging.getLogger(__name__)


class BackgroundTaskManager:
    """Manages background tasks for the multi-tenant platform."""

    def __init__(
        self,
        db: MultiTenantDatabase,
        order_service: MultiCryptoOrderService,
        commission_service: CommissionService,
        platform_monero_rpc: Optional[str] = None
    ):
        self.db = db
        self.order_service = order_service
        self.commission_service = commission_service
        self.platform_monero_rpc = platform_monero_rpc
        self._running = False
        self._tasks: list[asyncio.Task] = []

    async def start(self):
        """Start all background tasks."""
        if self._running:
            logger.warning("Background tasks already running")
            return

        self._running = True
        logger.info("Starting background tasks")

        # Start task loops
        self._tasks = [
            asyncio.create_task(self._swap_checker_loop()),
            asyncio.create_task(self._commission_payment_checker_loop()),
            asyncio.create_task(self._invoice_generator_loop()),
            asyncio.create_task(self._overdue_processor_loop()),
        ]

        logger.info(f"Started {len(self._tasks)} background tasks")

    async def stop(self):
        """Stop all background tasks."""
        if not self._running:
            return

        self._running = False
        logger.info("Stopping background tasks")

        for task in self._tasks:
            task.cancel()

        await asyncio.gather(*self._tasks, return_exceptions=True)
        self._tasks = []
        logger.info("Background tasks stopped")

    async def _swap_checker_loop(self):
        """Check pending swaps every 30 seconds."""
        while self._running:
            try:
                results = await self.order_service.process_pending_swaps()
                if results["completed"] > 0 or results["failed"] > 0:
                    logger.info(
                        f"Swap check: {results['checked']} checked, "
                        f"{results['completed']} completed, {results['failed']} failed"
                    )
            except Exception as e:
                logger.error(f"Error in swap checker: {e}")

            await asyncio.sleep(30)

    async def _commission_payment_checker_loop(self):
        """Check commission payments every hour."""
        while self._running:
            try:
                await self._check_commission_payments()
            except Exception as e:
                logger.error(f"Error in commission payment checker: {e}")

            await asyncio.sleep(3600)  # 1 hour

    async def _check_commission_payments(self):
        """Check if any commission invoices have been paid."""
        pending_invoices = self.db.get_pending_invoices()

        for invoice in pending_invoices:
            # In production, check Monero RPC for payment
            # For now, this is a placeholder
            # received = await self._check_monero_payment(invoice.payment_id)
            # if received >= invoice.commission_due_xmr:
            #     self.commission_service.check_payment(invoice.id, received)
            pass

        logger.debug(f"Checked {len(pending_invoices)} pending commission invoices")

    async def _invoice_generator_loop(self):
        """Generate weekly invoices (runs daily, generates on Sunday)."""
        while self._running:
            try:
                # Check if today is Sunday
                if datetime.utcnow().weekday() == 6:  # Sunday
                    invoices = self.commission_service.generate_weekly_invoices()
                    if invoices:
                        logger.info(f"Generated {len(invoices)} commission invoices")
            except Exception as e:
                logger.error(f"Error in invoice generator: {e}")

            # Sleep until next day
            await asyncio.sleep(86400)  # 24 hours

    async def _overdue_processor_loop(self):
        """Process overdue invoices daily."""
        while self._running:
            try:
                results = self.commission_service.process_overdue_invoices()
                if any(results.values()):
                    logger.info(
                        f"Overdue processing: {results['marked_overdue']} marked overdue, "
                        f"{results['suspended']} suspended, {results['terminated']} terminated"
                    )
            except Exception as e:
                logger.error(f"Error in overdue processor: {e}")

            await asyncio.sleep(86400)  # 24 hours

    async def run_once_swap_check(self):
        """Run swap check once (for testing/manual trigger)."""
        return await self.order_service.process_pending_swaps()

    async def run_once_invoice_generation(self):
        """Run invoice generation once (for testing/manual trigger)."""
        return self.commission_service.generate_weekly_invoices()

    async def run_once_overdue_processing(self):
        """Run overdue processing once (for testing/manual trigger)."""
        return self.commission_service.process_overdue_invoices()
