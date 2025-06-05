from bot.services.orders import OrderService
from bot.services.payments import PaymentService
from bot.services.catalog import CatalogService
from bot.models import Database, Product
import base64, os
from bot.config import Settings
from datetime import timedelta, datetime


def test_create_and_mark_paid(monkeypatch, tmp_path) -> None:
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids=[],
        monero_rpc_url="url",
        encryption_key=key,
        data_retention_days=30,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)

    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments)
    product = catalog.add_product(Product(name="p", description="", price_xmr=1.0, inventory=1))
    order = orders.create_order(product.id, 1, "addr")
    assert orders.get_address(order) == "addr"
    updated = orders.mark_paid(order.id)
    assert updated.state == "PAID"
    fetched = orders.get_order(order.id)
    assert fetched is not None
    orders.fulfill_order(order.id)
    assert orders.get_order(order.id).state == "FULFILLED"
    orders.cancel_order(order.id)
    assert orders.get_order(order.id).state == "CANCELLED"
    assert orders.list_orders()[0].id == order.id
    # Purge old orders
    # mark as old
    with db.session() as session:
        outdated = session.get(type(order), order.id)
        outdated.created_at = datetime.utcnow() - timedelta(days=31)
        session.add(outdated)
        session.commit()
    orders.purge_old_orders()
    assert orders.get_order(order.id) is None
