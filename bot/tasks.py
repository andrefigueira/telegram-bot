"""Background tasks for maintenance."""

import asyncio
import logging
from datetime import datetime, timedelta
from decimal import Decimal

from sqlmodel import select, delete
from .models import Database, Order, Product
from .config import get_settings
from .services.payout import PayoutService
from .services.payments import PaymentService

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


async def check_pending_payments(db: Database) -> None:
    """Check pending orders for received payments."""
    try:
        payment_service = PaymentService()
        payout_service = PayoutService(db)

        with db.session() as session:
            # Find orders awaiting payment (NEW state)
            statement = select(Order).where(Order.state == "NEW")
            pending_orders = list(session.exec(statement))

            if not pending_orders:
                logger.debug("No pending orders to check")
                return

            logger.info(f"Checking {len(pending_orders)} pending orders for payments")

            for order in pending_orders:
                try:
                    # Get product to calculate expected amount
                    product = session.get(Product, order.product_id)
                    if not product:
                        continue

                    # Calculate expected total
                    price_xmr = Decimal(str(product.price_xmr))
                    expected_amount = price_xmr * order.quantity + order.postage_xmr

                    # Check if payment received
                    if payment_service.check_paid(order.payment_id, expected_amount):
                        # Update order state
                        order.state = "PAID"
                        session.add(order)
                        session.commit()

                        logger.info(f"Order #{order.id} marked as PAID")

                        # Create payout record for vendor
                        vendor_share = expected_amount - order.commission_xmr
                        payout_service.create_payout(order.id, order.vendor_id, vendor_share)

                except Exception as e:
                    logger.error(f"Error checking order #{order.id}: {e}")
                    continue

    except Exception as e:
        logger.error(f"Error checking pending payments: {e}", exc_info=True)


async def process_vendor_payouts(db: Database) -> None:
    """Process pending payouts to vendor wallets."""
    try:
        payout_service = PayoutService(db)
        results = await payout_service.process_payouts()

        if results['processed'] > 0:
            logger.info(
                f"Payout processing complete: "
                f"sent={results['sent']}, failed={results['failed']}, skipped={results['skipped']}"
            )
        else:
            logger.debug("No pending payouts to process")

    except Exception as e:
        logger.error(f"Error processing payouts: {e}", exc_info=True)


async def start_background_tasks(db: Database) -> None:
    """Start all background tasks."""
    logger.info("Starting background tasks")

    iteration = 0

    while True:
        try:
            iteration += 1

            # Check payments every iteration (every 5 minutes)
            await check_pending_payments(db)

            # Process payouts every 12 iterations (every hour)
            if iteration % 12 == 0:
                await process_vendor_payouts(db)

            # Run cleanup every 288 iterations (every 24 hours)
            if iteration % 288 == 0:
                await cleanup_old_orders(db)
                iteration = 0  # Reset to prevent overflow

            await asyncio.sleep(300)  # 5 minutes
        except asyncio.CancelledError:
            logger.info("Background tasks cancelled")
            break
        except Exception as e:
            logger.error(f"Error in background tasks: {e}", exc_info=True)
            await asyncio.sleep(300)  # Retry after 5 minutes on error