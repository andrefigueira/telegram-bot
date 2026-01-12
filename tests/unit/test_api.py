"""Tests for API authentication and utilities."""

import pytest
from datetime import datetime, timedelta
from unittest.mock import patch, MagicMock

from bot.api.auth import (
    create_access_token, decode_token, TokenData, TokenResponse,
    JWT_SECRET, JWT_ALGORITHM
)


class TestJWTAuth:
    """Test JWT authentication."""

    def test_create_access_token(self):
        """Test creating an access token."""
        token_response = create_access_token("tenant-123", "test@example.com")

        assert token_response.access_token is not None
        assert token_response.token_type == "bearer"
        assert token_response.expires_in > 0

    def test_decode_token(self):
        """Test decoding a valid token."""
        token_response = create_access_token("tenant-456", "user@test.com")

        decoded = decode_token(token_response.access_token)

        assert decoded.tenant_id == "tenant-456"
        assert decoded.email == "user@test.com"

    def test_decode_invalid_token(self):
        """Test decoding an invalid token raises error."""
        from fastapi import HTTPException

        with pytest.raises(HTTPException) as exc_info:
            decode_token("invalid.token.here")

        assert exc_info.value.status_code == 401

    def test_decode_expired_token(self):
        """Test decoding an expired token raises error."""
        import jwt
        from fastapi import HTTPException

        # Create an expired token
        payload = {
            "tenant_id": "test",
            "email": "test@test.com",
            "exp": datetime.utcnow() - timedelta(hours=1),
            "iat": datetime.utcnow() - timedelta(hours=2)
        }
        expired_token = jwt.encode(payload, JWT_SECRET, algorithm=JWT_ALGORITHM)

        with pytest.raises(HTTPException) as exc_info:
            decode_token(expired_token)

        assert exc_info.value.status_code == 401
        assert "expired" in exc_info.value.detail.lower()

    def test_token_data_model(self):
        """Test TokenData model."""
        data = TokenData(
            tenant_id="test-id",
            email="test@test.com",
            exp=datetime.utcnow() + timedelta(hours=24)
        )

        assert data.tenant_id == "test-id"
        assert data.email == "test@test.com"

    def test_token_response_model(self):
        """Test TokenResponse model."""
        response = TokenResponse(
            access_token="some.jwt.token",
            expires_in=3600
        )

        assert response.access_token == "some.jwt.token"
        assert response.token_type == "bearer"
        assert response.expires_in == 3600

    def test_roundtrip_token(self):
        """Test creating and decoding token preserves data."""
        original_tenant = "my-tenant-uuid"
        original_email = "myemail@example.com"

        token = create_access_token(original_tenant, original_email)
        decoded = decode_token(token.access_token)

        assert decoded.tenant_id == original_tenant
        assert decoded.email == original_email

    def test_token_contains_expiration(self):
        """Test token contains future expiration."""
        token = create_access_token("test", "test@test.com")
        decoded = decode_token(token.access_token)

        assert decoded.exp > datetime.utcnow()

    def test_different_tenants_get_different_tokens(self):
        """Test different tenants get unique tokens."""
        token1 = create_access_token("tenant-1", "user1@test.com")
        token2 = create_access_token("tenant-2", "user2@test.com")

        assert token1.access_token != token2.access_token

        decoded1 = decode_token(token1.access_token)
        decoded2 = decode_token(token2.access_token)

        assert decoded1.tenant_id == "tenant-1"
        assert decoded2.tenant_id == "tenant-2"


class TestBackgroundTasks:
    """Test background task manager."""

    def test_task_manager_initialization(self):
        """Test BackgroundTaskManager can be initialized."""
        from bot.tasks_multitenant import BackgroundTaskManager
        from bot.models_multitenant import MultiTenantDatabase
        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            db = MultiTenantDatabase(f"sqlite:///{path}")
            swap_service = CryptoSwapService(testnet=True)
            order_service = MultiCryptoOrderService(db, swap_service)
            commission_service = CommissionService(db, "4TestAddress...")

            task_manager = BackgroundTaskManager(
                db=db,
                order_service=order_service,
                commission_service=commission_service
            )

            assert task_manager is not None
            assert task_manager._running is False
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_run_once_swap_check(self):
        """Test running swap check once."""
        from bot.tasks_multitenant import BackgroundTaskManager
        from bot.models_multitenant import MultiTenantDatabase
        from bot.services.crypto_swap import CryptoSwapService
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.commission import CommissionService
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            db = MultiTenantDatabase(f"sqlite:///{path}")
            swap_service = CryptoSwapService(testnet=True)
            order_service = MultiCryptoOrderService(db, swap_service)
            commission_service = CommissionService(db, "4TestAddress...")

            task_manager = BackgroundTaskManager(
                db=db,
                order_service=order_service,
                commission_service=commission_service
            )

            result = await task_manager.run_once_swap_check()

            assert "checked" in result
            assert "completed" in result
            assert "failed" in result
        finally:
            os.unlink(path)


