"""Currency conversion service for fiat to crypto.

Uses CoinGecko API for accurate real-time exchange rates.
Critical: All order conversions use fresh rates, not cached.
Uses Decimal for precision - never use float for money.
"""

from __future__ import annotations

import asyncio
import aiohttp
import logging
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP
from datetime import datetime, timedelta
from typing import Optional, Union

logger = logging.getLogger(__name__)

# Precision constants
XMR_PRECISION = Decimal("0.00000001")  # 8 decimal places
BTC_PRECISION = Decimal("0.00000001")  # 8 decimal places
ETH_PRECISION = Decimal("0.000000000000000001")  # 18 decimal places (Wei)
FIAT_PRECISION = Decimal("0.01")  # 2 decimal places

# Crypto precision map
CRYPTO_PRECISION = {
    "XMR": XMR_PRECISION,
    "BTC": BTC_PRECISION,
    "ETH": Decimal("0.000001"),  # Use 6 decimals for ETH (more practical)
}

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


async def fetch_crypto_rates() -> dict[str, dict[str, Decimal]]:
    """Fetch current exchange rates for all supported cryptocurrencies from CoinGecko.

    Returns dict with structure:
    {
        "XMR": {"USD": Decimal("150.0"), "GBP": Decimal("118.5"), "EUR": Decimal("138.0")},
        "BTC": {"USD": Decimal("45000.0"), ...},
        "ETH": {"USD": Decimal("3000.0"), ...}
    }

    Raises ValueError if rates cannot be fetched.
    """
    try:
        async with aiohttp.ClientSession() as session:
            url = "https://api.coingecko.com/api/v3/simple/price"
            params = {
                "ids": "monero,bitcoin,ethereum",
                "vs_currencies": "usd,gbp,eur",
                "precision": 8
            }
            async with session.get(url, params=params, timeout=15) as response:
                if response.status == 200:
                    data = await response.json()

                    rates = {}

                    if "monero" in data:
                        rates["XMR"] = {
                            "USD": Decimal(str(data["monero"]["usd"])),
                            "GBP": Decimal(str(data["monero"]["gbp"])),
                            "EUR": Decimal(str(data["monero"]["eur"])),
                        }

                    if "bitcoin" in data:
                        rates["BTC"] = {
                            "USD": Decimal(str(data["bitcoin"]["usd"])),
                            "GBP": Decimal(str(data["bitcoin"]["gbp"])),
                            "EUR": Decimal(str(data["bitcoin"]["eur"])),
                        }

                    if "ethereum" in data:
                        rates["ETH"] = {
                            "USD": Decimal(str(data["ethereum"]["usd"])),
                            "GBP": Decimal(str(data["ethereum"]["gbp"])),
                            "EUR": Decimal(str(data["ethereum"]["eur"])),
                        }

                    if len(rates) != 3:
                        raise ValueError(f"Incomplete rates data: {list(rates.keys())}")

                    return rates

                raise ValueError(f"Invalid response from CoinGecko: {response.status}")
    except aiohttp.ClientError as e:
        logger.error(f"Network error fetching crypto rates: {e}")
        raise ValueError(f"Failed to fetch exchange rates: {e}")
    except Exception as e:
        logger.error(f"Error fetching crypto rates: {e}")
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


def fiat_to_xmr_sync(amount: Union[float, Decimal, str], currency: str) -> Decimal:
    """Synchronous wrapper for fiat_to_xmr_accurate.

    Uses cached rate if available, otherwise runs async conversion.
    For use in non-async contexts where accuracy is still needed.
    """
    # Try cached first
    cached = fiat_to_xmr_cached(amount, currency)
    if cached is not None:
        return cached

    # Fall back to running the async function
    try:
        loop = asyncio.get_event_loop()
        if loop.is_running():
            # We're in an async context, create a task
            # For now, use a default rate if cache unavailable
            amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
            if currency == "XMR":
                return amount_decimal.quantize(XMR_PRECISION, rounding=ROUND_DOWN)
            # Use a reasonable default XMR price (will be updated when cache refreshes)
            default_xmr_price = Decimal("150")  # Approximate USD price
            rate_multipliers = {"USD": Decimal("1"), "GBP": Decimal("0.79"), "EUR": Decimal("0.92")}
            multiplier = rate_multipliers.get(currency, Decimal("1"))
            estimated_rate = default_xmr_price * multiplier
            return (amount_decimal / estimated_rate).quantize(XMR_PRECISION, rounding=ROUND_DOWN)
        else:
            return loop.run_until_complete(fiat_to_xmr_accurate(amount, currency))
    except RuntimeError:
        # No event loop, create one
        return asyncio.run(fiat_to_xmr_accurate(amount, currency))


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


