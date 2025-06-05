"""Database models."""

from __future__ import annotations

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
    price_xmr: float
    media_id: Optional[str] = None
    inventory: int = 0
    vendor_id: int = Field(foreign_key="vendor.id")
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Vendor(SQLModel, table=True):
    """Store vendor information."""

    id: Optional[int] = Field(default=None, primary_key=True)
    telegram_id: int
    name: str
    commission_rate: float = 0.05
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Order(SQLModel, table=True):
    """Customer order."""

    id: Optional[int] = Field(default=None, primary_key=True)
    product_id: int = Field(foreign_key="product.id")
    vendor_id: int = Field(foreign_key="vendor.id")
    quantity: int
    payment_id: str
    address_encrypted: str
    commission_xmr: float = 0.0
    state: str = "NEW"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class Database:
    """Database wrapper."""

    def __init__(self, url: str = "sqlite:///db.sqlite3") -> None:
        self.engine = create_engine(url, echo=False)
        SQLModel.metadata.create_all(self.engine)

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
