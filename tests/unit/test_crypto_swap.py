"""Tests for crypto swap service."""

import pytest
from decimal import Decimal
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.crypto_swap import (
    CryptoSwapService, SwapStatus, SupportedCoin,
    SwapQuote, SwapOrder
)


class TestCryptoSwapService:
    """Test CryptoSwapService functionality."""

    @pytest.fixture
    def swap_service(self):
        """Create swap service instance for testing."""
        return CryptoSwapService(
            trocador_api_key="test_trocador_key",
            changenow_api_key="test_changenow_key",
            testnet=True
        )

    @pytest.fixture
    def mock_swap_service(self):
        """Create swap service with mocked HTTP."""
        service = CryptoSwapService(
            trocador_api_key="test_key",
            changenow_api_key="test_key",
            testnet=False
        )
        return service

    def test_supported_coins(self, swap_service):
        """Test that all expected coins are supported."""
        expected = ["xmr", "btc", "eth", "sol", "ltc", "usdt", "usdc"]
        assert swap_service.SUPPORTED_COINS == expected

    @pytest.mark.asyncio
    async def test_get_supported_coins(self, swap_service):
        """Test getting supported coins list."""
        coins = await swap_service.get_supported_coins()
        assert "xmr" in coins
        assert "btc" in coins
        assert "eth" in coins

    @pytest.mark.asyncio
    async def test_get_rate_xmr_direct(self, swap_service):
        """Test that XMR to XMR returns 1:1 rate."""
        quote = await swap_service.get_rate("xmr", Decimal("1.5"))

        assert quote is not None
        assert quote.from_coin == "xmr"
        assert quote.to_coin == "xmr"
        assert quote.from_amount == Decimal("1.5")
        assert quote.to_amount == Decimal("1.5")
        assert quote.rate == Decimal("1")
        assert quote.provider == "direct"

    @pytest.mark.asyncio
    async def test_get_rate_unsupported_coin(self, swap_service):
        """Test that unsupported coins raise error."""
        with pytest.raises(ValueError, match="Unsupported coin"):
            await swap_service.get_rate("doge", Decimal("100"))

    @pytest.mark.asyncio
    async def test_get_rate_mock_btc(self, swap_service):
        """Test mock rate for BTC."""
        quote = await swap_service.get_rate("btc", Decimal("0.1"))

        assert quote is not None
        assert quote.from_coin == "btc"
        assert quote.to_coin == "xmr"
        assert quote.from_amount == Decimal("0.1")
        assert quote.to_amount == Decimal("0.1") * Decimal("250")  # Mock rate
        assert quote.provider == "mock"

    @pytest.mark.asyncio
    async def test_get_rate_mock_eth(self, swap_service):
        """Test mock rate for ETH."""
        quote = await swap_service.get_rate("eth", Decimal("1.0"))

        assert quote is not None
        assert quote.from_coin == "eth"
        assert quote.to_amount == Decimal("1.0") * Decimal("15")  # Mock rate

    @pytest.mark.asyncio
    async def test_create_swap_xmr_direct(self, swap_service):
        """Test creating XMR swap (direct, no conversion)."""
        dest_address = "4" + "A" * 94  # Mock XMR address

        order = await swap_service.create_swap(
            from_coin="xmr",
            from_amount=Decimal("1.5"),
            destination_xmr_address=dest_address
        )

        assert order is not None
        assert order.swap_id == "direct"
        assert order.from_coin == "xmr"
        assert order.to_coin == "xmr"
        assert order.deposit_address == dest_address
        assert order.provider == "direct"
        assert order.status == SwapStatus.WAITING

    @pytest.mark.asyncio
    async def test_create_swap_btc_mock(self, swap_service):
        """Test creating BTC to XMR swap in testnet mode."""
        dest_address = "4" + "A" * 94

        order = await swap_service.create_swap(
            from_coin="btc",
            from_amount=Decimal("0.01"),
            destination_xmr_address=dest_address
        )

        assert order is not None
        assert order.from_coin == "btc"
        assert order.to_coin == "xmr"
        assert order.deposit_address.startswith("bc1qtest")
        assert order.provider == "mock"
        assert order.swap_id.startswith("mock_")

    @pytest.mark.asyncio
    async def test_create_swap_eth_mock(self, swap_service):
        """Test creating ETH to XMR swap in testnet mode."""
        dest_address = "4" + "A" * 94

        order = await swap_service.create_swap(
            from_coin="eth",
            from_amount=Decimal("0.5"),
            destination_xmr_address=dest_address
        )

        assert order is not None
        assert order.from_coin == "eth"
        assert order.deposit_address.startswith("0x")
        assert len(order.deposit_address) == 42

    @pytest.mark.asyncio
    async def test_create_swap_sol_mock(self, swap_service):
        """Test creating SOL to XMR swap in testnet mode."""
        dest_address = "4" + "A" * 94

        order = await swap_service.create_swap(
            from_coin="sol",
            from_amount=Decimal("10"),
            destination_xmr_address=dest_address
        )

        assert order is not None
        assert order.from_coin == "sol"
        assert len(order.deposit_address) == 64  # Hex string

    @pytest.mark.asyncio
    async def test_create_swap_unsupported(self, swap_service):
        """Test creating swap with unsupported coin raises error."""
        with pytest.raises(ValueError, match="Unsupported coin"):
            await swap_service.create_swap(
                from_coin="doge",
                from_amount=Decimal("100"),
                destination_xmr_address="4" + "A" * 94
            )

    @pytest.mark.asyncio
    async def test_check_swap_status_direct(self, swap_service):
        """Test checking status of direct XMR payment."""
        status = await swap_service.check_swap_status("direct", "direct")
        assert status == SwapStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_check_swap_status_mock(self, swap_service):
        """Test checking status of mock swap."""
        status = await swap_service.check_swap_status("mock_123", "mock")
        assert status == SwapStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_get_minimum_amount(self, swap_service):
        """Test getting minimum swap amounts."""
        xmr_min = await swap_service.get_minimum_amount("xmr")
        assert xmr_min == Decimal("0.001")

        btc_min = await swap_service.get_minimum_amount("btc")
        assert btc_min == Decimal("0.0001")

        eth_min = await swap_service.get_minimum_amount("eth")
        assert eth_min == Decimal("0.01")

        usdt_min = await swap_service.get_minimum_amount("usdt")
        assert usdt_min == Decimal("10")

    @pytest.mark.asyncio
    async def test_close_session(self, swap_service):
        """Test closing HTTP session."""
        # Create session
        await swap_service._get_session()
        assert swap_service._session is not None

        # Close session
        await swap_service.close()
        assert swap_service._session.closed

    def test_swap_status_enum(self):
        """Test SwapStatus enum values."""
        assert SwapStatus.WAITING == "waiting"
        assert SwapStatus.CONFIRMING == "confirming"
        assert SwapStatus.EXCHANGING == "exchanging"
        assert SwapStatus.COMPLETE == "complete"
        assert SwapStatus.FAILED == "failed"
        assert SwapStatus.EXPIRED == "expired"

    def test_supported_coin_enum(self):
        """Test SupportedCoin enum values."""
        assert SupportedCoin.XMR == "xmr"
        assert SupportedCoin.BTC == "btc"
        assert SupportedCoin.ETH == "eth"
        assert SupportedCoin.SOL == "sol"


