"""Tests for background tasks module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from decimal import Decimal
from unittest.mock import MagicMock, patch, AsyncMock

from bot.tasks import cleanup_old_orders, start_background_tasks, check_pending_payments, process_vendor_payouts
from bot.models import Database, Order, Product


class TestTasks:
    """Test background tasks functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock(spec=Database)

    @pytest.mark.asyncio
    async def test_cleanup_old_orders_with_orders(self, mock_db):
        """Test cleanup of old orders."""
        # Create mock old orders
        old_order1 = MagicMock(spec=Order)
        old_order1.created_at = datetime.utcnow() - timedelta(days=40)
        old_order2 = MagicMock(spec=Order)
        old_order2.created_at = datetime.utcnow() - timedelta(days=35)

        # Mock session and query
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[old_order1, old_order2])))
        mock_session.commit = MagicMock()
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.get_settings') as mock_settings:
            mock_settings.return_value.data_retention_days = 30

            await cleanup_old_orders(mock_db)

            # Verify orders were deleted
            assert mock_session.exec.call_count == 2  # One for select, one for delete
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio
    async def test_cleanup_old_orders_no_orders(self, mock_db):
        """Test cleanup when no old orders exist."""
        # Mock session with no results
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=MagicMock(all=MagicMock(return_value=[])))
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.get_settings') as mock_settings:
            mock_settings.return_value.data_retention_days = 30

            await cleanup_old_orders(mock_db)

            # Verify no delete was attempted
            assert mock_session.exec.call_count == 1  # Only select query

    @pytest.mark.asyncio
    async def test_cleanup_old_orders_error(self, mock_db):
        """Test cleanup handles errors gracefully."""
        # Mock session that raises exception
        mock_db.session = MagicMock(side_effect=Exception("Database error"))

        with patch('bot.tasks.get_settings') as mock_settings:
            mock_settings.return_value.data_retention_days = 30

            # Should not raise exception
            await cleanup_old_orders(mock_db)

    @pytest.mark.asyncio
    async def test_check_pending_payments_no_orders(self, mock_db):
        """Test payment check with no pending orders."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.PaymentService') as mock_payment:
            with patch('bot.tasks.PayoutService'):
                await check_pending_payments(mock_db)
                # Should complete without errors
                mock_session.exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_pending_payments_with_paid_order(self, mock_db):
        """Test payment check marks paid orders."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.product_id = 1
        mock_order.vendor_id = 1
        mock_order.quantity = 2
        mock_order.payment_id = "test123"
        mock_order.postage_xmr = Decimal("0.01")
        mock_order.commission_xmr = Decimal("0.005")
        mock_order.state = "NEW"

        mock_product = MagicMock(spec=Product)
        mock_product.price_xmr = Decimal("0.1")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_order])
        mock_session.get = MagicMock(return_value=mock_product)
        mock_session.add = MagicMock()
        mock_session.commit = MagicMock()
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.PaymentService') as mock_payment_cls:
            mock_payment = MagicMock()
            mock_payment.check_paid.return_value = True
            mock_payment_cls.return_value = mock_payment

            with patch('bot.tasks.PayoutService') as mock_payout_cls:
                mock_payout = MagicMock()
                mock_payout_cls.return_value = mock_payout

                await check_pending_payments(mock_db)

                # Verify order was marked paid
                assert mock_order.state == "PAID"
                mock_session.commit.assert_called()
                mock_payout.create_payout.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_pending_payments_error(self, mock_db):
        """Test payment check handles errors gracefully."""
        mock_db.session = MagicMock(side_effect=Exception("Database error"))

        # Should not raise
        await check_pending_payments(mock_db)

    @pytest.mark.asyncio
    async def test_process_vendor_payouts(self, mock_db):
        """Test payout processing."""
        with patch('bot.tasks.PayoutService') as mock_payout_cls:
            mock_payout = MagicMock()
            mock_payout.process_payouts = AsyncMock(return_value={
                'processed': 2,
                'sent': 1,
                'failed': 0,
                'skipped': 1
            })
            mock_payout_cls.return_value = mock_payout

            await process_vendor_payouts(mock_db)

            mock_payout.process_payouts.assert_called_once()

    @pytest.mark.asyncio
    async def test_process_vendor_payouts_error(self, mock_db):
        """Test payout processing handles errors."""
        with patch('bot.tasks.PayoutService') as mock_payout_cls:
            mock_payout = MagicMock()
            mock_payout.process_payouts = AsyncMock(side_effect=Exception("Payout error"))
            mock_payout_cls.return_value = mock_payout

            # Should not raise
            await process_vendor_payouts(mock_db)

    @pytest.mark.asyncio
    async def test_start_background_tasks_normal_operation(self, mock_db):
        """Test background tasks normal operation."""
        call_count = 0

        async def mock_check_payments(db):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()

        with patch('bot.tasks.check_pending_payments', side_effect=mock_check_payments):
            with patch('bot.tasks.process_vendor_payouts', new=AsyncMock()):
                with patch('bot.tasks.cleanup_old_orders', new=AsyncMock()):
                    with patch('asyncio.sleep', return_value=None):
                        await start_background_tasks(mock_db)

                        assert call_count == 2

    @pytest.mark.asyncio
    async def test_start_background_tasks_with_error(self, mock_db):
        """Test background tasks with error recovery."""
        call_count = 0

        async def mock_check_payments(db):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Check error")
            elif call_count >= 2:
                raise asyncio.CancelledError()

        with patch('bot.tasks.check_pending_payments', side_effect=mock_check_payments):
            with patch('bot.tasks.process_vendor_payouts', new=AsyncMock()):
                with patch('bot.tasks.cleanup_old_orders', new=AsyncMock()):
                    with patch('asyncio.sleep', return_value=None) as mock_sleep:
                        await start_background_tasks(mock_db)

                        # Should have called sleep with 300 (5 min) after error
                        mock_sleep.assert_any_call(300)

    @pytest.mark.asyncio
    async def test_start_background_tasks_cancelled(self, mock_db):
        """Test background tasks cancellation."""
        async def mock_check_payments(db):
            raise asyncio.CancelledError()

        with patch('bot.tasks.check_pending_payments', side_effect=mock_check_payments):
            with patch('bot.tasks.process_vendor_payouts', new=AsyncMock()):
                with patch('bot.tasks.cleanup_old_orders', new=AsyncMock()):
                    # Should exit cleanly without raising
                    await start_background_tasks(mock_db)

    @pytest.mark.asyncio
    async def test_check_pending_payments_no_product(self, mock_db):
        """Test payment check when product is not found."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.product_id = 999  # Non-existent product
        mock_order.state = "NEW"

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_order])
        mock_session.get = MagicMock(return_value=None)  # Product not found
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.PaymentService') as mock_payment_cls:
            with patch('bot.tasks.PayoutService'):
                await check_pending_payments(mock_db)
                # Should continue without error when product not found
                mock_session.get.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_pending_payments_not_paid(self, mock_db):
        """Test payment check when payment not received."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.product_id = 1
        mock_order.quantity = 1
        mock_order.payment_id = "test123"
        mock_order.postage_xmr = Decimal("0.01")
        mock_order.state = "NEW"

        mock_product = MagicMock(spec=Product)
        mock_product.price_xmr = Decimal("0.1")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_order])
        mock_session.get = MagicMock(return_value=mock_product)
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.PaymentService') as mock_payment_cls:
            mock_payment = MagicMock()
            mock_payment.check_paid.return_value = False  # Payment not received
            mock_payment_cls.return_value = mock_payment

            with patch('bot.tasks.PayoutService'):
                await check_pending_payments(mock_db)
                # Order state should still be NEW
                assert mock_order.state == "NEW"

    @pytest.mark.asyncio
    async def test_check_pending_payments_order_error(self, mock_db):
        """Test payment check handles individual order errors."""
        mock_order = MagicMock(spec=Order)
        mock_order.id = 1
        mock_order.product_id = 1
        mock_order.state = "NEW"

        mock_product = MagicMock(spec=Product)
        mock_product.price_xmr = Decimal("0.1")

        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[mock_order])
        mock_session.get = MagicMock(return_value=mock_product)
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.tasks.PaymentService') as mock_payment_cls:
            mock_payment = MagicMock()
            mock_payment.check_paid.side_effect = Exception("Payment check error")
            mock_payment_cls.return_value = mock_payment

            with patch('bot.tasks.PayoutService'):
                # Should not raise, just continue
                await check_pending_payments(mock_db)

    @pytest.mark.asyncio
    async def test_process_vendor_payouts_no_pending(self, mock_db):
        """Test payout processing with no pending payouts."""
        with patch('bot.tasks.PayoutService') as mock_payout_cls:
            mock_payout = MagicMock()
            mock_payout.process_payouts = AsyncMock(return_value={
                'processed': 0,
                'sent': 0,
                'failed': 0,
                'skipped': 0
            })
            mock_payout_cls.return_value = mock_payout

            await process_vendor_payouts(mock_db)

            mock_payout.process_payouts.assert_called_once()

    @pytest.mark.asyncio
    async def test_start_background_tasks_periodic_payout(self, mock_db):
        """Test background tasks runs payout every 12 iterations."""
        iteration_count = 0

        async def mock_check_payments(db):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 13:
                raise asyncio.CancelledError()

        payout_called = False

        async def mock_process_payouts(db):
            nonlocal payout_called
            payout_called = True

        with patch('bot.tasks.check_pending_payments', side_effect=mock_check_payments):
            with patch('bot.tasks.process_vendor_payouts', side_effect=mock_process_payouts):
                with patch('bot.tasks.cleanup_old_orders', new=AsyncMock()):
                    with patch('asyncio.sleep', return_value=None):
                        await start_background_tasks(mock_db)

                        # Payout should have been called at iteration 12
                        assert payout_called is True

    @pytest.mark.asyncio
    async def test_start_background_tasks_periodic_cleanup(self, mock_db):
        """Test background tasks runs cleanup every 288 iterations."""
        iteration_count = 0

        async def mock_check_payments(db):
            nonlocal iteration_count
            iteration_count += 1
            if iteration_count >= 289:
                raise asyncio.CancelledError()

        cleanup_called = False

        async def mock_cleanup(db):
            nonlocal cleanup_called
            cleanup_called = True

        with patch('bot.tasks.check_pending_payments', side_effect=mock_check_payments):
            with patch('bot.tasks.process_vendor_payouts', new=AsyncMock()):
                with patch('bot.tasks.cleanup_old_orders', side_effect=mock_cleanup):
                    with patch('asyncio.sleep', return_value=None):
                        await start_background_tasks(mock_db)

                        # Cleanup should have been called at iteration 288
                        assert cleanup_called is True
