"""Currency conversion service for fiat to crypto.

Uses CoinGecko API for accurate real-time exchange rates.
Critical: All order conversions use fresh rates, not cached.
"""

from __future__ import annotations

import aiohttp
import logging
from datetime import datetime, timedelta
from typing import Optional

logger = logging.getLogger(__name__)

# Cache for display purposes only (not for order conversion)
_display_cache: dict = {}
_display_cache_time: Optional[datetime] = None
DISPLAY_CACHE_DURATION = timedelta(minutes=5)


async def fetch_xmr_rates() -> dict:
    """Fetch current XMR exchange rates from CoinGecko.

    Returns dict with rates: {"USD": 150.0, "GBP": 120.0, "EUR": 140.0}
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
                        return {
                            "USD": float(data["monero"]["usd"]),
                            "GBP": float(data["monero"]["gbp"]),
                            "EUR": float(data["monero"]["eur"]),
                        }
                raise ValueError(f"Invalid response from CoinGecko: {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching XMR rates: {e}")
        raise ValueError(f"Failed to fetch exchange rates: {e}")
    except Exception as e:
        logger.error(f"Error fetching XMR rates: {e}")
        raise ValueError(f"Failed to fetch exchange rates: {e}")


async def get_xmr_price(currency: str) -> float:
    """Get current XMR price in specified fiat currency.

    CRITICAL: This fetches fresh rates - use for order conversion.
    Raises ValueError if rate cannot be fetched.
    """
    if currency == "XMR":
        return 1.0

    rates = await fetch_xmr_rates()
    if currency not in rates:
        raise ValueError(f"Unsupported currency: {currency}")

    return rates[currency]


async def fiat_to_xmr_accurate(amount: float, currency: str) -> float:
    """Convert fiat amount to XMR with fresh exchange rate.

    CRITICAL: Use this for order creation - fetches live rates.
    Raises ValueError if conversion fails.
    """
    if currency == "XMR":
        return amount

    if amount <= 0:
        raise ValueError("Amount must be positive")

    xmr_price = await get_xmr_price(currency)
    if xmr_price <= 0:
        raise ValueError("Invalid exchange rate")

    xmr_amount = amount / xmr_price
    # Round to 8 decimal places (XMR precision)
    return round(xmr_amount, 8)


async def xmr_to_fiat_accurate(amount: float, currency: str) -> float:
    """Convert XMR amount to fiat with fresh exchange rate.

    CRITICAL: Use this for display - fetches live rates.
    Raises ValueError if conversion fails.
    """
    if currency == "XMR":
        return amount

    if amount <= 0:
        raise ValueError("Amount must be positive")

    xmr_price = await get_xmr_price(currency)
    fiat_amount = amount * xmr_price
    # Round to 2 decimal places for fiat
    return round(fiat_amount, 2)


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


def get_cached_rate(currency: str) -> Optional[float]:
    """Get cached rate for display purposes only.

    WARNING: Do NOT use for order conversion - use fiat_to_xmr_accurate instead.
    Returns None if no cache available.
    """
    if currency == "XMR":
        return 1.0

    # Check if cache is still valid
    if _display_cache_time:
        age = datetime.utcnow() - _display_cache_time
        if age < DISPLAY_CACHE_DURATION and currency in _display_cache:
            return _display_cache[currency]

    return None


def fiat_to_xmr_cached(amount: float, currency: str) -> Optional[float]:
    """Convert fiat to XMR using cached rate (for display only).

    WARNING: Do NOT use for order conversion - use fiat_to_xmr_accurate instead.
    Returns None if no cache available.
    """
    if currency == "XMR":
        return amount

    rate = get_cached_rate(currency)
    if rate is None:
        return None

    return round(amount / rate, 8)


def get_currency_symbol(currency: str) -> str:
    """Get currency symbol."""
    symbols = {
        "USD": "$",
        "GBP": "£",
        "EUR": "€",
        "XMR": "XMR",
    }
    return symbols.get(currency, currency)


def format_price(amount: float, currency: str) -> str:
    """Format price with currency symbol."""
    symbol = get_currency_symbol(currency)
    if currency == "XMR":
        return f"{amount:.8f} XMR" if amount < 1 else f"{amount:.4f} XMR"
    return f"{symbol}{amount:.2f}"


def format_price_simple(amount: float, currency: str) -> str:
    """Format price simply for display."""
    symbol = get_currency_symbol(currency)
    if currency == "XMR":
        return f"{amount} XMR"
    return f"{symbol}{amount:.2f}"
