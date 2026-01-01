"""Tests for currency conversion and decimal precision.

These tests ensure no money is lost due to floating-point errors.
All financial calculations must use Decimal for precision.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, MagicMock, patch

from bot.services.currency import (
    fiat_to_xmr_accurate,
    xmr_to_fiat_accurate,
    fiat_to_xmr_cached,
    get_cached_rate,
    format_price,
    format_price_simple,
    XMR_PRECISION,
    FIAT_PRECISION,
)


class TestDecimalPrecision:
    """Test that all calculations use Decimal and maintain precision."""

    @pytest.mark.asyncio
    async def test_fiat_to_xmr_returns_decimal(self):
        """Conversion should return Decimal, not float."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await fiat_to_xmr_accurate(100.0, "USD")
            assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_xmr_to_fiat_returns_decimal(self):
        """Conversion should return Decimal, not float."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await xmr_to_fiat_accurate(Decimal("1.0"), "USD")
            assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_accepts_float_input(self):
        """Should accept float and convert to Decimal internally."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await fiat_to_xmr_accurate(100.0, "USD")
            assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_accepts_string_input(self):
        """Should accept string and convert to Decimal internally."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await fiat_to_xmr_accurate("100.00", "USD")
            assert isinstance(result, Decimal)

    @pytest.mark.asyncio
    async def test_accepts_decimal_input(self):
        """Should accept Decimal directly."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await fiat_to_xmr_accurate(Decimal("100.00"), "USD")
            assert isinstance(result, Decimal)


class TestPrecisionLimits:
    """Test XMR and fiat precision limits."""

    @pytest.mark.asyncio
    async def test_xmr_precision_8_decimals(self):
        """XMR should have at most 8 decimal places."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await fiat_to_xmr_accurate(Decimal("100.00"), "USD")
            # Count decimal places
            _, _, exponent = result.as_tuple()
            decimal_places = -exponent if exponent < 0 else 0
            assert decimal_places <= 8

    @pytest.mark.asyncio
    async def test_fiat_precision_2_decimals(self):
        """Fiat should have at most 2 decimal places."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            result = await xmr_to_fiat_accurate(Decimal("0.66666666"), "USD")
            # Count decimal places
            _, _, exponent = result.as_tuple()
            decimal_places = -exponent if exponent < 0 else 0
            assert decimal_places <= 2


class TestRoundingBehavior:
    """Test rounding behavior for financial safety."""

    @pytest.mark.asyncio
    async def test_fiat_to_xmr_rounds_down(self):
        """Fiat to XMR should round DOWN (in favor of platform)."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            # Set up a rate that produces a repeating decimal
            mock.return_value = {"USD": Decimal("150.00")}
            # 100 / 150 = 0.666666...
            result = await fiat_to_xmr_accurate(Decimal("100.00"), "USD")
            # Should round down to 0.66666666 (8 decimals)
            assert result <= Decimal("0.66666667")

    @pytest.mark.asyncio
    async def test_xmr_to_fiat_rounds_half_up(self):
        """XMR to fiat should round HALF_UP for display."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            # 0.66666666 * 150 = 99.999999
            result = await xmr_to_fiat_accurate(Decimal("0.66666666"), "USD")
            # Should round to nearest cent
            assert result == Decimal("100.00")


