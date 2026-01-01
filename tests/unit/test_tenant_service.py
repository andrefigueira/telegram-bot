"""Tests for tenant management service."""

import pytest
import base64
import os
import tempfile
from unittest.mock import patch, MagicMock

from bot.services.tenant import TenantService
from bot.models_multitenant import MultiTenantDatabase, OrderState


class TestTenantService:
    """Test TenantService functionality."""

    @pytest.fixture
    def db(self):
        """Create a test database."""
        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)
        db = MultiTenantDatabase(f"sqlite:///{path}")
        yield db
        os.unlink(path)

    @pytest.fixture
    def tenant_service(self, db):
        """Create tenant service instance."""
        return TenantService(db)

    @pytest.fixture
    def platform_key(self):
        """Generate a platform encryption key."""
        return base64.b64encode(os.urandom(32)).decode('utf-8')

    # ==================== REGISTRATION TESTS ====================

    def test_register_success(self, tenant_service):
        """Test successful tenant registration."""
        tenant = tenant_service.register(
            email="test@example.com",
            password="secure_password",
            accept_terms=True
        )

        assert tenant is not None
        assert tenant.email == "test@example.com"
        assert tenant.password_hash != "secure_password"  # Should be hashed
        assert tenant.accepted_terms_version == "1.0"

    def test_register_without_terms(self, tenant_service):
        """Test registration fails without accepting terms."""
        with pytest.raises(ValueError, match="Terms must be accepted"):
            tenant_service.register(
                email="test@example.com",
                password="password",
                accept_terms=False
            )

    def test_register_duplicate_email(self, tenant_service):
        """Test registration fails with duplicate email."""
        tenant_service.register("test@example.com", "password", True)

        with pytest.raises(ValueError, match="already registered"):
            tenant_service.register("test@example.com", "password2", True)

    # ==================== AUTHENTICATION TESTS ====================

    def test_authenticate_success(self, tenant_service):
        """Test successful authentication."""
        tenant_service.register("auth@test.com", "correct_password", True)

        tenant = tenant_service.authenticate("auth@test.com", "correct_password")
        assert tenant is not None
        assert tenant.email == "auth@test.com"

    def test_authenticate_wrong_password(self, tenant_service):
        """Test authentication fails with wrong password."""
        tenant_service.register("auth@test.com", "correct_password", True)

        tenant = tenant_service.authenticate("auth@test.com", "wrong_password")
        assert tenant is None

    def test_authenticate_nonexistent_email(self, tenant_service):
        """Test authentication fails for non-existent user."""
        tenant = tenant_service.authenticate("nobody@test.com", "password")
        assert tenant is None

    # ==================== PROFILE TESTS ====================

    def test_update_profile(self, tenant_service):
        """Test updating tenant profile."""
        tenant = tenant_service.register("profile@test.com", "pass", True)

        updated = tenant_service.update_profile(
            tenant.id,
            shop_name="My Awesome Shop",
            monero_wallet_address="4AAAA..."
        )

        assert updated.shop_name == "My Awesome Shop"
        assert updated.monero_wallet_address == "4AAAA..."

    def test_update_profile_partial(self, tenant_service):
        """Test partial profile update."""
        tenant = tenant_service.register("partial@test.com", "pass", True)

        # Update only shop name
        updated = tenant_service.update_profile(tenant.id, shop_name="Shop Only")

        assert updated.shop_name == "Shop Only"
        assert updated.monero_wallet_address is None

    # ==================== BOT CONNECTION TESTS ====================

    def test_connect_bot(self, tenant_service, platform_key):
        """Test connecting a bot."""
        tenant = tenant_service.register("bot@test.com", "pass", True)

        updated = tenant_service.connect_bot(
            tenant.id,
            bot_token="123456789:ABCdefGHIjklMNOpqrsTUVwxyz",
            platform_encryption_key=platform_key
        )

        assert updated.bot_token_encrypted is not None
        assert updated.bot_active is True
        assert updated.bot_username is not None

    def test_disconnect_bot(self, tenant_service, platform_key):
        """Test disconnecting a bot."""
        tenant = tenant_service.register("disconnect@test.com", "pass", True)
        tenant_service.connect_bot(tenant.id, "token:abc", platform_key)

        updated = tenant_service.disconnect_bot(tenant.id)

        assert updated.bot_token_encrypted is None
        assert updated.bot_active is False
        assert updated.bot_username is None

    def test_decrypt_bot_token(self, tenant_service, platform_key):
        """Test decrypting bot token."""
        tenant = tenant_service.register("decrypt@test.com", "pass", True)
        original_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

        tenant_service.connect_bot(tenant.id, original_token, platform_key)

        # Get fresh tenant from DB
        tenant = tenant_service.get_tenant(tenant.id)
        decrypted = tenant_service.decrypt_bot_token(tenant, platform_key)

        assert decrypted == original_token

    def test_decrypt_bot_token_no_token(self, tenant_service, platform_key):
        """Test decrypting when no token is set."""
        tenant = tenant_service.register("notoken@test.com", "pass", True)
        tenant = tenant_service.get_tenant(tenant.id)

        decrypted = tenant_service.decrypt_bot_token(tenant, platform_key)
        assert decrypted is None

    # ==================== TOTP TESTS ====================

    def test_setup_totp(self, tenant_service):
        """Test TOTP setup."""
        tenant = tenant_service.register("totp@test.com", "pass", True)

        secret = tenant_service.setup_totp(tenant.id)

        assert secret is not None
        assert len(secret) == 32  # pyotp base32 secret length

    def test_verify_totp(self, tenant_service):
        """Test TOTP verification."""
        import pyotp

        tenant = tenant_service.register("verify@test.com", "pass", True)
        secret = tenant_service.setup_totp(tenant.id)

        # Generate valid token
        totp = pyotp.TOTP(secret)
        valid_token = totp.now()

        assert tenant_service.verify_totp(tenant.id, valid_token) is True
        assert tenant_service.verify_totp(tenant.id, "000000") is False

    def test_verify_totp_no_secret(self, tenant_service):
        """Test TOTP verification when not set up."""
        tenant = tenant_service.register("nototp@test.com", "pass", True)

        assert tenant_service.verify_totp(tenant.id, "123456") is False

    # ==================== DEACTIVATION TESTS ====================

    def test_deactivate_tenant(self, tenant_service, platform_key):
        """Test deactivating a tenant."""
        tenant = tenant_service.register("deactivate@test.com", "pass", True)
        tenant_service.connect_bot(tenant.id, "token:abc", platform_key)

        result = tenant_service.deactivate_tenant(tenant.id)
        assert result is True

        tenant = tenant_service.get_tenant(tenant.id)
        assert tenant.bot_active is False

    # ==================== INVOICE TESTS ====================

    def test_has_overdue_invoices_none(self, tenant_service, db):
        """Test checking for overdue invoices when none exist."""
        tenant = tenant_service.register("nooverdue@test.com", "pass", True)

        assert tenant_service.has_overdue_invoices(tenant.id) is False

    def test_has_overdue_invoices_exists(self, tenant_service, db):
        """Test checking for overdue invoices when they exist."""
        from datetime import date, datetime
        from decimal import Decimal

        tenant = tenant_service.register("hasoverdue@test.com", "pass", True)

        # Create and mark invoice as overdue
        invoice = db.create_commission_invoice(
            tenant.id,
            date(2024, 1, 1), date(2024, 1, 7),
            5, Decimal("25"), Decimal("0.05"), Decimal("1.25"),
            "4AAA...", datetime(2024, 1, 14)
        )
        db.mark_invoice_overdue(invoice.id)

        assert tenant_service.has_overdue_invoices(tenant.id) is True

    # ==================== STATISTICS TESTS ====================

    def test_get_tenant_stats_empty(self, tenant_service):
        """Test getting stats for tenant with no activity."""
        tenant = tenant_service.register("stats@test.com", "pass", True)

        stats = tenant_service.get_tenant_stats(tenant.id)

        assert stats["total_products"] == 0
        assert stats["total_orders"] == 0
        assert stats["total_revenue_xmr"] == 0

    def test_get_tenant_stats_with_data(self, tenant_service, db):
        """Test getting stats for tenant with activity."""
        from decimal import Decimal

        tenant = tenant_service.register("fullstats@test.com", "pass", True)

        # Create products
        p1 = db.create_product(tenant.id, "Product 1", Decimal("1.0"), 10)
        p2 = db.create_product(tenant.id, "Product 2", Decimal("2.0"), 5)
        p3 = db.create_product(tenant.id, "Inactive", Decimal("3.0"), 0)
        db.update_product(p3.id, tenant.id, active=False)

        # Create orders
        order1 = db.create_order(
            tenant.id, p1.id, 12345, 2, Decimal("2.0"),
            Decimal("0.1"), "xmr", Decimal("2.0"), "addr", "enc"
        )
        db.update_order_state(order1.id, tenant.id, OrderState.PAID)

        order2 = db.create_order(
            tenant.id, p2.id, 12346, 1, Decimal("2.0"),
            Decimal("0.1"), "xmr", Decimal("2.0"), "addr", "enc"
        )
        # Leave order2 as pending

        stats = tenant_service.get_tenant_stats(tenant.id)

        assert stats["total_products"] == 3
        assert stats["active_products"] == 2
        assert stats["total_orders"] == 2
        assert stats["paid_orders"] == 1
        assert stats["pending_orders"] == 1
        assert stats["total_revenue_xmr"] == Decimal("2.0")
        assert stats["total_commission_xmr"] == Decimal("0.1")
        assert stats["net_revenue_xmr"] == Decimal("1.9")

    # ==================== EDGE CASE TESTS ====================

    def test_update_profile_no_changes(self, tenant_service):
        """Test profile update with no changes returns current tenant."""
        tenant = tenant_service.register("nochange@test.com", "pass", True)

        # Update without providing any values
        result = tenant_service.update_profile(tenant.id)

        assert result is not None
        assert result.id == tenant.id

    def test_update_profile_all_fields(self, tenant_service):
        """Test profile update with all fields including view key."""
        tenant = tenant_service.register("allfields@test.com", "pass", True)

        updated = tenant_service.update_profile(
            tenant.id,
            shop_name="Complete Shop",
            monero_wallet_address="4AAAA...",
            monero_view_key="viewkey123"
        )

        assert updated.shop_name == "Complete Shop"
        assert updated.monero_wallet_address == "4AAAA..."
        assert updated.monero_view_key == "viewkey123"

    def test_update_profile_nonexistent(self, tenant_service):
        """Test profile update for nonexistent tenant."""
        result = tenant_service.update_profile("nonexistent_id", shop_name="Test")

        assert result is None

    def test_connect_bot_invalid_token_format(self, tenant_service, platform_key):
        """Test connecting bot with invalid token format."""
        tenant = tenant_service.register("badtoken@test.com", "pass", True)

        # Token without colon separator - triggers exception path
        updated = tenant_service.connect_bot(
            tenant.id,
            bot_token="invalid_token_no_colon",
            platform_encryption_key=platform_key
        )

        assert updated is not None
        assert updated.bot_token_encrypted is not None
        # bot_username might be None due to exception
        assert updated.bot_active is True

    def test_connect_bot_nonexistent_tenant(self, tenant_service, platform_key):
        """Test connecting bot for nonexistent tenant."""
        result = tenant_service.connect_bot(
            "nonexistent_tenant",
            bot_token="123:token",
            platform_encryption_key=platform_key
        )

        assert result is None

    def test_disconnect_bot_nonexistent(self, tenant_service):
        """Test disconnecting bot for nonexistent tenant."""
        result = tenant_service.disconnect_bot("nonexistent_id")

        assert result is None

    def test_setup_totp_nonexistent(self, tenant_service):
        """Test TOTP setup for nonexistent tenant."""
        result = tenant_service.setup_totp("nonexistent_id")

        assert result is None

    def test_deactivate_nonexistent_tenant(self, tenant_service):
        """Test deactivating nonexistent tenant."""
        result = tenant_service.deactivate_tenant("nonexistent_id")

        assert result is False

    def test_get_tenant_stats_nonexistent(self, tenant_service):
        """Test getting stats for nonexistent tenant."""
        stats = tenant_service.get_tenant_stats("nonexistent_id")

        # Should return empty stats
        assert stats["total_products"] == 0
        assert stats["total_orders"] == 0

    def test_decrypt_bot_token_wrong_key(self, tenant_service, platform_key):
        """Test decrypting bot token with wrong key returns None."""
        tenant = tenant_service.register("wrongkey@test.com", "pass", True)
        original_token = "123456789:ABCdefGHIjklMNOpqrsTUVwxyz"

        tenant_service.connect_bot(tenant.id, original_token, platform_key)

        # Get fresh tenant from DB
        tenant = tenant_service.get_tenant(tenant.id)

        # Try to decrypt with a different key - should fail and return None
        wrong_key = base64.b64encode(os.urandom(32)).decode('utf-8')
        decrypted = tenant_service.decrypt_bot_token(tenant, wrong_key)

        assert decrypted is None

    def test_connect_bot_token_parse_exception(self, tenant_service, platform_key):
        """Test connect_bot handles exception during token parsing."""
        tenant = tenant_service.register("parseexc@test.com", "pass", True)

        # Create a mock token that can be encoded but raises on split
        class MockToken:
            def encode(self, encoding):
                return b"mocktoken"
            def split(self, sep):
                raise RuntimeError("Parse error")

        mock_token = MockToken()
        updated = tenant_service.connect_bot(
            tenant.id,
            bot_token=mock_token,
            platform_encryption_key=platform_key
        )

        # Should still succeed but with bot_username as None
        assert updated is not None
        assert updated.bot_token_encrypted is not None
        assert updated.bot_username is None  # Due to exception
        assert updated.bot_active is True
