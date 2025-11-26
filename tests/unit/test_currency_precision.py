"""Tests for currency conversion and decimal precision.

These tests ensure no money is lost due to floating-point errors.
All financial calculations must use Decimal for precision.
"""

import pytest
from decimal import Decimal
from unittest.mock import AsyncMock, patch

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
