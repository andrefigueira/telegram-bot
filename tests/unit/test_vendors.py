from bot.services.vendors import VendorService
from bot.models import Database, Vendor
import pytest


def test_add_and_set_commission(tmp_path) -> None:
    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    service = VendorService(db)
    vendor = service.add_vendor(Vendor(telegram_id=1, name='v'))
    assert service.get_vendor(vendor.id) is not None
    assert service.get_by_telegram_id(1).id == vendor.id
    service.set_commission(vendor.id, 0.1)
    assert service.get_vendor(vendor.id).commission_rate == 0.1
    assert service.list_vendors()[0].name == 'v'
    with pytest.raises(ValueError):
        service.set_commission(999, 0.2)


class TestVendorSettings:
    """Tests for vendor settings persistence."""

    def test_update_pricing_currency(self, tmp_path) -> None:
        """Test updating vendor's pricing currency."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=100, name='TestVendor'))

        # Default should be USD
        assert vendor.pricing_currency == "USD"

        # Update to GBP
        updated = service.update_settings(vendor.id, pricing_currency="GBP")
        assert updated.pricing_currency == "GBP"

        # Verify persisted
        fetched = service.get_vendor(vendor.id)
        assert fetched.pricing_currency == "GBP"

    def test_update_shop_name(self, tmp_path) -> None:
        """Test updating vendor's shop name."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=101, name='TestVendor'))

        # Default should be None
        assert vendor.shop_name is None

        # Update shop name
        updated = service.update_settings(vendor.id, shop_name="My Awesome Shop")
        assert updated.shop_name == "My Awesome Shop"

        # Verify persisted
        fetched = service.get_vendor(vendor.id)
        assert fetched.shop_name == "My Awesome Shop"

    def test_update_wallet_address(self, tmp_path) -> None:
        """Test updating vendor's wallet address."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=102, name='TestVendor'))

        # Default should be None
        assert vendor.wallet_address is None

        # Update wallet
        test_wallet = "4AdUndXHHZ6cfufTMvppY6JwXNouMBzSkbLYfpAV5Usx"
        updated = service.update_settings(vendor.id, wallet_address=test_wallet)
        assert updated.wallet_address == test_wallet

        # Verify persisted
        fetched = service.get_vendor(vendor.id)
        assert fetched.wallet_address == test_wallet

    def test_update_accepted_payments(self, tmp_path) -> None:
        """Test updating vendor's accepted payment methods."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=103, name='TestVendor'))

        # Default should be XMR
        assert vendor.accepted_payments == "XMR"

        # Update to multiple currencies
        updated = service.update_settings(vendor.id, accepted_payments=["XMR", "BTC", "LTC"])
        assert updated.accepted_payments == "XMR,BTC,LTC"

        # Verify persisted
        fetched = service.get_vendor(vendor.id)
        assert fetched.accepted_payments == "XMR,BTC,LTC"

    def test_update_multiple_settings(self, tmp_path) -> None:
        """Test updating multiple settings at once."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=104, name='TestVendor'))

        # Update all settings at once
        updated = service.update_settings(
            vendor.id,
            pricing_currency="EUR",
            shop_name="Euro Store",
            wallet_address="test_wallet_123",
            accepted_payments=["XMR", "BTC"]
        )

        assert updated.pricing_currency == "EUR"
        assert updated.shop_name == "Euro Store"
        assert updated.wallet_address == "test_wallet_123"
        assert updated.accepted_payments == "XMR,BTC"

        # Verify all persisted
        fetched = service.get_vendor(vendor.id)
        assert fetched.pricing_currency == "EUR"
        assert fetched.shop_name == "Euro Store"
        assert fetched.wallet_address == "test_wallet_123"
        assert fetched.accepted_payments == "XMR,BTC"

    def test_update_settings_vendor_not_found(self, tmp_path) -> None:
        """Test update_settings raises error for non-existent vendor."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)

        with pytest.raises(ValueError, match="Vendor not found"):
            service.update_settings(999, pricing_currency="GBP")

    def test_get_accepted_payments_list(self, tmp_path) -> None:
        """Test get_accepted_payments_list helper method."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=105, name='TestVendor'))

        # Default should return XMR
        payments = service.get_accepted_payments_list(vendor)
        assert payments == ["XMR"]

        # Update and check list format
        service.update_settings(vendor.id, accepted_payments=["XMR", "BTC", "LTC"])
        updated = service.get_vendor(vendor.id)
        payments = service.get_accepted_payments_list(updated)
        assert payments == ["XMR", "BTC", "LTC"]

    def test_get_accepted_payments_list_empty(self, tmp_path) -> None:
        """Test get_accepted_payments_list with empty value returns default."""
        db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
        service = VendorService(db)
        vendor = service.add_vendor(Vendor(telegram_id=106, name='TestVendor'))

        # Manually set to empty string
        vendor.accepted_payments = ""

        payments = service.get_accepted_payments_list(vendor)
        assert payments == ["XMR"]

    def test_settings_persist_across_sessions(self, tmp_path) -> None:
        """Test that settings persist when creating new service instance."""
        db_path = tmp_path / 'persist_test.db'

        # First session - create and update vendor
        db1 = Database(url=f"sqlite:///{db_path}")
        service1 = VendorService(db1)
        vendor = service1.add_vendor(Vendor(telegram_id=107, name='PersistVendor'))
        service1.update_settings(
            vendor.id,
            pricing_currency="GBP",
            shop_name="Persistent Shop",
            wallet_address="persist_wallet",
            accepted_payments=["BTC", "ETH"]
        )

        # Second session - new service instance, same DB
        db2 = Database(url=f"sqlite:///{db_path}")
        service2 = VendorService(db2)
        fetched = service2.get_by_telegram_id(107)

        assert fetched is not None
        assert fetched.pricing_currency == "GBP"
        assert fetched.shop_name == "Persistent Shop"
        assert fetched.wallet_address == "persist_wallet"
        assert fetched.accepted_payments == "BTC,ETH"
