"""Vendor management service."""

from __future__ import annotations

from typing import List
from sqlmodel import select

from ..models import Vendor, Database


class VendorService:
    """Manage vendors."""

    def __init__(self, db: Database) -> None:
        self.db = db

    def add_vendor(self, vendor: Vendor) -> Vendor:
        with self.db.session() as session:
            session.add(vendor)
            session.commit()
            session.refresh(vendor)
            return vendor

    def list_vendors(self) -> List[Vendor]:
        with self.db.session() as session:
            return list(session.exec(select(Vendor)))

    def get_by_telegram_id(self, tg_id: int) -> Vendor | None:
        with self.db.session() as session:
            return session.exec(select(Vendor).where(Vendor.telegram_id == tg_id)).first()

    def get_vendor(self, vendor_id: int) -> Vendor | None:
        with self.db.session() as session:
            return session.get(Vendor, vendor_id)

    def set_commission(self, vendor_id: int, rate: float) -> Vendor:
        with self.db.session() as session:
            vendor = session.get(Vendor, vendor_id)
            if not vendor:
                raise ValueError("Vendor not found")
            vendor.commission_rate = rate
            session.add(vendor)
            session.commit()
            session.refresh(vendor)
            return vendor