class TestPlatform:
    """Test DarkPool platform."""

    def test_platform_initialization(self):
        """Test platform can be initialized."""
        from bot.main_multitenant import DarkPoolPlatform
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            platform = DarkPoolPlatform(
                database_url=f"sqlite:///{path}",
                testnet=True
            )

            platform.initialize()

            assert platform.db is not None
            assert platform.swap_service is not None
            assert platform.tenant_service is not None
            assert platform.order_service is not None
            assert platform.commission_service is not None
            assert platform.bot_manager is not None
            assert platform.task_manager is not None
        finally:
            os.unlink(path)

    def test_platform_get_services(self):
        """Test getting services from platform."""
        from bot.main_multitenant import DarkPoolPlatform
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            platform = DarkPoolPlatform(
                database_url=f"sqlite:///{path}",
                testnet=True
            )

            platform.initialize()
            services = platform.get_services()

            assert "db" in services
            assert "tenant_service" in services
            assert "order_service" in services
            assert "commission_service" in services
            assert "bot_manager" in services
            assert "swap_service" in services
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_platform_start_stop(self):
        """Test starting and stopping platform."""
        from bot.main_multitenant import DarkPoolPlatform
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            platform = DarkPoolPlatform(
                database_url=f"sqlite:///{path}",
                testnet=True
            )

            platform.initialize()

            # Start platform
            await platform.start()
            assert platform._running is True

            # Stop platform
            await platform.stop()
            assert platform._running is False
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_platform_double_start(self):
        """Test calling start twice logs warning."""
        from bot.main_multitenant import DarkPoolPlatform
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            platform = DarkPoolPlatform(
                database_url=f"sqlite:///{path}",
                testnet=True
            )

            platform.initialize()

            # Start platform first time
            await platform.start()
            assert platform._running is True

            # Start platform second time (should just warn and return)
            await platform.start()
            assert platform._running is True

            # Stop platform
            await platform.stop()
        finally:
            os.unlink(path)

    @pytest.mark.asyncio
    async def test_platform_stop_when_not_running(self):
        """Test stopping platform when not running does nothing."""
        from bot.main_multitenant import DarkPoolPlatform
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        try:
            platform = DarkPoolPlatform(
                database_url=f"sqlite:///{path}",
                testnet=True
            )

            platform.initialize()

            # Stop without starting (should just return)
            await platform.stop()
            assert platform._running is False
        finally:
            os.unlink(path)

    def test_get_platform_not_initialized(self):
        """Test get_platform raises error when not initialized."""
        import bot.main_multitenant as module

        # Save current state
        old_platform = module._platform
        module._platform = None

        try:
            with pytest.raises(RuntimeError, match="Platform not initialized"):
                module.get_platform()
        finally:
            # Restore state
            module._platform = old_platform

    def test_create_platform_with_env_vars(self):
        """Test create_platform reads from environment variables."""
        from bot.main_multitenant import create_platform
        import bot.main_multitenant as module
        import tempfile
        import os

        fd, path = tempfile.mkstemp(suffix='.db')
        os.close(fd)

        # Save current state
        old_platform = module._platform
        module._platform = None

        try:
            with patch.dict(os.environ, {
                'DATABASE_URL': f"sqlite:///{path}",
                'PLATFORM_XMR_ADDRESS': '4TestAddress',
                'TESTNET': 'true',
            }):
                platform = create_platform()
                assert platform is not None
                assert platform.testnet is True
                assert platform.platform_xmr_address == '4TestAddress'
        finally:
            module._platform = old_platform
            os.unlink(path)
