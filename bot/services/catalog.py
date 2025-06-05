"""Catalog service for products."""

from __future__ import annotations

from typing import List
from sqlmodel import select

from ..models import Product, Database


class CatalogService:
    """Manage products in the database."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def add_product(self, product: Product) -> Product:
        with self.db.session() as session:
            session.add(product)
            session.commit()
            session.refresh(product)
            return product

    def get_product(self, product_id: int) -> Product | None:
        """Retrieve a single product by id."""
        with self.db.session() as session:
            return session.get(Product, product_id)

    def update_product(self, product: Product) -> Product:
        """Persist updates to a product."""
        with self.db.session() as session:
            session.add(product)
            session.commit()
            session.refresh(product)
            return product

    def delete_product(self, product_id: int) -> None:
        """Remove a product from the catalog."""
        with self.db.session() as session:
            prod = session.get(Product, product_id)
            if prod is not None:
                session.delete(prod)
                session.commit()

    def list_products(self) -> List[Product]:
        with self.db.session() as session:
            return list(session.exec(select(Product)))

    def list_products_by_vendor(self, vendor_id: int) -> List[Product]:
        """List products belonging to a vendor."""
        with self.db.session() as session:
            return list(session.exec(select(Product).where(Product.vendor_id == vendor_id)))
