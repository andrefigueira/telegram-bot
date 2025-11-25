"""Tests for background tasks module."""

import pytest
import asyncio
from datetime import datetime, timedelta
from unittest.mock import MagicMock, patch

from bot.tasks import cleanup_old_orders, start_background_tasks
from bot.models import Database, Order


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
    async def test_start_background_tasks_normal_operation(self, mock_db):
        """Test background tasks normal operation."""
        call_count = 0
        
        async def mock_cleanup(db):
            nonlocal call_count
            call_count += 1
            if call_count >= 2:
                raise asyncio.CancelledError()
        
        with patch('bot.tasks.cleanup_old_orders', side_effect=mock_cleanup):
            with patch('asyncio.sleep', return_value=None):
                with pytest.raises(asyncio.CancelledError):
                    await start_background_tasks(mock_db)
                
                assert call_count == 2

    @pytest.mark.asyncio
    async def test_start_background_tasks_with_error(self, mock_db):
        """Test background tasks with error recovery."""
        call_count = 0
        
        async def mock_cleanup(db):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise Exception("Cleanup error")
            elif call_count >= 2:
                raise asyncio.CancelledError()
        
        with patch('bot.tasks.cleanup_old_orders', side_effect=mock_cleanup):
            with patch('asyncio.sleep', return_value=None) as mock_sleep:
                with pytest.raises(asyncio.CancelledError):
                    await start_background_tasks(mock_db)
                
                # Should have called sleep with 3600 (1 hour) after error
                mock_sleep.assert_any_call(3600)

    @pytest.mark.asyncio
    async def test_start_background_tasks_cancelled(self, mock_db):
        """Test background tasks cancellation."""
        async def mock_cleanup(db):
            raise asyncio.CancelledError()
        
        with patch('bot.tasks.cleanup_old_orders', side_effect=mock_cleanup):
            # Should exit cleanly without raising
            await start_background_tasks(mock_db)