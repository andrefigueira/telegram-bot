from bot.services.orders import OrderService
from bot.services.payments import PaymentService
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.models import Database, Product, Vendor
import base64, os
from bot.config import Settings
import pytest
from datetime import timedelta, datetime


def test_create_and_mark_paid(monkeypatch, tmp_path) -> None:
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids=[],
        super_admin_ids=[],
        monero_rpc_url="url",
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)

    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    vendors = VendorService(db)
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend"))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=1.0, inventory=10, vendor_id=vendor.id)
    )
    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]
    assert order_data["total_xmr"] == 1.0
    assert order_data["quantity"] == 1
    
    # Get the actual order object for testing
    order = orders.get_order(order_id)
    assert order.commission_xmr == pytest.approx(0.05)
    assert orders.get_address(order) == "addr"
    
    updated = orders.mark_paid(order_id)
    assert updated.state == "PAID"
    fetched = orders.get_order(order_id)
    assert fetched is not None
    orders.fulfill_order(order_id)
    assert orders.get_order(order_id).state == "FULFILLED"
    orders.cancel_order(order_id)
    assert orders.get_order(order_id).state == "CANCELLED"
    assert orders.list_orders()[0].id == order_id
    # Purge old orders
    # mark as old
    with db.session() as session:
        from bot.models import Order
        outdated = session.get(Order, order_id)
        outdated.created_at = datetime.utcnow() - timedelta(days=31)
        session.add(outdated)
        session.commit()
    orders.purge_old_orders()
    assert orders.get_order(order_id) is None


def test_create_order_errors(tmp_path) -> None:
    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    vendors = VendorService(db)
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    
    # Test product not found
    with pytest.raises(ValueError, match="Product not found"):
        orders.create_order(1, 1, "a")
    
    vend = vendors.add_vendor(Vendor(telegram_id=2, name="v"))
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=1.0, inventory=1, vendor_id=vend.id)
    )
    
    # Test insufficient inventory
    with pytest.raises(ValueError, match="Insufficient inventory"):
        orders.create_order(product.id, 2, "a")
    
    # remove vendor to trigger not found
    with db.session() as s:
        s.delete(vend)
        s.commit()
    with pytest.raises(ValueError, match="Vendor not found"):
        orders.create_order(product.id, 1, "a")
