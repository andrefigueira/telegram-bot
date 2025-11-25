"""Main bot application."""

import asyncio
import logging
import signal
import sys
from telegram.ext import ApplicationBuilder, CommandHandler, Application

from .config import get_settings
from .models import Database
from .services.catalog import CatalogService
from .services.orders import OrderService
from .services.payments import PaymentService
from .services.vendors import VendorService
from .handlers import admin, user
from .logging_config import setup_logging
from .error_handler import error_handler
from .health import HealthCheckServer
from .tasks import start_background_tasks

logger = logging.getLogger(__name__)


def build_app() -> Application:
    settings = get_settings()
    
    # Setup logging
    setup_logging(settings.log_level, settings.log_file)
    
    logger.info(f"Starting bot in {settings.environment} environment")
    
    # Initialize database
    db = Database(settings.database_url)
    
    # Initialize services
    vendors = VendorService(db)
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    
    # Build application
    application = ApplicationBuilder().token(settings.telegram_token).build()
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Add command handlers
    application.add_handler(CommandHandler("start", user.start))
    application.add_handler(CommandHandler("list", lambda u, c: user.list_products(u, c, catalog)))
    application.add_handler(CommandHandler("order", lambda u, c: user.order(u, c, orders)))
    application.add_handler(CommandHandler("add", lambda u, c: admin.add(u, c, catalog, vendors)))
    application.add_handler(CommandHandler("addvendor", lambda u, c: admin.add_vendor(u, c, vendors)))
    application.add_handler(CommandHandler("vendors", lambda u, c: admin.list_vendors(u, c, vendors)))
    application.add_handler(CommandHandler("commission", lambda u, c: admin.set_commission(u, c, vendors)))
    
    # Store services in application context
    application.bot_data["db"] = db
    application.bot_data["health_server"] = HealthCheckServer(db)
    
    return application


async def post_init(application: Application) -> None:
    """Initialize services after the bot starts."""
    # Start health check server
    health_server = application.bot_data["health_server"]
    await health_server.start()
    
    # Start background tasks
    db = application.bot_data["db"]
    asyncio.create_task(start_background_tasks(db))
    
    logger.info("Bot initialization complete")


async def post_shutdown(application: Application) -> None:
    """Clean up resources on shutdown."""
    logger.info("Shutting down bot...")
    
    # Stop health check server
    health_server = application.bot_data["health_server"]
    await health_server.stop()
    
    logger.info("Bot shutdown complete")


def handle_signal(signum, frame):
    """Handle shutdown signals gracefully."""
    logger.info(f"Received signal {signum}")
    sys.exit(0)


def main() -> None:
    """Main entry point."""
    # Set up signal handlers
    signal.signal(signal.SIGINT, handle_signal)
    signal.signal(signal.SIGTERM, handle_signal)
    
    # Build and run application
    app = build_app()
    app.post_init = post_init
    app.post_shutdown = post_shutdown
    
    try:
        app.run_polling(drop_pending_updates=True)
    except Exception as e:
        logger.error(f"Fatal error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":  # pragma: no cover
    main()