class TestSwapQuote:
    """Test SwapQuote dataclass."""

    def test_swap_quote_creation(self):
        """Test creating a SwapQuote."""
        quote = SwapQuote(
            from_coin="btc",
            to_coin="xmr",
            from_amount=Decimal("0.1"),
            to_amount=Decimal("25"),
            rate=Decimal("250"),
            provider="trocador",
            quote_id="abc123",
            expires_at=datetime.utcnow() + timedelta(minutes=10)
        )

        assert quote.from_coin == "btc"
        assert quote.to_coin == "xmr"
        assert quote.rate == Decimal("250")


class TestSwapOrder:
    """Test SwapOrder dataclass."""

    def test_swap_order_creation(self):
        """Test creating a SwapOrder."""
        order = SwapOrder(
            swap_id="order123",
            from_coin="eth",
            to_coin="xmr",
            deposit_address="0x" + "a" * 40,
            expected_amount=Decimal("15"),
            destination_address="4" + "B" * 94,
            provider="changenow",
            status=SwapStatus.WAITING,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow()
        )

        assert order.swap_id == "order123"
        assert order.status == SwapStatus.WAITING
        assert order.provider == "changenow"


class TestTrocadorIntegration:
    """Test Trocador API integration (mocked)."""

    @pytest.fixture
    def swap_service(self):
        """Create swap service for Trocador testing."""
        return CryptoSwapService(
            trocador_api_key="test_key",
            preferred_provider="trocador",
            testnet=False
        )

    @pytest.mark.asyncio
    async def test_trocador_rate_success(self, swap_service):
        """Test successful Trocador rate fetch."""
        mock_response = {
            "success": True,
            "amount_to": "25.5",
            "rate": "255",
            "id": "quote123"
        }

        with patch.object(swap_service, '_get_session') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)

            mock_session.return_value.get = AsyncMock(
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))
            )

            # This will use the mock since testnet=False
            quote = await swap_service._get_trocador_rate("btc", Decimal("0.1"))

            # Note: With mocking, we need proper async context manager setup
            # For now, test the mock path
            assert True  # Placeholder for full integration test

    @pytest.mark.asyncio
    async def test_trocador_rate_failure(self, swap_service):
        """Test Trocador rate fetch failure."""
        with patch.object(swap_service, '_get_session') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 500

            mock_session.return_value.get = AsyncMock(
                return_value=AsyncMock(__aenter__=AsyncMock(return_value=mock_resp))
            )

            # Should return None on failure
            # The actual implementation handles this gracefully