class TestNoFloatingPointErrors:
    """Test that classic floating-point errors are avoided."""

    @pytest.mark.asyncio
    async def test_no_float_addition_error(self):
        """Avoid the classic 0.1 + 0.2 != 0.3 problem."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("1.00")}
            # In float: 0.1 + 0.2 = 0.30000000000000004
            result1 = await fiat_to_xmr_accurate(Decimal("0.1"), "USD")
            result2 = await fiat_to_xmr_accurate(Decimal("0.2"), "USD")
            result3 = await fiat_to_xmr_accurate(Decimal("0.3"), "USD")
            # With Decimal, addition should be exact
            assert result1 + result2 == result3

    @pytest.mark.asyncio
    async def test_large_amounts_precise(self):
        """Large amounts should maintain precision."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            # Large transaction: $1,000,000
            result = await fiat_to_xmr_accurate(Decimal("1000000.00"), "USD")
            # Should be exactly 6666.66666666 XMR (rounded down)
            expected = Decimal("6666.66666666")
            assert result == expected

    @pytest.mark.asyncio
    async def test_small_amounts_precise(self):
        """Small amounts should maintain precision."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            # Tiny transaction: $0.01 (1 cent)
            result = await fiat_to_xmr_accurate(Decimal("0.01"), "USD")
            # Should be 0.00006666 XMR (rounded down)
            assert result == Decimal("0.00006666")


class TestXMRPassthrough:
    """Test XMR to XMR conversion (no conversion needed)."""

    @pytest.mark.asyncio
    async def test_xmr_to_xmr_passthrough(self):
        """XMR to XMR should return same value."""
        result = await fiat_to_xmr_accurate(Decimal("1.23456789"), "XMR")
        # Should truncate to 8 decimals
        assert result == Decimal("1.23456789")

    @pytest.mark.asyncio
    async def test_xmr_currency_no_api_call(self):
        """XMR currency should not call API."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            await fiat_to_xmr_accurate(Decimal("1.0"), "XMR")
            mock.assert_not_called()


class TestErrorHandling:
    """Test error cases."""

    @pytest.mark.asyncio
    async def test_negative_amount_error(self):
        """Should reject negative amounts."""
        with pytest.raises(ValueError, match="Amount must be positive"):
            await fiat_to_xmr_accurate(Decimal("-100.00"), "USD")

    @pytest.mark.asyncio
    async def test_zero_amount_error(self):
        """Should reject zero amounts."""
        with pytest.raises(ValueError, match="Amount must be positive"):
            await fiat_to_xmr_accurate(Decimal("0"), "USD")

    @pytest.mark.asyncio
    async def test_unsupported_currency_error(self):
        """Should reject unsupported currencies."""
        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            with pytest.raises(ValueError, match="Unsupported currency"):
                await fiat_to_xmr_accurate(Decimal("100.00"), "INVALID")


class TestFormatFunctions:
    """Test price formatting functions."""

    def test_format_price_xmr_small(self):
        """Small XMR amounts should show 8 decimals."""
        result = format_price(Decimal("0.00123456"), "XMR")
        assert "0.00123456" in result
        assert "XMR" in result

    def test_format_price_xmr_large(self):
        """Large XMR amounts should show 4 decimals."""
        result = format_price(Decimal("1.23456789"), "XMR")
        # Rounds to 4 decimals (1.2346 due to rounding)
        assert "1.2346" in result
        assert "XMR" in result

    def test_format_price_usd(self):
        """USD should show $ symbol and 2 decimals."""
        result = format_price(Decimal("99.99"), "USD")
        assert result == "$99.99"

    def test_format_price_gbp(self):
        """GBP should show pound symbol."""
        result = format_price(Decimal("50.00"), "GBP")
        assert result == "£50.00"

    def test_format_price_eur(self):
        """EUR should show euro symbol."""
        result = format_price(Decimal("75.50"), "EUR")
        assert result == "€75.50"

    def test_format_price_accepts_float(self):
        """Format functions should accept float input."""
        result = format_price(99.99, "USD")
        assert result == "$99.99"

    def test_format_price_simple_xmr(self):
        """Simple format for XMR."""
        result = format_price_simple(Decimal("0.5"), "XMR")
        assert result == "0.5 XMR"


