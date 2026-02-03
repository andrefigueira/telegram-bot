from decimal import Decimal
from bot.services.orders import OrderService
from bot.services.payments import PaymentService
from bot.services.catalog import CatalogService
from bot.services.vendors import VendorService
from bot.models import Database, Product, Vendor
import base64, os
from bot.config import Settings
import pytest
from datetime import timedelta, datetime
from unittest.mock import patch


def test_create_and_mark_paid(monkeypatch, tmp_path) -> None:
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",  # String, not list
        super_admin_ids="",  # String, not list
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
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )
    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]
    assert order_data["total_xmr"] == Decimal("1.0")
    assert order_data["quantity"] == 1

    # Get the actual order object for testing
    order = orders.get_order(order_id)
    assert order.commission_xmr == Decimal("0.05")
    assert orders.get_address(order) == "addr"
    
    # Mock check_paid to return True for test
    monkeypatch.setattr(payments, "check_paid", lambda payment_id: True)
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
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=1, vendor_id=vend.id)
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


def test_create_order_vendor_no_wallet(monkeypatch, tmp_path) -> None:
    """Test create_order raises error when vendor has no wallet and no RPC."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
        monero_rpc_url="",  # No RPC URL
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)

    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    vendors = VendorService(db)
    # Create vendor without wallet_address
    vendor = vendors.add_vendor(Vendor(telegram_id=99, name="no_wallet_vendor", wallet_address=None))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    with pytest.raises(ValueError, match="Vendor has not configured their payment wallet"):
        orders.create_order(product.id, 1, "addr")


def test_create_order_with_postage(monkeypatch, tmp_path) -> None:
    """Test create_order with postage type."""
    from bot.models import PostageType
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
        monero_rpc_url="url",
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)
    # Mock fiat_to_xmr_sync to return a fixed rate
    monkeypatch.setattr("bot.services.orders.fiat_to_xmr_sync", lambda amount, currency: Decimal("0.1"))

    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    vendors = VendorService(db)
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    # Create postage type
    with db.session() as session:
        postage = PostageType(
            vendor_id=vendor.id,
            name="Express",
            description="Fast delivery",
            price_fiat=Decimal("10.0"),
            currency="USD",
            is_active=True
        )
        session.add(postage)
        session.commit()
        session.refresh(postage)
        postage_id = postage.id

    order_data = orders.create_order(product.id, 1, "addr", postage_type_id=postage_id)

    assert order_data["postage_xmr"] == Decimal("0.1")
    assert order_data["total_xmr"] == Decimal("1.1")  # 1.0 + 0.1 postage


def test_get_payment_info_xmr(monkeypatch, tmp_path) -> None:
    """Test get_payment_info for XMR."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("2.5"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 2, "addr")
    order_id = order_data["order_id"]

    payment_info = orders.get_payment_info(order_id, "XMR")

    assert payment_info["amount"] == Decimal("5.0")  # 2.5 * 2
    assert payment_info["coin"] == "XMR"
    assert "address" in payment_info


def test_get_payment_info_uses_existing_payment_id(monkeypatch, tmp_path) -> None:
    """Test get_payment_info uses stored payment_id."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("2.5"), inventory=10, vendor_id=vendor.id)
    )

    with patch.object(payments, "get_address_for_payment_id", return_value="4ADDR") as mock_get_address:
        order_data = orders.create_order(product.id, 1, "addr")
        mock_get_address.reset_mock()

        payment_info = orders.get_payment_info(order_data["order_id"], "XMR")

        mock_get_address.assert_called_once_with(
            order_data["payment_id"],
            vendor_wallet=vendor.wallet_address
        )
        assert payment_info["address"] == "4ADDR"
        assert payment_info["payment_id"] == order_data["payment_id"]


def test_get_payment_info_other_coin(monkeypatch, tmp_path) -> None:
    """Test get_payment_info for non-XMR coin."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    payment_info = orders.get_payment_info(order_id, "BTC")

    assert payment_info["amount"] == Decimal("1.0")
    assert payment_info["coin"] == "BTC"
    assert payment_info["address"] == "Payment address pending..."


