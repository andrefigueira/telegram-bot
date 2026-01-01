"""Tests for multi-tenant background tasks."""

import pytest
import asyncio
from decimal import Decimal
from datetime import datetime
from unittest.mock import MagicMock, AsyncMock, patch

from bot.tasks_multitenant import BackgroundTaskManager


class TestBackgroundTaskManagerInit:
    """Test BackgroundTaskManager initialization."""

    def test_init(self):
        """Test manager initialization."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        manager = BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service,
            platform_monero_rpc="http://localhost:18081"
        )

        assert manager.db == mock_db
        assert manager.order_service == mock_order_service
        assert manager.commission_service == mock_commission_service
        assert manager.platform_monero_rpc == "http://localhost:18081"
        assert manager._running is False
        assert manager._tasks == []

    def test_init_no_rpc(self):
        """Test manager initialization without RPC."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        manager = BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

        assert manager.platform_monero_rpc is None


class TestBackgroundTaskManagerStartStop:
    """Test start and stop functionality."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_start_creates_tasks(self, manager):
        """Test that start creates background tasks."""
        # Mock the loop methods to exit immediately
        manager._swap_checker_loop = AsyncMock()
        manager._commission_payment_checker_loop = AsyncMock()
        manager._invoice_generator_loop = AsyncMock()
        manager._overdue_processor_loop = AsyncMock()

        await manager.start()

        assert manager._running is True
        assert len(manager._tasks) == 4

        # Clean up
        await manager.stop()

    @pytest.mark.asyncio
    async def test_start_already_running(self, manager):
        """Test that start does nothing if already running."""
        manager._running = True

        await manager.start()

        # Should not create new tasks
        assert len(manager._tasks) == 0

    @pytest.mark.asyncio
    async def test_stop_cancels_tasks(self, manager):
        """Test that stop cancels all tasks."""
        # Create mock tasks
        mock_task1 = MagicMock()
        mock_task2 = MagicMock()
        manager._tasks = [mock_task1, mock_task2]
        manager._running = True

        with patch('bot.tasks_multitenant.asyncio.gather', new_callable=AsyncMock):
            await manager.stop()

        assert manager._running is False
        assert manager._tasks == []
        mock_task1.cancel.assert_called_once()
        mock_task2.cancel.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_not_running(self, manager):
        """Test that stop does nothing if not running."""
        manager._running = False

        await manager.stop()

        # Should return immediately
        assert manager._running is False


class TestSwapCheckerLoop:
    """Test swap checker loop."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = AsyncMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_swap_checker_processes_swaps(self, manager):
        """Test swap checker processes pending swaps."""
        manager._running = True

        # Make it exit after one iteration
        call_count = 0
        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.order_service.process_pending_swaps.return_value = {
            "checked": 5,
            "completed": 2,
            "failed": 1
        }

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            await manager._swap_checker_loop()

        manager.order_service.process_pending_swaps.assert_called_once()

    @pytest.mark.asyncio
    async def test_swap_checker_handles_exception(self, manager):
        """Test swap checker handles exceptions."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.order_service.process_pending_swaps.side_effect = Exception("Test error")

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            # Should not raise
            await manager._swap_checker_loop()

    @pytest.mark.asyncio
    async def test_swap_checker_no_log_on_zero(self, manager):
        """Test swap checker doesn't log when no changes."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.order_service.process_pending_swaps.return_value = {
            "checked": 5,
            "completed": 0,
            "failed": 0
        }

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            await manager._swap_checker_loop()


class TestCommissionPaymentCheckerLoop:
    """Test commission payment checker loop."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_commission_checker_processes_invoices(self, manager):
        """Test commission checker processes pending invoices."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.db.get_pending_invoices.return_value = [
            MagicMock(id=1, payment_id="pay1"),
            MagicMock(id=2, payment_id="pay2")
        ]

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            await manager._commission_payment_checker_loop()

        manager.db.get_pending_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_commission_checker_handles_exception(self, manager):
        """Test commission checker handles exceptions."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.db.get_pending_invoices.side_effect = Exception("Database error")

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            # Should not raise
            await manager._commission_payment_checker_loop()


class TestCheckCommissionPayments:
    """Test _check_commission_payments method."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_check_commission_payments_empty(self, manager):
        """Test checking payments with no pending invoices."""
        manager.db.get_pending_invoices.return_value = []

        await manager._check_commission_payments()

        manager.db.get_pending_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_commission_payments_with_invoices(self, manager):
        """Test checking payments with pending invoices."""
        mock_invoice = MagicMock(id=1, payment_id="pay1")
        manager.db.get_pending_invoices.return_value = [mock_invoice]

        await manager._check_commission_payments()

        manager.db.get_pending_invoices.assert_called_once()


