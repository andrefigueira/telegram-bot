"""Tests for error handler module."""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from telegram import Update, Message
from telegram.ext import ContextTypes

from bot.error_handler import error_handler, handle_errors, RetryableError, retry_on_error


class TestErrorHandler:
    """Test error handling functionality."""

    @pytest.mark.asyncio
    async def test_error_handler_with_update(self):
        """Test global error handler with update."""
        # Mock update and context
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.effective_message = message
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = Exception("Test error")
        
        # Call error handler
        await error_handler(update, context)
        
        # Verify error message was sent
        message.reply_text.assert_called_once_with(
            "Sorry, an error occurred while processing your request. Please try again later."
        )

    @pytest.mark.asyncio
    async def test_error_handler_without_update(self):
        """Test global error handler without update."""
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = Exception("Test error")
        
        # Should not raise exception
        await error_handler(None, context)

    @pytest.mark.asyncio
    async def test_error_handler_reply_fails(self):
        """Test global error handler when reply fails."""
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock(side_effect=Exception("Reply failed"))
        update.effective_message = message
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        context.error = Exception("Test error")
        
        # Should not raise exception even if reply fails
        await error_handler(update, context)

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_success(self):
        """Test handle_errors decorator with successful function."""
        @handle_errors
        async def test_func(update, context):
            return "success"
        
        update = MagicMock(spec=Update)
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        result = await test_func(update, context)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_with_exception(self):
        """Test handle_errors decorator with exception."""
        @handle_errors
        async def test_func(update, context):
            raise ValueError("Test error")
        
        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        message.reply_text = AsyncMock()
        update.effective_message = message
        
        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)
        
        with pytest.raises(ValueError):
            await test_func(update, context)
        
        message.reply_text.assert_called_once_with(
            "An error occurred. Please try again or contact support."
        )

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_no_update(self):
        """Test handle_errors decorator without update."""
        @handle_errors
        async def test_func(update, context):
            raise ValueError("Test error")

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        with pytest.raises(ValueError):
            await test_func(None, context)

    @pytest.mark.asyncio
    async def test_handle_errors_decorator_reply_fails(self):
        """Test handle_errors decorator when reply_text fails."""
        @handle_errors
        async def test_func(update, context):
            raise ValueError("Test error")

        update = MagicMock(spec=Update)
        message = MagicMock(spec=Message)
        # Make reply_text raise an exception
        message.reply_text = AsyncMock(side_effect=Exception("Reply failed"))
        update.effective_message = message

        context = MagicMock(spec=ContextTypes.DEFAULT_TYPE)

        # Should still raise the original ValueError, not the reply exception
        with pytest.raises(ValueError, match="Test error"):
            await test_func(update, context)

    @pytest.mark.asyncio
    async def test_retry_on_error_success(self):
        """Test retry_on_error with successful function."""
        async def test_func():
            return "success"
        
        result = await retry_on_error(test_func, max_retries=3, delay=0)
        assert result == "success"

    @pytest.mark.asyncio
    async def test_retry_on_error_with_retries(self):
        """Test retry_on_error with retries."""
        call_count = 0
        
        async def test_func():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise RetryableError("Retry me")
            return "success"
        
        result = await retry_on_error(test_func, max_retries=3, delay=0)
        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_retry_on_error_max_retries_exceeded(self):
        """Test retry_on_error when max retries exceeded."""
        async def test_func():
            raise RetryableError("Always fails")
        
        with pytest.raises(RetryableError):
            await retry_on_error(test_func, max_retries=2, delay=0)