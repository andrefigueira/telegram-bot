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
