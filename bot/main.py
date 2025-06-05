"""Main bot application."""

from telegram.ext import ApplicationBuilder, CommandHandler

from .config import get_settings
from .models import Database
from .services.catalog import CatalogService
from .services.orders import OrderService
from .services.payments import PaymentService
from .handlers import admin, user


def build_app() -> ApplicationBuilder:
    settings = get_settings()
    db = Database()
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments)

    application = ApplicationBuilder().token(settings.telegram_token).build()

    application.add_handler(CommandHandler("start", user.start))
    application.add_handler(CommandHandler("list", lambda u, c: user.list_products(u, c, catalog)))
    application.add_handler(CommandHandler("order", lambda u, c: user.order(u, c, orders)))
    application.add_handler(CommandHandler("add", lambda u, c: admin.add(u, c, catalog)))
    return application


def main() -> None:
    app = build_app()  # pragma: no cover
    app.run_polling()  # pragma: no cover


if __name__ == "__main__":  # pragma: no cover
    main()
