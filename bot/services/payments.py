"""Payment processing stubs for Monero integration."""

from __future__ import annotations

import uuid
from typing import Tuple


class PaymentService:
    """Stubbed payment service."""

    def create_address(self) -> Tuple[str, str]:
        """Return a tuple of (address, payment_id)."""
        payment_id = uuid.uuid4().hex
        address = f"4A{payment_id[:10]}"  # fake address
        return address, payment_id

    def check_paid(self, payment_id: str) -> bool:
        """Fake payment confirmation."""
        return True
