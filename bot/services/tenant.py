"""Tenant management service."""

import hashlib
import logging
import secrets
from datetime import datetime
from typing import Optional

import bcrypt

from bot.models_multitenant import (
    MultiTenantDatabase, Tenant, TenantProduct, TenantOrder,
    OrderState
)

logger = logging.getLogger(__name__)


class TenantService:
    """Service for managing tenants (shop owners)."""

    TERMS_VERSION = "1.0"

    def __init__(self, db: MultiTenantDatabase):
        self.db = db

    def register(
        self,
        email: str,
        password: str,
        accept_terms: bool = False
    ) -> Optional[Tenant]:
        """Register a new tenant."""
        if not accept_terms:
            raise ValueError("Terms must be accepted to register")

        # Check if email already exists
        existing = self.db.get_tenant_by_email(email)
        if existing:
            raise ValueError("Email already registered")

        # Hash password
        password_hash = bcrypt.hashpw(
            password.encode('utf-8'),
            bcrypt.gensalt()
        ).decode('utf-8')

        tenant = self.db.create_tenant(
            email=email,
            password_hash=password_hash,
            terms_version=self.TERMS_VERSION
        )

        logger.info(f"New tenant registered: {email}")
        self.db.log_action(
            action="tenant_registered",
            tenant_id=tenant.id,
            details=f'{{"email": "{email}"}}'
        )

        return tenant

    def authenticate(self, email: str, password: str) -> Optional[Tenant]:
        """Authenticate a tenant."""
        tenant = self.db.get_tenant_by_email(email)
        if not tenant:
            return None

        if bcrypt.checkpw(
            password.encode('utf-8'),
            tenant.password_hash.encode('utf-8')
        ):
            logger.info(f"Tenant authenticated: {email}")
            return tenant

        return None

    def get_tenant(self, tenant_id: str) -> Optional[Tenant]:
        """Get tenant by ID."""
        return self.db.get_tenant(tenant_id)

    def update_profile(
        self,
        tenant_id: str,
        shop_name: Optional[str] = None,
        monero_wallet_address: Optional[str] = None,
        monero_view_key: Optional[str] = None
    ) -> Optional[Tenant]:
        """Update tenant profile."""
        updates = {}
        if shop_name is not None:
            updates["shop_name"] = shop_name
        if monero_wallet_address is not None:
            updates["monero_wallet_address"] = monero_wallet_address
        if monero_view_key is not None:
            updates["monero_view_key"] = monero_view_key

        if updates:
            tenant = self.db.update_tenant(tenant_id, **updates)
            if tenant:
                self.db.log_action(
                    action="profile_updated",
                    tenant_id=tenant_id,
                    details=str(list(updates.keys()))
                )
            return tenant
        return self.db.get_tenant(tenant_id)

    def connect_bot(
        self,
        tenant_id: str,
        bot_token: str,
        platform_encryption_key: str
    ) -> Optional[Tenant]:
        """Connect a Telegram bot to the tenant."""
        from nacl.secret import SecretBox
        import base64

        # Encrypt the bot token
        key = base64.b64decode(platform_encryption_key)
        box = SecretBox(key)
        encrypted = box.encrypt(bot_token.encode('utf-8'))
        token_encrypted = base64.b64encode(encrypted).decode('utf-8')

        # Extract bot username from token (first part before :)
        try:
            bot_id = bot_token.split(':')[0]
            # We'd normally call Telegram API to get username
            # For now, store just the ID
            bot_username = f"bot_{bot_id}"
        except Exception:
            bot_username = None

        tenant = self.db.update_tenant(
            tenant_id,
            bot_token_encrypted=token_encrypted,
            bot_username=bot_username,
            bot_active=True
        )

        if tenant:
            logger.info(f"Bot connected for tenant: {tenant_id}")
            self.db.log_action(
                action="bot_connected",
                tenant_id=tenant_id
            )

        return tenant

    def disconnect_bot(self, tenant_id: str) -> Optional[Tenant]:
        """Disconnect the Telegram bot from tenant."""
        tenant = self.db.update_tenant(
            tenant_id,
            bot_token_encrypted=None,
            bot_username=None,
            bot_active=False
        )

        if tenant:
            logger.info(f"Bot disconnected for tenant: {tenant_id}")
            self.db.log_action(
                action="bot_disconnected",
                tenant_id=tenant_id
            )

        return tenant

    def decrypt_bot_token(
        self,
        tenant: Tenant,
        platform_encryption_key: str
    ) -> Optional[str]:
        """Decrypt a tenant's bot token."""
        if not tenant.bot_token_encrypted:
            return None

        from nacl.secret import SecretBox
        import base64

        try:
            key = base64.b64decode(platform_encryption_key)
            box = SecretBox(key)
            encrypted = base64.b64decode(tenant.bot_token_encrypted)
            decrypted = box.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt bot token: {e}")
            return None

    def setup_totp(self, tenant_id: str) -> Optional[str]:
        """Setup TOTP for a tenant. Returns the secret."""
        import pyotp
        secret = pyotp.random_base32()

        tenant = self.db.update_tenant(tenant_id, totp_secret=secret)
        if tenant:
            self.db.log_action(
                action="totp_enabled",
                tenant_id=tenant_id
            )
            return secret
        return None

    def verify_totp(self, tenant_id: str, token: str) -> bool:
        """Verify a TOTP token."""
        import pyotp
        tenant = self.db.get_tenant(tenant_id)
        if not tenant or not tenant.totp_secret:
            return False

        totp = pyotp.TOTP(tenant.totp_secret)
        return totp.verify(token)

    def deactivate_tenant(self, tenant_id: str) -> bool:
        """Deactivate a tenant (stop bot, mark inactive)."""
        tenant = self.db.update_tenant(
            tenant_id,
            bot_active=False
        )

        if tenant:
            logger.info(f"Tenant deactivated: {tenant_id}")
            self.db.log_action(
                action="tenant_deactivated",
                tenant_id=tenant_id
            )
            return True
        return False

    def has_overdue_invoices(self, tenant_id: str) -> bool:
        """Check if tenant has any overdue invoices."""
        overdue = self.db.get_overdue_invoices(tenant_id)
        return len(overdue) > 0

    def get_tenant_stats(self, tenant_id: str) -> dict:
        """Get statistics for a tenant."""
        products = self.db.get_products(tenant_id, active_only=False)
        orders = self.db.get_orders(tenant_id)

        paid_orders = [o for o in orders if o.state in [OrderState.PAID, OrderState.FULFILLED]]
        total_revenue = sum(o.total_xmr for o in paid_orders)
        total_commission = sum(o.commission_xmr for o in paid_orders)

        return {
            "total_products": len(products),
            "active_products": len([p for p in products if p.active]),
            "total_orders": len(orders),
            "paid_orders": len(paid_orders),
            "pending_orders": len([o for o in orders if o.state == OrderState.PENDING]),
            "total_revenue_xmr": total_revenue,
            "total_commission_xmr": total_commission,
            "net_revenue_xmr": total_revenue - total_commission
        }