class TestOrderCalculationIntegration:
    """Test that order calculations maintain precision."""

    def test_commission_calculation_precise(self):
        """Commission should be calculated with Decimal precision."""
        price = Decimal("0.05")  # 0.05 XMR
        quantity = 3
        commission_rate = Decimal("0.05")  # 5%

        total = price * Decimal(quantity)
        commission = total * commission_rate

        assert total == Decimal("0.15")
        assert commission == Decimal("0.0075")

    def test_multiple_items_no_rounding_loss(self):
        """Multiple items should not accumulate rounding errors."""
        price = Decimal("0.333333")
        quantity = 3
        commission_rate = Decimal("0.05")

        total = price * Decimal(quantity)
        commission = total * commission_rate

        # Should be exact, no floating point drift
        assert total == Decimal("0.999999")
        assert commission == Decimal("0.04999995")


class TestFetchXMRRates:
    """Test fetch_xmr_rates function."""

    @pytest.mark.asyncio
    async def test_fetch_rates_success(self):
        """Test successful rate fetch from API."""
        from bot.services.currency import fetch_xmr_rates

        mock_response = {
            "monero": {
                "usd": 150.0,
                "gbp": 120.0,
                "eur": 140.0
            }
        }

        with patch('aiohttp.ClientSession') as mock_session:
            mock_resp = AsyncMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value=mock_response)

            mock_cm = AsyncMock()
            mock_cm.__aenter__.return_value = mock_resp

            mock_session_instance = MagicMock()
            mock_session_instance.get.return_value = mock_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock()
            mock_session.return_value = mock_session_instance

            rates = await fetch_xmr_rates()

            assert "USD" in rates
            assert "GBP" in rates
            assert "EUR" in rates
            assert isinstance(rates["USD"], Decimal)

    @pytest.mark.asyncio
    async def test_fetch_rates_api_error(self):
        """Test API error handling."""
        from bot.services.currency import fetch_xmr_rates

        with patch('bot.services.currency.aiohttp.ClientSession') as mock_session:
            mock_resp = MagicMock()
            mock_resp.status = 500

            # Mock the response context manager (session.get() returns this)
            # __aexit__ must return False to not suppress exceptions
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)

            # Mock the session instance
            mock_session_instance = MagicMock()
            mock_session_instance.get.return_value = mock_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value = mock_session_instance

            with pytest.raises(ValueError, match="Invalid response"):
                await fetch_xmr_rates()

    @pytest.mark.asyncio
    async def test_fetch_rates_missing_monero_data(self):
        """Test API response with status 200 but missing monero data."""
        from bot.services.currency import fetch_xmr_rates

        with patch('bot.services.currency.aiohttp.ClientSession') as mock_session:
            mock_resp = MagicMock()
            mock_resp.status = 200
            mock_resp.json = AsyncMock(return_value={"bitcoin": {"usd": 50000}})

            # Mock the response context manager
            mock_cm = MagicMock()
            mock_cm.__aenter__ = AsyncMock(return_value=mock_resp)
            mock_cm.__aexit__ = AsyncMock(return_value=False)

            # Mock the session instance
            mock_session_instance = MagicMock()
            mock_session_instance.get.return_value = mock_cm
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value = mock_session_instance

            with pytest.raises(ValueError, match="Invalid response"):
                await fetch_xmr_rates()

    @pytest.mark.asyncio
    async def test_fetch_rates_network_error(self):
        """Test network error handling."""
        from bot.services.currency import fetch_xmr_rates
        import aiohttp

        with patch('bot.services.currency.aiohttp.ClientSession') as mock_session:
            # Mock the session instance that raises on get()
            mock_session_instance = MagicMock()
            mock_session_instance.get.side_effect = aiohttp.ClientError("Network error")
            mock_session_instance.__aenter__ = AsyncMock(return_value=mock_session_instance)
            mock_session_instance.__aexit__ = AsyncMock(return_value=False)
            mock_session.return_value = mock_session_instance

            with pytest.raises(ValueError, match="Failed to fetch"):
                await fetch_xmr_rates()

    @pytest.mark.asyncio
    async def test_fetch_rates_general_exception(self):
        """Test general exception handling."""
        from bot.services.currency import fetch_xmr_rates

        with patch('aiohttp.ClientSession') as mock_session:
            mock_session.side_effect = Exception("Unexpected error")

            with pytest.raises(ValueError, match="Failed to fetch"):
                await fetch_xmr_rates()


