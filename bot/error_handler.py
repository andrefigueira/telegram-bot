"""Error handling utilities."""

import logging
import traceback
from functools import wraps
from typing import Callable, Any

from telegram import Update
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)


async def error_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Global error handler for the bot."""
    logger.error(f"Exception while handling an update: {context.error}")
    
    # Log the full traceback
    tb_list = traceback.format_exception(
        None, context.error, context.error.__traceback__
    )
    tb_string = "".join(tb_list)
    logger.error(f"Traceback:\n{tb_string}")
    
    # Notify user about the error (if possible)
    if update and update.effective_message:
        try:
            await update.effective_message.reply_text(
                "Sorry, an error occurred while processing your request. Please try again later."
            )
        except Exception as e:
            logger.error(f"Failed to send error message to user: {e}")


def handle_errors(func: Callable) -> Callable:
    """Decorator to handle errors in handler functions."""
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args: Any, **kwargs: Any) -> Any:
        try:
            return await func(update, context, *args, **kwargs)
        except Exception as e:
            logger.error(f"Error in {func.__name__}: {e}", exc_info=True)
            if update and update.effective_message:
                try:
                    await update.effective_message.reply_text(
                        "An error occurred. Please try again or contact support."
                    )
                except Exception:
                    pass
            raise
    return wrapper


class RetryableError(Exception):
    """Error that should trigger a retry."""
    pass


async def retry_on_error(
    func: Callable,
    max_retries: int = 3,
    delay: int = 1,
    *args: Any,
    **kwargs: Any
) -> Any:
    """Retry a function on error with exponential backoff."""
    import asyncio
    
    last_error = None
    for attempt in range(max_retries):
        try:
            return await func(*args, **kwargs)
        except RetryableError as e:
            last_error = e
            if attempt < max_retries - 1:
                wait_time = delay * (2 ** attempt)
                logger.warning(
                    f"Attempt {attempt + 1} failed, retrying in {wait_time}s: {e}"
                )
                await asyncio.sleep(wait_time)
            else:
                logger.error(f"All {max_retries} attempts failed")
    
    raise last_error