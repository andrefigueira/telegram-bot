"""Vendor management service."""

from __future__ import annotations

import logging
from typing import List
from sqlmodel import select

from ..models import Vendor, Database

logger = logging.getLogger(__name__)


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

    def update_settings(
        self,
        vendor_id: int,
        pricing_currency: str | None = None,
        shop_name: str | None = None,
        wallet_address: str | None = None,
        accepted_payments: list[str] | None = None,
    ) -> Vendor:
        """Update vendor settings."""
        with self.db.session() as session:
            vendor = session.get(Vendor, vendor_id)
            if not vendor:
                raise ValueError("Vendor not found")

            if pricing_currency is not None:
                vendor.pricing_currency = pricing_currency
                logger.info(f"Updated vendor {vendor_id} pricing_currency to {pricing_currency}")
            if shop_name is not None:
                vendor.shop_name = shop_name
                logger.info(f"Updated vendor {vendor_id} shop_name to {shop_name}")
            if wallet_address is not None:
                vendor.wallet_address = wallet_address
                logger.info(f"Updated vendor {vendor_id} wallet_address to {wallet_address[:20]}...")
            if accepted_payments is not None:
                vendor.accepted_payments = ",".join(accepted_payments)
                logger.info(f"Updated vendor {vendor_id} accepted_payments to {accepted_payments}")

            session.add(vendor)
            session.commit()
            session.refresh(vendor)
            logger.info(f"Vendor {vendor_id} settings saved. Wallet: {vendor.wallet_address}")
            return vendor

    def get_accepted_payments_list(self, vendor: Vendor) -> list[str]:
        """Get accepted payments as a list."""
        if not vendor.accepted_payments:
            return ["XMR"]
        return [p.strip() for p in vendor.accepted_payments.split(",") if p.strip()]