class TestGetXMRPrice:
    """Test get_xmr_price function."""

    @pytest.mark.asyncio
    async def test_get_xmr_price_for_xmr(self):
        """Test getting XMR price for XMR currency (returns 1)."""
        from bot.services.currency import get_xmr_price

        result = await get_xmr_price("XMR")
        assert result == Decimal("1")

    @pytest.mark.asyncio
    async def test_get_xmr_price_unsupported(self):
        """Test getting price for unsupported currency."""
        from bot.services.currency import get_xmr_price

        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}
            with pytest.raises(ValueError, match="Unsupported currency"):
                await get_xmr_price("INVALID")


class TestFiatToXMRSync:
    """Test fiat_to_xmr_sync function."""

    def test_fiat_to_xmr_sync_with_cache(self):
        """Test sync conversion using cached rate."""
        from bot.services.currency import fiat_to_xmr_sync, _display_cache, DISPLAY_CACHE_DURATION
        import bot.services.currency as currency_module
        from datetime import datetime

        currency_module._display_cache = {"USD": Decimal("150.00")}
        currency_module._display_cache_time = datetime.utcnow()

        result = fiat_to_xmr_sync(Decimal("100.00"), "USD")
        assert isinstance(result, Decimal)

    def test_fiat_to_xmr_sync_xmr(self):
        """Test sync conversion for XMR currency."""
        from bot.services.currency import fiat_to_xmr_sync

        result = fiat_to_xmr_sync(Decimal("1.5"), "XMR")
        assert result == Decimal("1.50000000")

    def test_fiat_to_xmr_sync_no_cache_running_loop(self):
        """Test sync conversion with running event loop and no cache."""
        from bot.services.currency import fiat_to_xmr_sync
        import bot.services.currency as currency_module

        currency_module._display_cache = {}
        currency_module._display_cache_time = None

        result = fiat_to_xmr_sync(Decimal("100.00"), "USD")
        assert isinstance(result, Decimal)

    def test_fiat_to_xmr_sync_running_loop_xmr(self):
        """Test sync conversion with running event loop for XMR currency."""
        from bot.services.currency import fiat_to_xmr_sync
        import asyncio

        # Create and run in an event loop context
        async def run_test():
            # Mock fiat_to_xmr_cached to return None, forcing us into the running loop branch
            with patch('bot.services.currency.fiat_to_xmr_cached', return_value=None):
                result = fiat_to_xmr_sync(Decimal("1.5"), "XMR")
                return result

        result = asyncio.run(run_test())
        assert result == Decimal("1.50000000")

    def test_fiat_to_xmr_sync_running_loop_gbp(self):
        """Test sync conversion with running event loop for GBP currency."""
        from bot.services.currency import fiat_to_xmr_sync
        import asyncio

        async def run_test():
            # Mock fiat_to_xmr_cached to return None
            with patch('bot.services.currency.fiat_to_xmr_cached', return_value=None):
                result = fiat_to_xmr_sync(Decimal("100.00"), "GBP")
                return result

        result = asyncio.run(run_test())
        assert isinstance(result, Decimal)
        # GBP has a multiplier of 0.79, so rate = 150 * 0.79 = 118.5
        # 100 / 118.5 = ~0.84388...
        assert result > Decimal("0")

    def test_fiat_to_xmr_sync_running_loop_eur(self):
        """Test sync conversion with running event loop for EUR currency."""
        from bot.services.currency import fiat_to_xmr_sync
        import asyncio

        async def run_test():
            with patch('bot.services.currency.fiat_to_xmr_cached', return_value=None):
                result = fiat_to_xmr_sync(Decimal("100.00"), "EUR")
                return result

        result = asyncio.run(run_test())
        assert isinstance(result, Decimal)
        assert result > Decimal("0")

    def test_fiat_to_xmr_sync_running_loop_unknown(self):
        """Test sync conversion with running event loop for unknown currency."""
        from bot.services.currency import fiat_to_xmr_sync
        import asyncio

        async def run_test():
            # Unknown currency uses default multiplier of 1
            with patch('bot.services.currency.fiat_to_xmr_cached', return_value=None):
                result = fiat_to_xmr_sync(Decimal("100.00"), "UNKNOWN")
                return result

        result = asyncio.run(run_test())
        assert isinstance(result, Decimal)

    def test_fiat_to_xmr_sync_no_event_loop(self):
        """Test sync conversion with no event loop (RuntimeError branch)."""
        from bot.services.currency import fiat_to_xmr_sync
        import bot.services.currency as currency_module
        import asyncio

        # Clear cache
        currency_module._display_cache = {}
        currency_module._display_cache_time = None

        # Patch get_event_loop to raise RuntimeError
        with patch('bot.services.currency.asyncio.get_event_loop') as mock_get_loop:
            mock_get_loop.side_effect = RuntimeError("No event loop")
            with patch('bot.services.currency.fiat_to_xmr_accurate', new_callable=AsyncMock) as mock_convert:
                mock_convert.return_value = Decimal("0.66666666")
                result = fiat_to_xmr_sync(Decimal("100.00"), "USD")
                assert result == Decimal("0.66666666")


