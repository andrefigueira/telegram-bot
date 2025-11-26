"""Payout service for vendor payments."""

from __future__ import annotations

import logging
from datetime import datetime
from decimal import Decimal
from typing import Optional, List
from sqlmodel import select

from ..models import Database, PlatformSettings, Payout, Order, Vendor
from ..config import get_settings

logger = logging.getLogger(__name__)


class PayoutService:
    """Service for managing platform settings and vendor payouts."""

    # Default settings
    DEFAULT_COMMISSION_RATE = Decimal("0.05")  # 5%

    def __init__(self, db: Database):
        self.db = db
        self.settings = get_settings()

    # Platform Settings Management

    def get_setting(self, key: str, default: str = "") -> str:
        """Get a platform setting value."""
        with self.db.session() as session:
            stmt = select(PlatformSettings).where(PlatformSettings.key == key)
            setting = session.exec(stmt).first()
            return setting.value if setting else default

    def set_setting(self, key: str, value: str) -> PlatformSettings:
        """Set a platform setting value."""
        with self.db.session() as session:
            stmt = select(PlatformSettings).where(PlatformSettings.key == key)
            setting = session.exec(stmt).first()

            if setting:
                setting.value = value
                setting.updated_at = datetime.utcnow()
            else:
                setting = PlatformSettings(key=key, value=value)

            session.add(setting)
            session.commit()
            session.refresh(setting)
            return setting

    def get_platform_commission_rate(self) -> Decimal:
        """Get the platform commission rate."""
        rate_str = self.get_setting("commission_rate", str(self.DEFAULT_COMMISSION_RATE))
        try:
            return Decimal(rate_str)
        except Exception:
            return self.DEFAULT_COMMISSION_RATE

    def set_platform_commission_rate(self, rate: Decimal) -> None:
        """Set the platform commission rate."""
        self.set_setting("commission_rate", str(rate))

    def get_platform_wallet(self) -> Optional[str]:
        """Get the platform payout wallet address."""
        return self.get_setting("platform_wallet", "") or None

    def set_platform_wallet(self, address: str) -> None:
        """Set the platform payout wallet address."""
        self.set_setting("platform_wallet", address)

    # Payout Management

    def calculate_split(
        self,
        total_xmr: Decimal,
        vendor_commission_rate: Optional[Decimal] = None
    ) -> tuple[Decimal, Decimal]:
        """
        Calculate the split between vendor and platform.

        Returns (vendor_share, platform_share)
        """
        # Use vendor-specific rate if provided, otherwise platform default
        commission_rate = vendor_commission_rate or self.get_platform_commission_rate()
        platform_share = total_xmr * commission_rate
        vendor_share = total_xmr - platform_share
        return vendor_share, platform_share

    def create_payout(self, order_id: int, vendor_id: int, amount_xmr: Decimal) -> Payout:
        """Create a pending payout record."""
        payout = Payout(
            order_id=order_id,
            vendor_id=vendor_id,
            amount_xmr=amount_xmr,
            status="PENDING"
        )
        with self.db.session() as session:
            session.add(payout)
            session.commit()
            session.refresh(payout)
            logger.info(f"Created payout {payout.id} for vendor {vendor_id}: {amount_xmr} XMR")
            return payout

    def get_pending_payouts(self) -> List[Payout]:
        """Get all pending payouts."""
        with self.db.session() as session:
            stmt = select(Payout).where(Payout.status == "PENDING")
            return list(session.exec(stmt))

    def get_vendor_payouts(self, vendor_id: int) -> List[Payout]:
        """Get all payouts for a vendor."""
        with self.db.session() as session:
            stmt = select(Payout).where(Payout.vendor_id == vendor_id)
            return list(session.exec(stmt))

    def mark_payout_sent(self, payout_id: int, tx_hash: str) -> Optional[Payout]:
        """Mark a payout as sent with transaction hash."""
        with self.db.session() as session:
            payout = session.get(Payout, payout_id)
            if payout:
                payout.status = "SENT"
                payout.tx_hash = tx_hash
                payout.sent_at = datetime.utcnow()
                session.add(payout)
                session.commit()
                session.refresh(payout)
                logger.info(f"Payout {payout_id} sent: {tx_hash}")
            return payout

    def mark_payout_confirmed(self, payout_id: int) -> Optional[Payout]:
        """Mark a payout as confirmed."""
        with self.db.session() as session:
            payout = session.get(Payout, payout_id)
            if payout:
                payout.status = "CONFIRMED"
                session.add(payout)
                session.commit()
                session.refresh(payout)
            return payout

    def mark_payout_failed(self, payout_id: int, error: str = "") -> Optional[Payout]:
        """Mark a payout as failed."""
        with self.db.session() as session:
            payout = session.get(Payout, payout_id)
            if payout:
                payout.status = "FAILED"
                session.add(payout)
                session.commit()
                session.refresh(payout)
                logger.error(f"Payout {payout_id} failed: {error}")
            return payout

    async def process_payouts(self) -> dict:
        """
        Process all pending payouts by sending XMR to vendor wallets.

        Returns summary of processed payouts.
        """
        from ..services.payments import MoneroPaymentService

        results = {"processed": 0, "sent": 0, "failed": 0, "skipped": 0}
        payment_service = MoneroPaymentService()

        pending = self.get_pending_payouts()
        results["processed"] = len(pending)

        for payout in pending:
            # Get vendor wallet address
            with self.db.session() as session:
                vendor = session.get(Vendor, payout.vendor_id)

            if not vendor or not vendor.wallet_address:
                logger.warning(
                    f"Skipping payout {payout.id}: vendor {payout.vendor_id} has no wallet"
                )
                results["skipped"] += 1
                continue

            try:
                # Send the payment via Monero RPC
                wallet = payment_service._get_wallet()
                if wallet:
                    # Use monero library to send
                    tx = wallet.transfer(
                        vendor.wallet_address,
                        payout.amount_xmr
                    )
                    tx_hash = str(tx.hash) if hasattr(tx, 'hash') else str(tx)
                    self.mark_payout_sent(payout.id, tx_hash)
                    results["sent"] += 1
                    logger.info(
                        f"Sent {payout.amount_xmr} XMR to vendor {vendor.id}: {tx_hash}"
                    )
                else:
                    results["skipped"] += 1
                    logger.warning(f"No wallet available for payout {payout.id}")

            except Exception as e:
                self.mark_payout_failed(payout.id, str(e))
                results["failed"] += 1
                logger.error(f"Failed to process payout {payout.id}: {e}")

        return results

    def get_platform_stats(self) -> dict:
        """Get platform statistics for super admin."""
        with self.db.session() as session:
            # Total orders
            orders = list(session.exec(select(Order)))
            total_orders = len(orders)
            paid_orders = len([o for o in orders if o.state in ("PAID", "SHIPPED", "COMPLETED")])

            # Total commission earned
            total_commission = sum(o.commission_xmr for o in orders if o.state in ("PAID", "SHIPPED", "COMPLETED"))

            # Pending payouts
            pending_payouts = list(session.exec(
                select(Payout).where(Payout.status == "PENDING")
            ))
            pending_amount = sum(p.amount_xmr for p in pending_payouts)

            # Sent payouts
            sent_payouts = list(session.exec(
                select(Payout).where(Payout.status.in_(["SENT", "CONFIRMED"]))
            ))
            sent_amount = sum(p.amount_xmr for p in sent_payouts)

            return {
                "total_orders": total_orders,
                "paid_orders": paid_orders,
                "total_commission_xmr": total_commission,
                "pending_payouts": len(pending_payouts),
                "pending_payout_amount_xmr": pending_amount,
                "completed_payouts": len(sent_payouts),
                "completed_payout_amount_xmr": sent_amount,
                "commission_rate": self.get_platform_commission_rate(),
                "platform_wallet": self.get_platform_wallet(),
            }
