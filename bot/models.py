"""Database models."""

from __future__ import annotations

from decimal import Decimal
from sqlalchemy import Column, Numeric
from sqlmodel import Field, SQLModel, create_engine, Session, select
from typing import Optional, List
from datetime import datetime
import base64
from nacl import secret


class Product(SQLModel, table=True):
    """Product item."""

    id: Optional[int] = Field(default=None, primary_key=True)
    name: str
    description: str
    category: Optional[str] = None
    # Use sa_column for Decimal type to ensure precision
    price_xmr: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(precision=20, scale=8, asdecimal=True)))
    price_fiat: Optional[Decimal] = Field(default=None, sa_column=Column(Numeric(precision=20, scale=2, asdecimal=True)))
    currency: str = "XMR"  # Currency code (USD, GBP, EUR, XMR)
    media_id: Optional[str] = None
    inventory: int = 0
    vendor_id: int = Field(foreign_key="vendor.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Vendor(SQLModel, table=True):
    """Store vendor information."""

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int
    name: str
    commission_rate: Decimal = Field(default=Decimal("0.05"), sa_column=Column(Numeric(precision=10, scale=4, asdecimal=True)))
    # Vendor settings (persisted)
    pricing_currency: str = "USD"
    shop_name: Optional[str] = None
    wallet_address: Optional[str] = None
    accepted_payments: str = "XMR"  # Comma-separated list of accepted coins
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Order(SQLModel, table=True):
    """Customer order."""

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    vendor_id: int = Field(foreign_key="vendor.id")
    quantity: int
    payment_id: str
    address_encrypted: str
    commission_xmr: Decimal = Field(default=Decimal("0"), sa_column=Column(Numeric(precision=20, scale=8, asdecimal=True)))
    state: str = "NEW"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Database:
    """Database wrapper."""

    def __init__(self, url: str = "sqlite:///db.sqlite3") -> None:
        self.engine = create_engine(url, echo=False)
        SQLModel.metadata.create_all(self.engine)
        self._run_migrations()

    def _run_migrations(self) -> None:
        """Run database migrations for schema changes."""
        from sqlalchemy import text, inspect

        inspector = inspect(self.engine)
        migrations = []

        # Check if vendor table exists and add missing columns
        if 'vendor' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('vendor')]

            if 'pricing_currency' not in columns:
                migrations.append("ALTER TABLE vendor ADD COLUMN pricing_currency VARCHAR DEFAULT 'USD'")
            if 'shop_name' not in columns:
                migrations.append("ALTER TABLE vendor ADD COLUMN shop_name VARCHAR")
            if 'wallet_address' not in columns:
                migrations.append("ALTER TABLE vendor ADD COLUMN wallet_address VARCHAR")
            if 'accepted_payments' not in columns:
                migrations.append("ALTER TABLE vendor ADD COLUMN accepted_payments VARCHAR DEFAULT 'XMR'")

        # Check if product table exists and add missing columns
        if 'product' in inspector.get_table_names():
            columns = [col['name'] for col in inspector.get_columns('product')]

            if 'price_fiat' not in columns:
                migrations.append("ALTER TABLE product ADD COLUMN price_fiat FLOAT")
            if 'currency' not in columns:
                migrations.append("ALTER TABLE product ADD COLUMN currency VARCHAR DEFAULT 'XMR'")

        if migrations:
            with self.engine.connect() as conn:
                for sql in migrations:
                    conn.execute(text(sql))
                conn.commit()

    def session(self) -> Session:
        """Create a new session."""
        return Session(self.engine)


def encrypt(plain: str, key: str) -> str:
    """Encrypt text with base64 key."""
    box = secret.SecretBox(base64.b64decode(key))
    encrypted = box.encrypt(plain.encode())
    return base64.b64encode(encrypted).decode()


def decrypt(ciphertext: str, key: str) -> str:
    """Decrypt text with base64 key."""
    box = secret.SecretBox(base64.b64decode(key))
    decrypted = box.decrypt(base64.b64decode(ciphertext))
    return decrypted.decode()
