from bot.services.catalog import CatalogService
from bot.models import Database, Product


def test_add_and_list_product(tmp_path) -> None:
    db = Database(url=f"sqlite:///{tmp_path/'test.db'}")
    service = CatalogService(db)
    prod = Product(name="A", description="B", price_xmr=1.0, inventory=1)
    added = service.add_product(prod)
    assert service.get_product(added.id) is not None
    products = service.list_products()
    assert products[0].name == "A"
    added.inventory = 2
    service.update_product(added)
    assert service.get_product(added.id).inventory == 2
    service.delete_product(added.id)
    assert service.get_product(added.id) is None
    service.delete_product(999)  # cover branch when product missing