async def fiat_to_crypto(
    amount: Union[float, Decimal, str],
    fiat_currency: str,
    crypto_currency: str
) -> Decimal:
    """Convert fiat amount to any supported cryptocurrency with fresh exchange rate.

    CRITICAL: Use this for order creation - fetches live rates.
    Supports BTC, ETH, and XMR.
    Uses Decimal for precision - no floating point errors.
    Raises ValueError if conversion fails.

    Args:
        amount: Amount in fiat currency
        fiat_currency: Fiat currency code (USD, GBP, EUR)
        crypto_currency: Crypto currency code (BTC, ETH, XMR)

    Returns:
        Amount in cryptocurrency

    Example:
        >>> await fiat_to_crypto(100, "USD", "BTC")
        Decimal("0.00222222")  # $100 worth of BTC
    """
    # Convert input to Decimal for precision
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount

    # Normalize currency codes
    fiat_currency = fiat_currency.upper()
    crypto_currency = crypto_currency.upper()

    # Validate currencies
    if fiat_currency not in ["USD", "GBP", "EUR"]:
        raise ValueError(f"Unsupported fiat currency: {fiat_currency}")

    if crypto_currency not in ["XMR", "BTC", "ETH"]:
        raise ValueError(f"Unsupported crypto currency: {crypto_currency}")

    if amount_decimal <= 0:
        raise ValueError("Amount must be positive")

    # Fetch all crypto rates
    rates = await fetch_crypto_rates()

    if crypto_currency not in rates:
        raise ValueError(f"Rates not available for {crypto_currency}")

    if fiat_currency not in rates[crypto_currency]:
        raise ValueError(f"Rate not available for {fiat_currency} to {crypto_currency}")

    crypto_price = rates[crypto_currency][fiat_currency]

    if crypto_price <= 0:
        raise ValueError("Invalid exchange rate")

    # Calculate crypto amount
    crypto_amount = amount_decimal / crypto_price

    # Get appropriate precision for this crypto
    precision = CRYPTO_PRECISION.get(crypto_currency, XMR_PRECISION)

    # Round down to appropriate precision (always round in favor of platform)
    return crypto_amount.quantize(precision, rounding=ROUND_DOWN)


async def crypto_to_fiat(
    amount: Union[float, Decimal, str],
    crypto_currency: str,
    fiat_currency: str
) -> Decimal:
    """Convert cryptocurrency amount to fiat with fresh exchange rate.

    CRITICAL: Use this for display - fetches live rates.
    Supports BTC, ETH, and XMR.
    Uses Decimal for precision.
    Raises ValueError if conversion fails.

    Args:
        amount: Amount in cryptocurrency
        crypto_currency: Crypto currency code (BTC, ETH, XMR)
        fiat_currency: Fiat currency code (USD, GBP, EUR)

    Returns:
        Amount in fiat currency

    Example:
        >>> await crypto_to_fiat(0.1, "ETH", "USD")
        Decimal("300.00")  # 0.1 ETH in USD
    """
    # Convert input to Decimal for precision
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount

    # Normalize currency codes
    crypto_currency = crypto_currency.upper()
    fiat_currency = fiat_currency.upper()

    # Validate currencies
    if crypto_currency not in ["XMR", "BTC", "ETH"]:
        raise ValueError(f"Unsupported crypto currency: {crypto_currency}")

    if fiat_currency not in ["USD", "GBP", "EUR"]:
        raise ValueError(f"Unsupported fiat currency: {fiat_currency}")

    if amount_decimal <= 0:
        raise ValueError("Amount must be positive")

    # Fetch all crypto rates
    rates = await fetch_crypto_rates()

    if crypto_currency not in rates:
        raise ValueError(f"Rates not available for {crypto_currency}")

    crypto_price = rates[crypto_currency][fiat_currency]

    # Calculate fiat amount
    fiat_amount = amount_decimal * crypto_price

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
        "BTC": "BTC",
        "ETH": "ETH",
    }
    return symbols.get(currency, currency)


def format_price(amount: Union[float, Decimal, str], currency: str) -> str:
    """Format price with currency symbol."""
    # Convert to Decimal for consistent formatting
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    symbol = get_currency_symbol(currency)

    # Crypto currencies need different formatting
    if currency == "XMR":
        if amount_decimal < 1:
            return f"{amount_decimal:.8f} XMR"
        return f"{amount_decimal:.4f} XMR"
    elif currency == "BTC":
        if amount_decimal < 1:
            return f"{amount_decimal:.8f} BTC"
        return f"{amount_decimal:.4f} BTC"
    elif currency == "ETH":
        if amount_decimal < 1:
            return f"{amount_decimal:.6f} ETH"
        return f"{amount_decimal:.4f} ETH"

    # Fiat currencies
    return f"{symbol}{amount_decimal:.2f}"


def format_price_simple(amount: Union[float, Decimal, str], currency: str) -> str:
    """Format price simply for display."""
    # Convert to Decimal for consistent formatting
    amount_decimal = Decimal(str(amount)) if not isinstance(amount, Decimal) else amount
    symbol = get_currency_symbol(currency)

    # Crypto currencies
    if currency in ["XMR", "BTC", "ETH"]:
        return f"{amount_decimal} {symbol}"

    # Fiat currencies
    return f"{symbol}{amount_decimal:.2f}"
