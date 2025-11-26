"""Postage type management service."""

from __future__ import annotations

from typing import List, Optional
from decimal import Decimal
from sqlmodel import select

from ..models import Database, PostageType


class PostageService:
    """Service for managing vendor postage options."""

    def __init__(self, db: Database):
        self.db = db

    def add_postage_type(
        self,
        vendor_id: int,
        name: str,
        price_fiat: Decimal,
        currency: str = "USD",
        description: Optional[str] = None,
    ) -> PostageType:
        """Add a new postage type for a vendor."""
        postage = PostageType(
            vendor_id=vendor_id,
            name=name,
            price_fiat=price_fiat,
            currency=currency,
            description=description,
            is_active=True,
        )
        with self.db.session() as session:
            session.add(postage)
            session.commit()
            session.refresh(postage)
            return postage

    def get_postage_type(self, postage_id: int) -> Optional[PostageType]:
        """Get a postage type by ID."""
        with self.db.session() as session:
            return session.get(PostageType, postage_id)

    def list_by_vendor(self, vendor_id: int, active_only: bool = False) -> List[PostageType]:
        """List all postage types for a vendor."""
        with self.db.session() as session:
            stmt = select(PostageType).where(PostageType.vendor_id == vendor_id)
            if active_only:
                stmt = stmt.where(PostageType.is_active == True)
            return list(session.exec(stmt))

    def update_postage_type(self, postage_id: int, **kwargs) -> Optional[PostageType]:
        """Update a postage type."""
        with self.db.session() as session:
            postage = session.get(PostageType, postage_id)
            if postage:
                for key, value in kwargs.items():
                    if hasattr(postage, key):
                        setattr(postage, key, value)
                session.add(postage)
                session.commit()
                session.refresh(postage)
            return postage

    def toggle_active(self, postage_id: int) -> Optional[PostageType]:
        """Toggle postage type active status."""
        with self.db.session() as session:
            postage = session.get(PostageType, postage_id)
            if postage:
                postage.is_active = not postage.is_active
                session.add(postage)
                session.commit()
                session.refresh(postage)
            return postage

    def delete_postage_type(self, postage_id: int) -> bool:
        """Delete a postage type."""
        with self.db.session() as session:
            postage = session.get(PostageType, postage_id)
            if postage:
                session.delete(postage)
                session.commit()
                return True
            return False