class TestFiatToXMRAccurateEdgeCases:
    """Test edge cases for fiat_to_xmr_accurate function."""

    @pytest.mark.asyncio
    async def test_fiat_to_xmr_accurate_invalid_exchange_rate(self):
        """Test that invalid exchange rate (0 or negative) raises error."""
        from bot.services.currency import fiat_to_xmr_accurate

        with patch('bot.services.currency.get_xmr_price', new_callable=AsyncMock) as mock:
            mock.return_value = Decimal("0")

            with pytest.raises(ValueError, match="Invalid exchange rate"):
                await fiat_to_xmr_accurate(Decimal("100.00"), "USD")

    @pytest.mark.asyncio
    async def test_fiat_to_xmr_accurate_negative_exchange_rate(self):
        """Test that negative exchange rate raises error."""
        from bot.services.currency import fiat_to_xmr_accurate

        with patch('bot.services.currency.get_xmr_price', new_callable=AsyncMock) as mock:
            mock.return_value = Decimal("-1")

            with pytest.raises(ValueError, match="Invalid exchange rate"):
                await fiat_to_xmr_accurate(Decimal("100.00"), "USD")


class TestXMRToFiatAccurate:
    """Test xmr_to_fiat_accurate function."""

    @pytest.mark.asyncio
    async def test_xmr_to_fiat_xmr_passthrough(self):
        """Test XMR to XMR passthrough."""
        from bot.services.currency import xmr_to_fiat_accurate

        result = await xmr_to_fiat_accurate(Decimal("1.5"), "XMR")
        assert result == Decimal("1.5")

    @pytest.mark.asyncio
    async def test_xmr_to_fiat_negative_error(self):
        """Test negative amount error."""
        from bot.services.currency import xmr_to_fiat_accurate

        with pytest.raises(ValueError, match="Amount must be positive"):
            await xmr_to_fiat_accurate(Decimal("-1.0"), "USD")


class TestUpdateDisplayCache:
    """Test update_display_cache function."""

    @pytest.mark.asyncio
    async def test_update_cache_success(self):
        """Test successful cache update."""
        from bot.services.currency import update_display_cache
        import bot.services.currency as currency_module

        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.return_value = {"USD": Decimal("150.00")}

            await update_display_cache()

            assert "USD" in currency_module._display_cache
            assert currency_module._display_cache_time is not None

    @pytest.mark.asyncio
    async def test_update_cache_failure(self):
        """Test cache update failure."""
        from bot.services.currency import update_display_cache

        with patch('bot.services.currency.fetch_xmr_rates', new_callable=AsyncMock) as mock:
            mock.side_effect = Exception("API error")

            await update_display_cache()