def test_get_payment_info_order_not_found(monkeypatch, tmp_path) -> None:
    """Test get_payment_info with non-existent order."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)

    with pytest.raises(ValueError, match="Order not found"):
        orders.get_payment_info(99999, "XMR")


def test_list_orders_by_vendor(monkeypatch, tmp_path) -> None:
    """Test listing orders by vendor."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor1 = vendors.add_vendor(Vendor(telegram_id=1, name="vend1", wallet_address="4ABC..."))
    vendor2 = vendors.add_vendor(Vendor(telegram_id=2, name="vend2", wallet_address="4DEF..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)

    product1 = catalog.add_product(
        Product(name="p1", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor1.id)
    )
    product2 = catalog.add_product(
        Product(name="p2", description="", price_xmr=Decimal("2.0"), inventory=10, vendor_id=vendor2.id)
    )

    # Create orders for both vendors
    orders.create_order(product1.id, 1, "addr1")
    orders.create_order(product1.id, 1, "addr2")
    orders.create_order(product2.id, 1, "addr3")

    vendor1_orders = orders.list_orders_by_vendor(vendor1.id)
    vendor2_orders = orders.list_orders_by_vendor(vendor2.id)

    assert len(vendor1_orders) == 2
    assert len(vendor2_orders) == 1


def test_mark_shipped(monkeypatch, tmp_path) -> None:
    """Test marking an order as shipped."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Mark as paid first
    monkeypatch.setattr(payments, "check_paid", lambda payment_id: True)
    orders.mark_paid(order_id)

    # Now mark as shipped
    shipped_order = orders.mark_shipped(order_id, shipping_note="Tracking: XYZ123")

    assert shipped_order.state == "SHIPPED"
    assert shipped_order.shipped_at is not None
    assert shipped_order.shipping_note == "Tracking: XYZ123"


def test_mark_shipped_without_note(monkeypatch, tmp_path) -> None:
    """Test marking an order as shipped without a note."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Mark as paid first
    monkeypatch.setattr(payments, "check_paid", lambda payment_id: True)
    orders.mark_paid(order_id)

    # Now mark as shipped without note
    shipped_order = orders.mark_shipped(order_id)

    assert shipped_order.state == "SHIPPED"
    assert shipped_order.shipped_at is not None


def test_mark_shipped_order_not_found(monkeypatch, tmp_path) -> None:
    """Test mark_shipped with non-existent order."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)

    with pytest.raises(ValueError, match="Order not found"):
        orders.mark_shipped(99999)


def test_mark_shipped_wrong_state(monkeypatch, tmp_path) -> None:
    """Test mark_shipped on an order that's not PAID."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Try to ship without paying first (order is NEW)
    with pytest.raises(ValueError, match="Cannot ship order in state"):
        orders.mark_shipped(order_id)


def test_mark_completed(monkeypatch, tmp_path) -> None:
    """Test marking an order as completed."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Mark as paid, then shipped
    monkeypatch.setattr(payments, "check_paid", lambda payment_id: True)
    orders.mark_paid(order_id)
    orders.mark_shipped(order_id)

    # Now complete
    completed_order = orders.mark_completed(order_id)

    assert completed_order.state == "COMPLETED"


def test_mark_completed_order_not_found(monkeypatch, tmp_path) -> None:
    """Test mark_completed with non-existent order."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)

    with pytest.raises(ValueError, match="Order not found"):
        orders.mark_completed(99999)


def test_mark_completed_wrong_state(monkeypatch, tmp_path) -> None:
    """Test mark_completed on an order that's not SHIPPED."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Mark as paid but not shipped
    monkeypatch.setattr(payments, "check_paid", lambda payment_id: True)
    orders.mark_paid(order_id)

    # Try to complete without shipping
    with pytest.raises(ValueError, match="Cannot complete order in state"):
        orders.mark_completed(order_id)


def test_get_payment_info_product_not_found(monkeypatch, tmp_path) -> None:
    """Test get_payment_info when product has been deleted."""
    from unittest.mock import patch
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    order_data = orders.create_order(product.id, 1, "addr")
    order_id = order_data["order_id"]

    # Delete the product to trigger "Product not found" in get_payment_info
    with db.session() as session:
        prod = session.get(Product, product.id)
        session.delete(prod)
        session.commit()

    with pytest.raises(ValueError, match="Product not found"):
        orders.get_payment_info(order_id, "XMR")


def test_create_order_with_inactive_postage(monkeypatch, tmp_path) -> None:
    """Test create_order with inactive postage type (should not add postage)."""
    from bot.models import PostageType
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
        monero_rpc_url="url",
        encryption_key=key,
        data_retention_days=30,
        default_commission_rate=0.05,
        totp_secret=None,
    )
    monkeypatch.setattr("bot.config.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.get_settings", lambda: settings)
    monkeypatch.setattr("bot.services.orders.fiat_to_xmr_sync", lambda amount, currency: Decimal("0.1"))

    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    vendors = VendorService(db)
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    # Create inactive postage type
    with db.session() as session:
        postage = PostageType(
            vendor_id=vendor.id,
            name="Inactive Postage",
            description="Not available",
            price_fiat=Decimal("10.0"),
            currency="USD",
            is_active=False
        )
        session.add(postage)
        session.commit()
        session.refresh(postage)
        postage_id = postage.id

    # Order should be created but without postage since it's inactive
    order_data = orders.create_order(product.id, 1, "addr", postage_type_id=postage_id)

    # Postage should be 0 since the type is inactive
    assert order_data["postage_xmr"] == Decimal("0")
    assert order_data["total_xmr"] == Decimal("1.0")


def test_create_order_with_nonexistent_postage(monkeypatch, tmp_path) -> None:
    """Test create_order with non-existent postage type ID."""
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    # Pass non-existent postage_type_id
    order_data = orders.create_order(product.id, 1, "addr", postage_type_id=99999)

    # Should succeed but with zero postage
    assert order_data["postage_xmr"] == Decimal("0")
    assert order_data["total_xmr"] == Decimal("1.0")


def test_create_order_product_deleted_race_condition(monkeypatch, tmp_path) -> None:
    """Test create_order when product is deleted between checks (race condition)."""
    from unittest.mock import patch, MagicMock
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders_service = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    # Delete the product after catalog lookup but before session lookup
    # We'll patch the session.get to return None only in the order-saving block
    original_session = db.session
    session_count = [0]

    def mock_session():
        session_count[0] += 1
        session = original_session()
        # After monkeypatch, in create_order:
        # 1: catalog.get_product
        # 2: vendors.get_vendor
        # 3: order saving block (lines 90-105) <- this is where we want to return None
        if session_count[0] == 3:
            original_get = session.get
            def mock_get(model, id):
                if model == Product:
                    return None  # Simulate product deleted
                return original_get(model, id)
            session.get = mock_get
        return session

    monkeypatch.setattr(db, "session", mock_session)

    with pytest.raises(ValueError, match="Product not found"):
        orders_service.create_order(product.id, 1, "addr")


def test_create_order_inventory_race_condition(monkeypatch, tmp_path) -> None:
    """Test create_order when inventory goes negative due to race condition."""
    from unittest.mock import MagicMock
    key = base64.b64encode(os.urandom(32)).decode()
    settings = Settings(
        telegram_token="123:ABC",
        admin_ids="",
        super_admin_ids="",
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
    vendor = vendors.add_vendor(Vendor(telegram_id=1, name="vend", wallet_address="4ABC..."))
    catalog = CatalogService(db)
    payments = PaymentService()
    orders_service = OrderService(db, payments, catalog, vendors)
    product = catalog.add_product(
        Product(name="p", description="", price_xmr=Decimal("1.0"), inventory=10, vendor_id=vendor.id)
    )

    # Mock the session to return product with inventory=0 in third session (order saving block)
    original_session = db.session
    session_count = [0]

    def mock_session():
        session_count[0] += 1
        session = original_session()
        # After monkeypatch, in create_order:
        # 1: catalog.get_product
        # 2: vendors.get_vendor
        # 3: order saving block (lines 90-105) <- this is where we want to set inventory=0
        if session_count[0] == 3:
            original_get = session.get
            def mock_get(model, id):
                result = original_get(model, id)
                if model == Product and result is not None:
                    # Simulate another order reducing inventory to 0
                    result.inventory = 0
                return result
            session.get = mock_get
        return session

    monkeypatch.setattr(db, "session", mock_session)

    with pytest.raises(ValueError, match="Insufficient inventory"):
        orders_service.create_order(product.id, 1, "addr")
