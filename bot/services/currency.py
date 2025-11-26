"""Currency conversion service for fiat to crypto.

Uses CoinGecko API for accurate real-time exchange rates.
Critical: All order conversions use fresh rates, not cached.
Uses Decimal for precision - never use float for money.
"""

from __future__ import annotations

import aiohttp
import logging
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Precision constants
XMR_PRECISION = Decimal("0.00000001")  # 8 decimal places
FIAT_PRECISION = Decimal("0.01")  # 2 decimal places

# Cache for display purposes only (not for order conversion)
_display_cache: dict = {}
_display_cache_time: Optional[datetime] = None
DISPLAY_CACHE_DURATION = timedelta(minutes=5)


async def fetch_xmr_rates() -> dict[str, Decimal]:
    """Fetch current XMR exchange rates from CoinGecko.

    Returns dict with rates: {"USD": Decimal("150.0"), ...}
    Raises ValueError if rates cannot be fetched.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "monero",
                "vs_currencies": "usd,gbp,eur",
                "precision": 8
            }
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()
                    if "monero" in data:
                        # Use Decimal for precise rate storage
                        return {
                            "USD": Decimal(str(data["monero"]["usd"])),
                            "GBP": Decimal(str(data["monero"]["gbp"])),
                            "EUR": Decimal(str(data["monero"]["eur"])),
                        }
                raise ValueError(f"Invalid response from CoinGecko: {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching XMR rates: {e}")
        raise ValueError(f"Failed to fetch exchange rates: {e}")
    except Exception as e:
        logger.error(f"Error fetching XMR rates: {e}")
        raise ValueError(f"Failed to fetch exchange rates: {e}")


async def get_xmr_price(currency: str) -> Decimal:
    """Get current XMR price in specified fiat currency.

    CRITICAL: This fetches fresh rates - use for order conversion.
    Raises ValueError if rate cannot be fetched.
    """
    if currency == "XMR":
        return Decimal("1")

    rates = await fetch_xmr_rates()
    if currency not in rates:
        raise ValueError(f"Unsupported currency: {currency}")

    return rates[currency]


async def fiat_to_xmr_accurate(amount: Union[float, Decimal, str], currency: str) -> Decimal:
    """Convert fiat amount to XMR with fresh exchange rate.

    CRITICAL: Use this for order creation - fetches live rates.
    Uses Decimal for precision - no floating point errors.
    Raises ValueError if conversion fails.
    """
    # Convert input to Decimal for precision
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount

    if currency == "XMR":
        return amount_decimal.quantize(XMR_PRECISION, rounding=ROUND_DOWN)

    if amount_decimal <= 0:
        raise ValueError("Amount must be positive")

    xmr_price = await get_xmr_price(currency)
    if xmr_price <= 0:
        raise ValueError("Invalid exchange rate")

    xmr_amount = amount_decimal / xmr_price
    # Round down to 8 decimal places (XMR precision) - always round in favor of platform
    return xmr_amount.quantize(XMR_PRECISION, rounding=ROUND_DOWN)


async def xmr_to_fiat_accurate(amount: Union[float, Decimal, str], currency: str) -> Decimal:
    """Convert XMR amount to fiat with fresh exchange rate.

    CRITICAL: Use this for display - fetches live rates.
    Uses Decimal for precision.
    Raises ValueError if conversion fails.
    """
    # Convert input to Decimal for precision
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount

    if currency == "XMR":
        return amount_decimal

    if amount_decimal <= 0:
        raise ValueError("Amount must be positive")

    xmr_price = await get_xmr_price(currency)
    fiat_amount = amount_decimal * xmr_price
    # Round to 2 decimal places for fiat
    return fiat_amount.quantize(FIAT_PRECISION, rounding=ROUND_HALF_UP)


async def update_display_cache() -> None:
    """Update the display cache with fresh rates."""
    global _display_cache, _display_cache_time
    try:
        rates = await fetch_xmr_rates()
        _display_cache = rates
        _display_cache_time = datetime.utcnow()
        logger.info(f"Updated exchange rate cache: {rates}")
    except Exception as e:
        logger.warning(f"Failed to update display cache: {e}")


def get_cached_rate(currency: str) -> Optional[Decimal]:
    """Get cached rate for display purposes only.

    WARNING: Do NOT use for order conversion - use fiat_to_xmr_accurate instead.
    Returns None if no cache available.
    """
    if currency == "XMR":
        return Decimal("1")

    # Check if cache is still valid
    if _display_cache_time:
        age = datetime.utcnow() - _display_cache_time
        if age < DISPLAY_CACHE_DURATION and currency in _display_cache:
            return _display_cache[currency]

    return None


def fiat_to_xmr_cached(amount: Union[float, Decimal, str], currency: str) -> Optional[Decimal]:
    """Convert fiat to XMR using cached rate (for display only).

    WARNING: Do NOT use for order conversion - use fiat_to_xmr_accurate instead.
    Returns None if no cache available.
    """
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount

    if currency == "XMR":
        return amount_decimal

    rate = get_cached_rate(currency)
    if rate is None:
        return None

    return (amount_decimal / rate).quantize(XMR_PRECISION, rounding=ROUND_DOWN)


def get_currency_symbol(currency: str) -> str:
    """Get currency symbol."""
    symbols = {
        "USD": "$",
        "GBP": "£",
        "EUR": "€",
        "XMR": "XMR",
    }
    return symbols.get(currency, currency)


def format_price(amount: Union[float, Decimal, str], currency: str) -> str:
    """Format price with currency symbol."""
    # Convert to Decimal for consistent formatting
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    symbol = get_currency_symbol(currency)
    if currency == "XMR":
        if amount_decimal < 1:
            return f"{amount_decimal:.8f} XMR"
        return f"{amount_decimal:.4f} XMR"
    return f"{symbol}{amount_decimal:.2f}"


def format_price_simple(amount: Union[float, Decimal, str], currency: str) -> str:
    """Format price simply for display."""
    # Convert to Decimal for consistent formatting
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    symbol = get_currency_symbol(currency)
    if currency == "XMR":
        return f"{amount_decimal} XMR"
    return f"{symbol}{amount_decimal:.2f}"
