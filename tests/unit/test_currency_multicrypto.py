"""Tests for multi-cryptocurrency currency conversion."""

import pytest
from decimal import Decimal
from unittest.mock import patch, AsyncMock

from bot.services.currency import (
    fetch_crypto_rates,
    fiat_to_crypto,
    crypto_to_fiat,
    get_currency_symbol,
    format_price,
    CRYPTO_PRECISION
)


@pytest.mark.asyncio
class TestFetchCryptoRates:
    """Test fetching crypto rates."""

    async def test_fetch_crypto_rates_success(self):
        """Test successfully fetching rates for all cryptocurrencies."""
        mock_response = {
            "monero": {"usd": 150.0, "gbp": 118.5, "eur": 138.0},
            "bitcoin": {"usd": 45000.0, "gbp": 35550.0, "eur": 41400.0},
            "ethereum": {"usd": 3000.0, "gbp": 2370.0, "eur": 2760.0}
        }

        with patch('bot.services.currency.aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            rates = await fetch_crypto_rates()

            assert "XMR" in rates
            assert "BTC" in rates
            assert "ETH" in rates
            assert rates["XMR"]["USD"] == Decimal("150.0")
            assert rates["BTC"]["USD"] == Decimal("45000.0")
            assert rates["ETH"]["USD"] == Decimal("3000.0")

    async def test_fetch_crypto_rates_incomplete_data(self):
        """Test error when rates data is incomplete."""
        mock_response = {
            "monero": {"usd": 150.0, "gbp": 118.5, "eur": 138.0}
            # Missing bitcoin and ethereum
        }

        with patch('bot.services.currency.aiohttp.ClientSession') as mock_session:
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.status = 200
            mock_session.return_value.__aenter__.return_value.get.return_value.__aenter__.return_value.json = AsyncMock(return_value=mock_response)

            with pytest.raises(ValueError, match="Incomplete rates data"):
                await fetch_crypto_rates()


@pytest.mark.asyncio
class TestFiatToCrypto:
    """Test fiat to crypto conversion."""

    async def test_fiat_to_btc_conversion(self):
        """Test converting USD to BTC."""
        with patch('bot.services.currency.fetch_crypto_rates', new_callable=AsyncMock) as mock_rates:
            mock_rates.return_value = {
                "BTC": {"USD": Decimal("45000.0")}
            }

            result = await fiat_to_crypto(Decimal("100"), "USD", "BTC")

            assert isinstance(result, Decimal)
            # $100 / $45000 = 0.00222222... BTC
            assert result == Decimal("0.00222222")

    async def test_fiat_to_eth_conversion(self):
        """Test converting EUR to ETH."""
        with patch('bot.services.currency.fetch_crypto_rates', new_callable=AsyncMock) as mock_rates:
            mock_rates.return_value = {
                "ETH": {"EUR": Decimal("2760.0")}
            }

            result = await fiat_to_crypto(Decimal("100"), "EUR", "ETH")

            assert isinstance(result, Decimal)
            # €100 / €2760 = 0.036231... ETH
            expected = Decimal("100") / Decimal("2760.0")
            assert result == expected.quantize(CRYPTO_PRECISION["ETH"])

    async def test_fiat_to_xmr_conversion(self):
        """Test converting GBP to XMR."""
        with patch('bot.services.currency.fetch_crypto_rates', new_callable=AsyncMock) as mock_rates:
            mock_rates.return_value = {
                "XMR": {"GBP": Decimal("118.5")}
            }

            result = await fiat_to_crypto(Decimal("50"), "GBP", "XMR")

            assert isinstance(result, Decimal)
            # £50 / £118.5 = 0.42194092... XMR
            expected = Decimal("50") / Decimal("118.5")
            assert result == expected.quantize(CRYPTO_PRECISION["XMR"])

    async def test_unsupported_fiat_currency(self):
        """Test error with unsupported fiat currency."""
        with pytest.raises(ValueError, match="Unsupported fiat currency: JPY"):
            await fiat_to_crypto(Decimal("100"), "JPY", "BTC")

    async def test_unsupported_crypto_currency(self):
        """Test error with unsupported crypto currency."""
        with pytest.raises(ValueError, match="Unsupported crypto currency: DOGE"):
            await fiat_to_crypto(Decimal("100"), "USD", "DOGE")

    async def test_negative_amount(self):
        """Test error with negative amount."""
        with pytest.raises(ValueError, match="Amount must be positive"):
            await fiat_to_crypto(Decimal("-10"), "USD", "BTC")


@pytest.mark.asyncio
class TestCryptoToFiat:
    """Test crypto to fiat conversion."""

    async def test_btc_to_usd_conversion(self):
        """Test converting BTC to USD."""
        with patch('bot.services.currency.fetch_crypto_rates', new_callable=AsyncMock) as mock_rates:
            mock_rates.return_value = {
                "BTC": {"USD": Decimal("45000.0")}
            }

            result = await crypto_to_fiat(Decimal("0.1"), "BTC", "USD")

            assert isinstance(result, Decimal)
            assert result == Decimal("4500.00")

    async def test_eth_to_eur_conversion(self):
        """Test converting ETH to EUR."""
        with patch('bot.services.currency.fetch_crypto_rates', new_callable=AsyncMock) as mock_rates:
            mock_rates.return_value = {
                "ETH": {"EUR": Decimal("2760.0")}
            }

            result = await crypto_to_fiat(Decimal("1.5"), "ETH", "EUR")

            assert isinstance(result, Decimal)
            assert result == Decimal("4140.00")


class TestCurrencySymbols:
    """Test currency symbol retrieval."""

    def test_get_btc_symbol(self):
        """Test getting BTC symbol."""
        assert get_currency_symbol("BTC") == "BTC"

    def test_get_eth_symbol(self):
        """Test getting ETH symbol."""
        assert get_currency_symbol("ETH") == "ETH"

    def test_get_xmr_symbol(self):
        """Test getting XMR symbol."""
        assert get_currency_symbol("XMR") == "XMR"


class TestFormatPrice:
    """Test price formatting."""

    def test_format_btc_price_small(self):
        """Test formatting small BTC amount."""
        formatted = format_price(Decimal("0.00123456"), "BTC")
        assert "0.00123456 BTC" in formatted

    def test_format_eth_price_small(self):
        """Test formatting small ETH amount."""
        formatted = format_price(Decimal("0.123456"), "ETH")
        assert "0.123456 ETH" in formatted

    def test_format_btc_price_large(self):
        """Test formatting large BTC amount."""
        formatted = format_price(Decimal("1.5"), "BTC")
        assert "1.5" in formatted
        assert "BTC" in formatted

    def test_format_eth_price_large(self):
        """Test formatting large ETH amount."""
        formatted = format_price(Decimal("10.25"), "ETH")
        assert "10.25" in formatted or "10.2500" in formatted
        assert "ETH" in formatted