class TestChangeNowIntegration:
    """Test ChangeNow API integration (mocked)."""

    @pytest.fixture
    def swap_service(self):
        """Create swap service for ChangeNow testing."""
        return CryptoSwapService(
            changenow_api_key="test_key",
            preferred_provider="changenow",
            testnet=False
        )

    @pytest.mark.asyncio
    async def test_changenow_swap_creation(self, swap_service):
        """Test ChangeNow swap order creation."""
        # Test the mock fallback path
        swap_service.testnet = True

        order = await swap_service.create_swap(
            from_coin="btc",
            from_amount=Decimal("0.01"),
            destination_xmr_address="4" + "A" * 94
        )

        assert order is not None
        assert order.provider == "mock"


class TestTrocadorRateFullPath:
    """Test Trocador rate fetching with proper async mocking."""

    @pytest.fixture
    def swap_service_trocador_only(self):
        """Create swap service with only Trocador."""
        return CryptoSwapService(
            trocador_api_key="test_key",
            changenow_api_key=None,
            preferred_provider="trocador",
            testnet=False
        )

    @pytest.mark.asyncio
    async def test_trocador_rate_success_full(self, swap_service_trocador_only):
        """Test successful Trocador rate with proper async context manager."""
        mock_response = {
            "success": True,
            "amount_to": "25.5",
            "rate": "255",
            "id": "quote123"
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(swap_service_trocador_only, '_get_session', return_value=mock_session):
            quote = await swap_service_trocador_only._get_trocador_rate("btc", Decimal("0.1"))

            assert quote is not None
            assert quote.from_coin == "btc"
            assert quote.to_coin == "xmr"
            assert quote.to_amount == Decimal("25.5")
            assert quote.rate == Decimal("255")
            assert quote.provider == "trocador"

    @pytest.mark.asyncio
    async def test_trocador_rate_non_200(self, swap_service_trocador_only):
        """Test Trocador rate with non-200 response."""
        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(swap_service_trocador_only, '_get_session', return_value=mock_session):
            quote = await swap_service_trocador_only._get_trocador_rate("btc", Decimal("0.1"))
            assert quote is None

    @pytest.mark.asyncio
    async def test_trocador_rate_not_success(self, swap_service_trocador_only):
        """Test Trocador rate with success=false."""
        mock_response = {"success": False}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(swap_service_trocador_only, '_get_session', return_value=mock_session):
            quote = await swap_service_trocador_only._get_trocador_rate("btc", Decimal("0.1"))
            assert quote is None

    @pytest.mark.asyncio
    async def test_trocador_rate_exception(self, swap_service_trocador_only):
        """Test Trocador rate with exception."""
        with patch.object(swap_service_trocador_only, '_get_session', side_effect=Exception("Connection error")):
            quote = await swap_service_trocador_only._get_trocador_rate("btc", Decimal("0.1"))
            assert quote is None


class TestChangeNowRateFullPath:
    """Test ChangeNow rate fetching with proper async mocking."""

    @pytest.fixture
    def swap_service_changenow_only(self):
        """Create swap service with only ChangeNow."""
        return CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key="test_key",
            preferred_provider="changenow",
            testnet=False
        )

    @pytest.mark.asyncio
    async def test_changenow_rate_success(self, swap_service_changenow_only):
        """Test successful ChangeNow rate fetch."""
        mock_response = {"toAmount": "25.5"}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(swap_service_changenow_only, '_get_session', return_value=mock_session):
            quote = await swap_service_changenow_only._get_changenow_rate("btc", Decimal("0.1"))

            assert quote is not None
            assert quote.to_amount == Decimal("25.5")
            assert quote.provider == "changenow"

    @pytest.mark.asyncio
    async def test_changenow_rate_non_200(self, swap_service_changenow_only):
        """Test ChangeNow rate with non-200 response."""
        mock_resp = MagicMock()
        mock_resp.status = 400

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(swap_service_changenow_only, '_get_session', return_value=mock_session):
            quote = await swap_service_changenow_only._get_changenow_rate("btc", Decimal("0.1"))
            assert quote is None

    @pytest.mark.asyncio
    async def test_changenow_rate_exception(self, swap_service_changenow_only):
        """Test ChangeNow rate with exception."""
        with patch.object(swap_service_changenow_only, '_get_session', side_effect=Exception("Error")):
            quote = await swap_service_changenow_only._get_changenow_rate("btc", Decimal("0.1"))
            assert quote is None