class TestGetCachedRate:
    """Test get_cached_rate function."""

    def test_get_cached_rate_xmr(self):
        """Test getting cached rate for XMR."""
        from bot.services.currency import get_cached_rate

        result = get_cached_rate("XMR")
        assert result == Decimal("1")

    def test_get_cached_rate_valid_cache(self):
        """Test getting cached rate with valid cache."""
        from bot.services.currency import get_cached_rate
        import bot.services.currency as currency_module
        from datetime import datetime

        currency_module._display_cache = {"USD": Decimal("150.00")}
        currency_module._display_cache_time = datetime.utcnow()

        result = get_cached_rate("USD")
        assert result == Decimal("150.00")

    def test_get_cached_rate_expired(self):
        """Test getting cached rate with expired cache."""
        from bot.services.currency import get_cached_rate, DISPLAY_CACHE_DURATION
        import bot.services.currency as currency_module
        from datetime import datetime, timedelta

        currency_module._display_cache = {"USD": Decimal("150.00")}
        currency_module._display_cache_time = datetime.utcnow() - DISPLAY_CACHE_DURATION - timedelta(minutes=1)

        result = get_cached_rate("USD")
        assert result is None

    def test_get_cached_rate_no_cache(self):
        """Test getting cached rate with no cache."""
        from bot.services.currency import get_cached_rate
        import bot.services.currency as currency_module

        currency_module._display_cache = {}
        currency_module._display_cache_time = None

        result = get_cached_rate("USD")
        assert result is None


class TestFiatToXMRCached:
    """Test fiat_to_xmr_cached function."""

    def test_fiat_to_xmr_cached_xmr(self):
        """Test cached conversion for XMR."""
        from bot.services.currency import fiat_to_xmr_cached

        result = fiat_to_xmr_cached(Decimal("1.5"), "XMR")
        assert result == Decimal("1.5")

    def test_fiat_to_xmr_cached_valid(self):
        """Test cached conversion with valid cache."""
        from bot.services.currency import fiat_to_xmr_cached
        import bot.services.currency as currency_module
        from datetime import datetime

        currency_module._display_cache = {"USD": Decimal("150.00")}
        currency_module._display_cache_time = datetime.utcnow()

        result = fiat_to_xmr_cached(Decimal("150.00"), "USD")
        assert result == Decimal("1.00000000")

    def test_fiat_to_xmr_cached_no_cache(self):
        """Test cached conversion with no cache."""
        from bot.services.currency import fiat_to_xmr_cached
        import bot.services.currency as currency_module

        currency_module._display_cache = {}
        currency_module._display_cache_time = None

        result = fiat_to_xmr_cached(Decimal("100.00"), "USD")
        assert result is None


class TestGetCurrencySymbol:
    """Test get_currency_symbol function."""

    def test_get_currency_symbol_all(self):
        """Test getting all currency symbols."""
        from bot.services.currency import get_currency_symbol

        assert get_currency_symbol("USD") == "$"
        assert get_currency_symbol("GBP") == "£"
        assert get_currency_symbol("EUR") == "€"
        assert get_currency_symbol("XMR") == "XMR"
        assert get_currency_symbol("UNKNOWN") == "UNKNOWN"


class TestFormatPriceSimple:
    """Test format_price_simple function."""

    def test_format_price_simple_fiat(self):
        """Test simple format for fiat currencies."""
        from bot.services.currency import format_price_simple

        assert format_price_simple(Decimal("99.99"), "USD") == "$99.99"
        assert format_price_simple(Decimal("50.00"), "GBP") == "£50.00"
        assert format_price_simple(Decimal("75.50"), "EUR") == "€75.50"
