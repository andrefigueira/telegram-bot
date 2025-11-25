"""Crypto swap service for multi-currency to XMR conversion."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from enum import Enum
from typing import Optional

import aiohttp

logger = logging.getLogger(__name__)


class SwapStatus(str, Enum):
    """Status of a swap transaction."""
    WAITING = "waiting"
    CONFIRMING = "confirming"
    EXCHANGING = "exchanging"
    COMPLETE = "complete"
    FAILED = "failed"
    EXPIRED = "expired"


class SupportedCoin(str, Enum):
    """Supported cryptocurrencies for payment."""
    XMR = "xmr"
    BTC = "btc"
    ETH = "eth"
    SOL = "sol"
    LTC = "ltc"
    USDT = "usdt"
    USDC = "usdc"


@dataclass
class SwapQuote:
    """Quote for a crypto swap."""
    from_coin: str
    to_coin: str
    from_amount: Decimal
    to_amount: Decimal
    rate: Decimal
    provider: str
    quote_id: str
    expires_at: datetime


@dataclass
class SwapOrder:
    """A created swap order."""
    swap_id: str
    from_coin: str
    to_coin: str
    deposit_address: str
    expected_amount: Decimal
    destination_address: str
    provider: str
    status: SwapStatus
    expires_at: datetime
    created_at: datetime


class CryptoSwapService:
    """Handle multi-crypto to XMR conversions via swap services."""

    SUPPORTED_COINS = [coin.value for coin in SupportedCoin]

    def __init__(
        self,
        trocador_api_key: Optional[str] = None,
        changenow_api_key: Optional[str] = None,
        preferred_provider: str = "trocador",
        testnet: bool = False
    ):
        self.trocador_api_key = trocador_api_key
        self.changenow_api_key = changenow_api_key
        self.preferred_provider = preferred_provider
        self.testnet = testnet

        # API endpoints
        self.trocador_base = "https://trocador.app/api"
        self.changenow_base = "https://api.changenow.io/v2"

        self._session: Optional[aiohttp.ClientSession] = None

    async def _get_session(self) -> aiohttp.ClientSession:
        """Get or create aiohttp session."""
        if self._session is None or self._session.closed:
            self._session = aiohttp.ClientSession(
                timeout=aiohttp.ClientTimeout(total=30)
            )
        return self._session

    async def close(self):
        """Close the HTTP session."""
        if self._session and not self._session.closed:
            await self._session.close()

    async def get_supported_coins(self) -> list[str]:
        """Get list of supported coins for swapping to XMR."""
        return self.SUPPORTED_COINS

    async def get_rate(
        self,
        from_coin: str,
        amount: Decimal
    ) -> Optional[SwapQuote]:
        """Get exchange rate for swapping to XMR."""
        from_coin = from_coin.lower()

        if from_coin not in self.SUPPORTED_COINS:
            raise ValueError(f"Unsupported coin: {from_coin}")

        if from_coin == "xmr":
            # No swap needed
            return SwapQuote(
                from_coin="xmr",
                to_coin="xmr",
                from_amount=amount,
                to_amount=amount,
                rate=Decimal("1"),
                provider="direct",
                quote_id="direct",
                expires_at=datetime.utcnow() + timedelta(hours=24)
            )

        # Try preferred provider first
        if self.preferred_provider == "trocador" and self.trocador_api_key:
            quote = await self._get_trocador_rate(from_coin, amount)
            if quote:
                return quote

        # Fallback to ChangeNow
        if self.changenow_api_key:
            quote = await self._get_changenow_rate(from_coin, amount)
            if quote:
                return quote

        # Development fallback
        if self.testnet:
            return self._get_mock_rate(from_coin, amount)

        return None

    async def _get_trocador_rate(
        self,
        from_coin: str,
        amount: Decimal
    ) -> Optional[SwapQuote]:
        """Get rate from Trocador aggregator."""
        try:
            session = await self._get_session()
            params = {
                "api_key": self.trocador_api_key,
                "ticker_from": from_coin,
                "ticker_to": "xmr",
                "amount_from": str(amount),
            }

            async with session.get(
                f"{self.trocador_base}/new_rate",
                params=params
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Trocador rate failed: {resp.status}")
                    return None

                data = await resp.json()

                if not data.get("success"):
                    return None

                return SwapQuote(
                    from_coin=from_coin,
                    to_coin="xmr",
                    from_amount=amount,
                    to_amount=Decimal(str(data["amount_to"])),
                    rate=Decimal(str(data["rate"])),
                    provider="trocador",
                    quote_id=data.get("id", ""),
                    expires_at=datetime.utcnow() + timedelta(minutes=10)
                )

        except Exception as e:
            logger.error(f"Trocador rate error: {e}")
            return None

    async def _get_changenow_rate(
        self,
        from_coin: str,
        amount: Decimal
    ) -> Optional[SwapQuote]:
        """Get rate from ChangeNow."""
        try:
            session = await self._get_session()
            headers = {"x-changenow-api-key": self.changenow_api_key}

            # Get estimated amount
            async with session.get(
                f"{self.changenow_base}/exchange/estimated-amount",
                params={
                    "fromCurrency": from_coin,
                    "toCurrency": "xmr",
                    "fromAmount": str(amount),
                    "flow": "standard"
                },
                headers=headers
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"ChangeNow rate failed: {resp.status}")
                    return None

                data = await resp.json()

                to_amount = Decimal(str(data["toAmount"]))
                rate = to_amount / amount if amount > 0 else Decimal("0")

                return SwapQuote(
                    from_coin=from_coin,
                    to_coin="xmr",
                    from_amount=amount,
                    to_amount=to_amount,
                    rate=rate,
                    provider="changenow",
                    quote_id="",
                    expires_at=datetime.utcnow() + timedelta(minutes=10)
                )

        except Exception as e:
            logger.error(f"ChangeNow rate error: {e}")
            return None

    def _get_mock_rate(self, from_coin: str, amount: Decimal) -> SwapQuote:
        """Get mock rate for testing."""
        # Approximate rates for testing
        mock_rates = {
            "btc": Decimal("250"),      # 1 BTC = ~250 XMR
            "eth": Decimal("15"),       # 1 ETH = ~15 XMR
            "sol": Decimal("0.8"),      # 1 SOL = ~0.8 XMR
            "ltc": Decimal("0.5"),      # 1 LTC = ~0.5 XMR
            "usdt": Decimal("0.006"),   # 1 USDT = ~0.006 XMR
            "usdc": Decimal("0.006"),   # 1 USDC = ~0.006 XMR
        }

        rate = mock_rates.get(from_coin, Decimal("1"))
        to_amount = amount * rate

        return SwapQuote(
            from_coin=from_coin,
            to_coin="xmr",
            from_amount=amount,
            to_amount=to_amount,
            rate=rate,
            provider="mock",
            quote_id="mock_quote",
            expires_at=datetime.utcnow() + timedelta(minutes=30)
        )

    async def create_swap(
        self,
        from_coin: str,
        from_amount: Decimal,
        destination_xmr_address: str,
        refund_address: Optional[str] = None
    ) -> Optional[SwapOrder]:
        """Create a swap order from any coin to XMR."""
        from_coin = from_coin.lower()

        if from_coin not in self.SUPPORTED_COINS:
            raise ValueError(f"Unsupported coin: {from_coin}")

        if from_coin == "xmr":
            # No swap needed, return direct payment info
            return SwapOrder(
                swap_id="direct",
                from_coin="xmr",
                to_coin="xmr",
                deposit_address=destination_xmr_address,
                expected_amount=from_amount,
                destination_address=destination_xmr_address,
                provider="direct",
                status=SwapStatus.WAITING,
                expires_at=datetime.utcnow() + timedelta(hours=24),
                created_at=datetime.utcnow()
            )

        # Try preferred provider first
        if self.preferred_provider == "trocador" and self.trocador_api_key:
            order = await self._create_trocador_swap(
                from_coin, from_amount, destination_xmr_address, refund_address
            )
            if order:
                return order

        # Fallback to ChangeNow
        if self.changenow_api_key:
            order = await self._create_changenow_swap(
                from_coin, from_amount, destination_xmr_address, refund_address
            )
            if order:
                return order

        # Development fallback
        if self.testnet:
            return self._create_mock_swap(
                from_coin, from_amount, destination_xmr_address
            )

        return None

    async def _create_trocador_swap(
        self,
        from_coin: str,
        from_amount: Decimal,
        destination: str,
        refund_address: Optional[str]
    ) -> Optional[SwapOrder]:
        """Create swap via Trocador."""
        try:
            session = await self._get_session()

            data = {
                "api_key": self.trocador_api_key,
                "ticker_from": from_coin,
                "ticker_to": "xmr",
                "amount_from": str(from_amount),
                "address": destination,
                "refund": refund_address or "",
            }

            async with session.post(
                f"{self.trocador_base}/new_trade",
                json=data
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"Trocador swap failed: {resp.status}")
                    return None

                result = await resp.json()

                if not result.get("success"):
                    return None

                return SwapOrder(
                    swap_id=result["trade_id"],
                    from_coin=from_coin,
                    to_coin="xmr",
                    deposit_address=result["address_provider"],
                    expected_amount=Decimal(str(result["amount_to"])),
                    destination_address=destination,
                    provider="trocador",
                    status=SwapStatus.WAITING,
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                    created_at=datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"Trocador swap error: {e}")
            return None

    async def _create_changenow_swap(
        self,
        from_coin: str,
        from_amount: Decimal,
        destination: str,
        refund_address: Optional[str]
    ) -> Optional[SwapOrder]:
        """Create swap via ChangeNow."""
        try:
            session = await self._get_session()
            headers = {"x-changenow-api-key": self.changenow_api_key}

            data = {
                "fromCurrency": from_coin,
                "toCurrency": "xmr",
                "fromAmount": str(from_amount),
                "address": destination,
                "flow": "standard",
            }

            if refund_address:
                data["refundAddress"] = refund_address

            async with session.post(
                f"{self.changenow_base}/exchange",
                json=data,
                headers=headers
            ) as resp:
                if resp.status != 200:
                    logger.warning(f"ChangeNow swap failed: {resp.status}")
                    return None

                result = await resp.json()

                return SwapOrder(
                    swap_id=result["id"],
                    from_coin=from_coin,
                    to_coin="xmr",
                    deposit_address=result["payinAddress"],
                    expected_amount=Decimal(str(result["toAmount"])),
                    destination_address=destination,
                    provider="changenow",
                    status=SwapStatus.WAITING,
                    expires_at=datetime.utcnow() + timedelta(hours=24),
                    created_at=datetime.utcnow()
                )

        except Exception as e:
            logger.error(f"ChangeNow swap error: {e}")
            return None

    def _create_mock_swap(
        self,
        from_coin: str,
        from_amount: Decimal,
        destination: str
    ) -> SwapOrder:
        """Create mock swap for testing."""
        import secrets

        mock_addresses = {
            "btc": "bc1qtest" + secrets.token_hex(16),
            "eth": "0x" + secrets.token_hex(20),
            "sol": secrets.token_hex(32),
            "ltc": "ltc1qtest" + secrets.token_hex(16),
            "usdt": "0x" + secrets.token_hex(20),
            "usdc": "0x" + secrets.token_hex(20),
        }

        quote = self._get_mock_rate(from_coin, from_amount)

        return SwapOrder(
            swap_id="mock_" + secrets.token_hex(8),
            from_coin=from_coin,
            to_coin="xmr",
            deposit_address=mock_addresses.get(from_coin, "mock_address"),
            expected_amount=quote.to_amount,
            destination_address=destination,
            provider="mock",
            status=SwapStatus.WAITING,
            expires_at=datetime.utcnow() + timedelta(hours=24),
            created_at=datetime.utcnow()
        )

    async def check_swap_status(self, swap_id: str, provider: str) -> SwapStatus:
        """Check the status of a swap order."""
        if provider == "direct" or provider == "mock":
            # For direct XMR or mock, assume complete after creation
            return SwapStatus.COMPLETE

        if provider == "trocador":
            return await self._check_trocador_status(swap_id)

        if provider == "changenow":
            return await self._check_changenow_status(swap_id)

        return SwapStatus.FAILED

    async def _check_trocador_status(self, swap_id: str) -> SwapStatus:
        """Check Trocador swap status."""
        try:
            session = await self._get_session()

            async with session.get(
                f"{self.trocador_base}/trade",
                params={
                    "api_key": self.trocador_api_key,
                    "id": swap_id
                }
            ) as resp:
                if resp.status != 200:
                    return SwapStatus.FAILED

                data = await resp.json()
                status = data.get("status", "").lower()

                status_map = {
                    "waiting": SwapStatus.WAITING,
                    "confirming": SwapStatus.CONFIRMING,
                    "exchanging": SwapStatus.EXCHANGING,
                    "complete": SwapStatus.COMPLETE,
                    "finished": SwapStatus.COMPLETE,
                    "failed": SwapStatus.FAILED,
                    "expired": SwapStatus.EXPIRED,
                }

                return status_map.get(status, SwapStatus.WAITING)

        except Exception as e:
            logger.error(f"Trocador status check error: {e}")
            return SwapStatus.FAILED

    async def _check_changenow_status(self, swap_id: str) -> SwapStatus:
        """Check ChangeNow swap status."""
        try:
            session = await self._get_session()
            headers = {"x-changenow-api-key": self.changenow_api_key}

            async with session.get(
                f"{self.changenow_base}/exchange/by-id",
                params={"id": swap_id},
                headers=headers
            ) as resp:
                if resp.status != 200:
                    return SwapStatus.FAILED

                data = await resp.json()
                status = data.get("status", "").lower()

                status_map = {
                    "new": SwapStatus.WAITING,
                    "waiting": SwapStatus.WAITING,
                    "confirming": SwapStatus.CONFIRMING,
                    "exchanging": SwapStatus.EXCHANGING,
                    "sending": SwapStatus.EXCHANGING,
                    "finished": SwapStatus.COMPLETE,
                    "failed": SwapStatus.FAILED,
                    "refunded": SwapStatus.FAILED,
                    "expired": SwapStatus.EXPIRED,
                }

                return status_map.get(status, SwapStatus.WAITING)

        except Exception as e:
            logger.error(f"ChangeNow status check error: {e}")
            return SwapStatus.FAILED

    async def get_minimum_amount(self, from_coin: str) -> Optional[Decimal]:
        """Get minimum swap amount for a coin."""
        from_coin = from_coin.lower()

        if from_coin == "xmr":
            return Decimal("0.001")

        # Approximate minimums (these vary by provider)
        minimums = {
            "btc": Decimal("0.0001"),
            "eth": Decimal("0.01"),
            "sol": Decimal("0.1"),
            "ltc": Decimal("0.01"),
            "usdt": Decimal("10"),
            "usdc": Decimal("10"),
        }

        return minimums.get(from_coin)