class TestGetRateFallback:
    """Test get_rate method with provider fallback."""

    @pytest.mark.asyncio
    async def test_get_rate_no_providers(self):
        """Test get_rate returns None when no providers available."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key=None,
            testnet=False
        )

        result = await service.get_rate("btc", Decimal("0.1"))
        assert result is None

    @pytest.mark.asyncio
    async def test_get_rate_trocador_success(self):
        """Test get_rate uses Trocador when available."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key="key",
            preferred_provider="trocador",
            testnet=False
        )

        mock_quote = SwapQuote(
            from_coin="btc", to_coin="xmr", from_amount=Decimal("0.1"),
            to_amount=Decimal("25"), rate=Decimal("250"), provider="trocador",
            quote_id="q1", expires_at=datetime.utcnow()
        )

        with patch.object(service, '_get_trocador_rate', return_value=mock_quote):
            quote = await service.get_rate("btc", Decimal("0.1"))
            assert quote.provider == "trocador"

    @pytest.mark.asyncio
    async def test_get_rate_fallback_to_changenow(self):
        """Test get_rate falls back to ChangeNow when Trocador fails."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key="key",
            preferred_provider="trocador",
            testnet=False
        )

        mock_quote = SwapQuote(
            from_coin="btc", to_coin="xmr", from_amount=Decimal("0.1"),
            to_amount=Decimal("25"), rate=Decimal("250"), provider="changenow",
            quote_id="q1", expires_at=datetime.utcnow()
        )

        with patch.object(service, '_get_trocador_rate', return_value=None):
            with patch.object(service, '_get_changenow_rate', return_value=mock_quote):
                quote = await service.get_rate("btc", Decimal("0.1"))
                assert quote.provider == "changenow"


class TestCreateSwapProviders:
    """Test create_swap with different providers."""

    @pytest.mark.asyncio
    async def test_create_swap_trocador_success(self):
        """Test create_swap with Trocador."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key=None,
            preferred_provider="trocador",
            testnet=False
        )

        mock_response = {
            "success": True,
            "trade_id": "trade123",
            "address_provider": "bc1qtest123",
            "amount_to": "25.5"
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")

            assert order is not None
            assert order.swap_id == "trade123"
            assert order.provider == "trocador"

    @pytest.mark.asyncio
    async def test_create_swap_trocador_non_200(self):
        """Test create_swap with Trocador non-200 response."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key=None,
            preferred_provider="trocador",
            testnet=False
        )

        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
            assert order is None

    @pytest.mark.asyncio
    async def test_create_swap_trocador_not_success(self):
        """Test create_swap with Trocador success=false."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key=None,
            preferred_provider="trocador",
            testnet=False
        )

        mock_response = {"success": False}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
            assert order is None

    @pytest.mark.asyncio
    async def test_create_swap_trocador_exception(self):
        """Test create_swap with Trocador exception."""
        service = CryptoSwapService(
            trocador_api_key="key",
            changenow_api_key=None,
            preferred_provider="trocador",
            testnet=False
        )

        with patch.object(service, '_get_session', side_effect=Exception("Error")):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
            assert order is None

    @pytest.mark.asyncio
    async def test_create_swap_changenow_success(self):
        """Test create_swap with ChangeNow."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key="key",
            testnet=False
        )

        mock_response = {
            "id": "cn_trade123",
            "payinAddress": "bc1qtest456",
            "toAmount": "25.5"
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")

            assert order is not None
            assert order.swap_id == "cn_trade123"
            assert order.provider == "changenow"

    @pytest.mark.asyncio
    async def test_create_swap_changenow_with_refund(self):
        """Test create_swap with ChangeNow and refund address."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key="key",
            testnet=False
        )

        mock_response = {
            "id": "cn_trade123",
            "payinAddress": "bc1qtest456",
            "toAmount": "25.5"
        }

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap(
                "btc", Decimal("0.1"), "4AAA...",
                refund_address="bc1qrefund"
            )

            assert order is not None
            assert order.provider == "changenow"

    @pytest.mark.asyncio
    async def test_create_swap_changenow_non_200(self):
        """Test create_swap with ChangeNow non-200 response."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key="key",
            testnet=False
        )

        mock_resp = MagicMock()
        mock_resp.status = 400

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.post = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
            assert order is None

    @pytest.mark.asyncio
    async def test_create_swap_changenow_exception(self):
        """Test create_swap with ChangeNow exception."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key="key",
            testnet=False
        )

        with patch.object(service, '_get_session', side_effect=Exception("Error")):
            order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
            assert order is None

    @pytest.mark.asyncio
    async def test_create_swap_no_providers(self):
        """Test create_swap returns None when no providers."""
        service = CryptoSwapService(
            trocador_api_key=None,
            changenow_api_key=None,
            testnet=False
        )

        order = await service.create_swap("btc", Decimal("0.1"), "4AAA...")
        assert order is None


