"""Main bot application."""

import asyncio
import logging
import signal
import sys
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    Application,
    filters,
)

from .config import get_settings
from .models import Database
from .services.catalog import CatalogService
from .services.orders import OrderService
from .services.payments import PaymentService
from .services.vendors import VendorService
from .services.postage import PostageService
from .services.payout import PayoutService
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
    postage = PostageService(db)
    payout = PayoutService(db)

    # Build application
    application = ApplicationBuilder().token(settings.telegram_token).build()

    # Add error handler
    application.add_error_handler(error_handler)

    # Command handlers
    application.add_handler(CommandHandler("start", user.start))
    application.add_handler(CommandHandler("help", user.help_command))
    application.add_handler(CommandHandler("setup", user.setup_command))
    application.add_handler(CommandHandler("list", lambda u, c: user.list_products(u, c, catalog)))
    application.add_handler(CommandHandler("products", lambda u, c: user.list_products(u, c, catalog)))
    application.add_handler(CommandHandler("order", lambda u, c: user.order(u, c, orders)))
    application.add_handler(CommandHandler("orders", lambda u, c: user.orders_list(u, c, orders)))
    application.add_handler(CommandHandler("status", lambda u, c: user.order_status(u, c, orders)))

    # Admin command handlers
    application.add_handler(CommandHandler("add", lambda u, c: admin.add(u, c, catalog, vendors)))
    application.add_handler(CommandHandler("addvendor", lambda u, c: admin.add_vendor(u, c, vendors)))
    application.add_handler(CommandHandler("vendors", lambda u, c: admin.list_vendors(u, c, vendors)))
    application.add_handler(CommandHandler("commission", lambda u, c: admin.set_commission(u, c, vendors)))

    # Callback query handlers for button interactions
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_menu_callback(u, c, catalog),
        pattern=r"^menu:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_setup_callback(u, c, vendors, postage),
        pattern=r"^setup:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_payment_toggle_callback(u, c, vendors),
        pattern=r"^pay:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_currency_callback(u, c, vendors),
        pattern=r"^currency:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_postage_callback(u, c, vendors, postage),
        pattern=r"^postage:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_products_callback(u, c, catalog),
        pattern=r"^products:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_product_callback(u, c, catalog),
        pattern=r"^product:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: user.handle_order_callback(u, c, orders, catalog, postage, vendors),
        pattern=r"^order:"
    ))

    # Admin/Vendor callback handlers
    application.add_handler(CallbackQueryHandler(
        lambda u, c: admin.handle_admin_callback(u, c, catalog, vendors),
        pattern=r"^admin:"
    ))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: admin.handle_vendor_callback(u, c, catalog, vendors),
        pattern=r"^vendor:"
    ))

    # Vendor order management
    application.add_handler(CallbackQueryHandler(
        lambda u, c: admin.handle_vendor_order_callback(u, c, orders, vendors),
        pattern=r"^vorder:"
    ))

    # Super admin handlers
    application.add_handler(CommandHandler("superadmin", admin.super_admin_command))
    application.add_handler(CallbackQueryHandler(
        lambda u, c: admin.handle_super_admin_callback(u, c, payout),
        pattern=r"^sadmin:"
    ))

    # Message handler for text input (setup flows, delivery address, product creation)
    async def handle_all_text_input(update, context):
        # Try admin text input first (for product creation/editing)
        await admin.handle_admin_text_input(update, context, catalog, vendors)
        # Then user text input (for setup flows, delivery address)
        await user.handle_text_input(update, context, orders, catalog, vendors, postage)

    application.add_handler(MessageHandler(
        filters.TEXT & ~filters.COMMAND,
        handle_all_text_input
    ))

    # Store services in application context
    application.bot_data["db"] = db
    application.bot_data["catalog"] = catalog
    application.bot_data["orders"] = orders
    application.bot_data["postage"] = postage
    application.bot_data["payout_service"] = payout
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
