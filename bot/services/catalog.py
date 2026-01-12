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

    def update_product(self, product_or_id, **kwargs) -> Product | None:
        """Persist updates to a product.

        Can be called with a Product object or product_id with keyword args.
        """
        with self.db.session() as session:
            if isinstance(product_or_id, Product):
                session.add(product_or_id)
                session.commit()
                session.refresh(product_or_id)
                return product_or_id
            else:
                # product_id with kwargs
                product = session.get(Product, product_or_id)
                if product:
                    for key, value in kwargs.items():
                        setattr(product, key, value)
                    session.commit()
                    session.refresh(product)
                    return product
                return None

    def delete_product(self, product_id: int) -> None:
        """Remove a product from the catalog."""
        with self.db.session() as session:
            prod = session.get(Product, product_id)
            if prod is not None:
                session.delete(prod)
                session.commit()

    def list_products(self) -> List[Product]:
        with self.db.session() as session:
            products = list(session.exec(select(Product)))
            # Ensure all attributes are loaded before session closes
            for p in products:
                _ = p.id, p.name, p.description, p.price_xmr, p.price_fiat, p.currency, p.inventory, p.vendor_id
            return products

    def list_products_by_vendor(self, vendor_id: int) -> List[Product]:
        """List products belonging to a vendor."""
        with self.db.session() as session:
            products = list(session.exec(select(Product).where(Product.vendor_id == vendor_id)))
            # Ensure all attributes are loaded before session closes
            for p in products:
                _ = p.id, p.name, p.description, p.price_xmr, p.price_fiat, p.currency, p.inventory, p.vendor_id
            return products

    def search(self, query: str) -> List[Product]:
        """Search products by name, description or category."""
        like = f"%{query}%"
        stmt = select(Product).where(
            (Product.name.ilike(like)) |
            (Product.description.ilike(like)) |
            (Product.category.ilike(like))
        )
        with self.db.session() as session:
            products = list(session.exec(stmt))
            # Ensure all attributes are loaded before session closes
            for p in products:
                _ = p.id, p.name, p.description, p.price_xmr, p.price_fiat, p.currency, p.inventory, p.vendor_id
            return products
