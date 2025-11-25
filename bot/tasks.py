"""Background tasks for maintenance."""

import asyncio
import logging
from datetime import datetime, timedelta

from sqlmodel import select, delete
from .models import Database, Order
from .config import get_settings

logger = logging.getLogger(__name__)


async def cleanup_old_orders(db: Database) -> None:
    """Delete orders older than retention period."""
    settings = get_settings()
    cutoff_date = datetime.utcnow() - timedelta(days=settings.data_retention_days)
    
    try:
        with db.session() as session:
            # Find old orders
            statement = select(Order).where(Order.created_at < cutoff_date)
            old_orders = session.exec(statement).all()
            
            if old_orders:
                # Delete old orders
                delete_statement = delete(Order).where(Order.created_at < cutoff_date)
                session.exec(delete_statement)
                session.commit()
                logger.info(f"Deleted {len(old_orders)} old orders")
            else:
                logger.debug("No old orders to delete")
                
    except Exception as e:
        logger.error(f"Error cleaning up old orders: {e}", exc_info=True)


async def start_background_tasks(db: Database) -> None:
    """Start all background tasks."""
    logger.info("Starting background tasks")
    
    while True:
        try:
            # Run cleanup daily
            await cleanup_old_orders(db)
            await asyncio.sleep(86400)  # 24 hours
        except asyncio.CancelledError:
            logger.info("Background tasks cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background tasks: {e}", exc_info=True)
            await asyncio.sleep(3600)  # Retry after 1 hour on error