class TestInvoiceGeneratorLoop:
    """Test invoice generator loop."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_invoice_generator_on_sunday(self, manager):
        """Test invoice generator generates on Sunday."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.generate_weekly_invoices.return_value = [
            MagicMock(id=1),
            MagicMock(id=2)
        ]

        # Mock Sunday
        mock_datetime = MagicMock()
        mock_datetime.utcnow.return_value.weekday.return_value = 6

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            with patch('bot.tasks_multitenant.datetime', mock_datetime):
                await manager._invoice_generator_loop()

        manager.commission_service.generate_weekly_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_invoice_generator_not_sunday(self, manager):
        """Test invoice generator skips on non-Sunday."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        # Mock Monday (weekday=0)
        mock_datetime = MagicMock()
        mock_datetime.utcnow.return_value.weekday.return_value = 0

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            with patch('bot.tasks_multitenant.datetime', mock_datetime):
                await manager._invoice_generator_loop()

        manager.commission_service.generate_weekly_invoices.assert_not_called()

    @pytest.mark.asyncio
    async def test_invoice_generator_empty_invoices(self, manager):
        """Test invoice generator with no invoices generated."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.generate_weekly_invoices.return_value = []

        mock_datetime = MagicMock()
        mock_datetime.utcnow.return_value.weekday.return_value = 6

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            with patch('bot.tasks_multitenant.datetime', mock_datetime):
                await manager._invoice_generator_loop()

    @pytest.mark.asyncio
    async def test_invoice_generator_handles_exception(self, manager):
        """Test invoice generator handles exceptions."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.generate_weekly_invoices.side_effect = Exception("Error")

        mock_datetime = MagicMock()
        mock_datetime.utcnow.return_value.weekday.return_value = 6

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            with patch('bot.tasks_multitenant.datetime', mock_datetime):
                # Should not raise
                await manager._invoice_generator_loop()


class TestOverdueProcessorLoop:
    """Test overdue processor loop."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = MagicMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_overdue_processor_with_results(self, manager):
        """Test overdue processor with results."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.process_overdue_invoices.return_value = {
            "marked_overdue": 3,
            "suspended": 1,
            "terminated": 0
        }

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            await manager._overdue_processor_loop()

        manager.commission_service.process_overdue_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_overdue_processor_no_results(self, manager):
        """Test overdue processor with no results."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.process_overdue_invoices.return_value = {
            "marked_overdue": 0,
            "suspended": 0,
            "terminated": 0
        }

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            await manager._overdue_processor_loop()

    @pytest.mark.asyncio
    async def test_overdue_processor_handles_exception(self, manager):
        """Test overdue processor handles exceptions."""
        manager._running = True
        call_count = 0

        async def controlled_sleep(seconds):
            nonlocal call_count
            call_count += 1
            if call_count >= 1:
                manager._running = False

        manager.commission_service.process_overdue_invoices.side_effect = Exception("Error")

        with patch('bot.tasks_multitenant.asyncio.sleep', controlled_sleep):
            # Should not raise
            await manager._overdue_processor_loop()


class TestRunOnceMethods:
    """Test run_once methods."""

    @pytest.fixture
    def manager(self):
        """Create a manager instance."""
        mock_db = MagicMock()
        mock_order_service = AsyncMock()
        mock_commission_service = MagicMock()

        return BackgroundTaskManager(
            db=mock_db,
            order_service=mock_order_service,
            commission_service=mock_commission_service
        )

    @pytest.mark.asyncio
    async def test_run_once_swap_check(self, manager):
        """Test run_once_swap_check."""
        expected_result = {"checked": 5, "completed": 2, "failed": 0}
        manager.order_service.process_pending_swaps.return_value = expected_result

        result = await manager.run_once_swap_check()

        assert result == expected_result
        manager.order_service.process_pending_swaps.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_once_invoice_generation(self, manager):
        """Test run_once_invoice_generation."""
        expected_invoices = [MagicMock(id=1), MagicMock(id=2)]
        manager.commission_service.generate_weekly_invoices.return_value = expected_invoices

        result = await manager.run_once_invoice_generation()

        assert result == expected_invoices
        manager.commission_service.generate_weekly_invoices.assert_called_once()

    @pytest.mark.asyncio
    async def test_run_once_overdue_processing(self, manager):
        """Test run_once_overdue_processing."""
        expected_result = {"marked_overdue": 2, "suspended": 1, "terminated": 0}
        manager.commission_service.process_overdue_invoices.return_value = expected_result

        result = await manager.run_once_overdue_processing()

        assert result == expected_result
        manager.commission_service.process_overdue_invoices.assert_called_once()
