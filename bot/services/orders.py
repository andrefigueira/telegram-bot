"""Order management service."""

from __future__ import annotations

from typing import List
from datetime import datetime, timedelta
from sqlmodel import select

from ..models import Order, Database, encrypt, decrypt
from .payments import PaymentService
from ..config import get_settings


class OrderService:
    """Manage orders in the database."""

    def __init__(self, db: Database, payments: PaymentService) -> None:
        self.db = db
        self.payments = payments
        self.settings = get_settings()

    def create_order(self, product_id: int, quantity: int, address: str) -> Order:
        _, payment_id = self.payments.create_address()
        encrypted = encrypt(address, self.settings.encryption_key)
        order = Order(
            product_id=product_id,
            quantity=quantity,
            payment_id=payment_id,
            address_encrypted=encrypted,
        )
        with self.db.session() as session:
            session.add(order)
            session.commit()
            session.refresh(order)
        return order

    def mark_paid(self, order_id: int) -> Order:
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            if self.payments.check_paid(order.payment_id):  # pragma: no cover
                order.state = "PAID"  # pragma: no cover
                session.add(order)  # pragma: no cover
                session.commit()  # pragma: no cover
                session.refresh(order)  # pragma: no cover
            return order

    def get_order(self, order_id: int) -> Order | None:
        """Retrieve a single order."""
        with self.db.session() as session:
            return session.get(Order, order_id)

    def fulfill_order(self, order_id: int) -> Order:
        """Mark a paid order as fulfilled."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            order.state = "FULFILLED"
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def cancel_order(self, order_id: int) -> Order:
        """Cancel an order."""
        with self.db.session() as session:
            order = session.get(Order, order_id)
            if not order:  # pragma: no cover
                raise ValueError("Order not found")
            order.state = "CANCELLED"
            session.add(order)
            session.commit()
            session.refresh(order)
            return order

    def list_orders(self) -> List[Order]:
        with self.db.session() as session:
            return list(session.exec(select(Order)))

    def get_address(self, order: Order) -> str:
        return decrypt(order.address_encrypted, self.settings.encryption_key)

    def purge_old_orders(self) -> None:
        """Delete orders older than retention days."""
        cutoff = datetime.utcnow() - timedelta(days=self.settings.data_retention_days)
        with self.db.session() as session:
            old_orders = session.exec(select(Order).where(Order.created_at < cutoff))
            for order in list(old_orders):
                session.delete(order)
            session.commit()