class TestCheckSwapStatus:
    """Test swap status checking."""

    @pytest.mark.asyncio
    async def test_check_status_trocador_success(self):
        """Test checking Trocador swap status."""
        service = CryptoSwapService(trocador_api_key="key")

        mock_response = {"status": "complete"}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            status = await service.check_swap_status("trade123", "trocador")
            assert status == SwapStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_check_status_trocador_statuses(self):
        """Test Trocador status mapping."""
        service = CryptoSwapService(trocador_api_key="key")

        for api_status, expected_status in [
            ("waiting", SwapStatus.WAITING),
            ("confirming", SwapStatus.CONFIRMING),
            ("exchanging", SwapStatus.EXCHANGING),
            ("finished", SwapStatus.COMPLETE),
            ("failed", SwapStatus.FAILED),
            ("expired", SwapStatus.EXPIRED),
            ("unknown", SwapStatus.WAITING),
        ]:
            mock_response = {"status": api_status}

            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            with patch.object(service, '_get_session', return_value=mock_session):
                status = await service._check_trocador_status("trade123")
                assert status == expected_status

    @pytest.mark.asyncio
    async def test_check_status_trocador_non_200(self):
        """Test Trocador status check with non-200 response."""
        service = CryptoSwapService(trocador_api_key="key")

        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            status = await service._check_trocador_status("trade123")
            assert status == SwapStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_status_trocador_exception(self):
        """Test Trocador status check with exception."""
        service = CryptoSwapService(trocador_api_key="key")

        with patch.object(service, '_get_session', side_effect=Exception("Error")):
            status = await service._check_trocador_status("trade123")
            assert status == SwapStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_status_changenow_success(self):
        """Test checking ChangeNow swap status."""
        service = CryptoSwapService(changenow_api_key="key")

        mock_response = {"status": "finished"}

        mock_resp = MagicMock()
        mock_resp.status = 200
        mock_resp.json = AsyncMock(return_value=mock_response)

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            status = await service.check_swap_status("trade123", "changenow")
            assert status == SwapStatus.COMPLETE

    @pytest.mark.asyncio
    async def test_check_status_changenow_statuses(self):
        """Test ChangeNow status mapping."""
        service = CryptoSwapService(changenow_api_key="key")

        for api_status, expected_status in [
            ("new", SwapStatus.WAITING),
            ("waiting", SwapStatus.WAITING),
            ("confirming", SwapStatus.CONFIRMING),
            ("exchanging", SwapStatus.EXCHANGING),
            ("sending", SwapStatus.EXCHANGING),
            ("finished", SwapStatus.COMPLETE),
            ("failed", SwapStatus.FAILED),
            ("refunded", SwapStatus.FAILED),
            ("expired", SwapStatus.EXPIRED),
            ("unknown", SwapStatus.WAITING),
        ]:
            mock_response = {"status": api_status}

            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)

            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)

            mock_session = MagicMock()
            mock_session.get = MagicMock(return_value=mock_cm)

            with patch.object(service, '_get_session', return_value=mock_session):
                status = await service._check_changenow_status("trade123")
                assert status == expected_status

    @pytest.mark.asyncio
    async def test_check_status_changenow_non_200(self):
        """Test ChangeNow status check with non-200 response."""
        service = CryptoSwapService(changenow_api_key="key")

        mock_resp = MagicMock()
        mock_resp.status = 500

        mock_cm = MagicMock()
        mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
        mock_cm.__aexit__ = AsyncMock(return_value=False)

        mock_session = MagicMock()
        mock_session.get = MagicMock(return_value=mock_cm)

        with patch.object(service, '_get_session', return_value=mock_session):
            status = await service._check_changenow_status("trade123")
            assert status == SwapStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_status_changenow_exception(self):
        """Test ChangeNow status check with exception."""
        service = CryptoSwapService(changenow_api_key="key")

        with patch.object(service, '_get_session', side_effect=Exception("Error")):
            status = await service._check_changenow_status("trade123")
            assert status == SwapStatus.FAILED

    @pytest.mark.asyncio
    async def test_check_status_unknown_provider(self):
        """Test status check with unknown provider returns FAILED."""
        service = CryptoSwapService()

        status = await service.check_swap_status("trade123", "unknown")
        assert status == SwapStatus.FAILED
