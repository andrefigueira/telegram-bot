"""Bitcoin blockchain API client for payment verification."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)


class BlockchainAPIError(Exception):
    """Base exception for blockchain API errors."""
    pass


class RateLimitError(BlockchainAPIError):
    """Rate limit exceeded."""
    pass


class Transaction:
    """Represents a Bitcoin transaction."""

    def __init__(self, data: dict):
        self.hash = data.get("hash", "")
        self.time = datetime.fromtimestamp(data.get("time", 0))
        self.confirmations = data.get("block_height", 0)

        # Parse outputs to get received amount
        self.received_btc = Decimal("0")
        for output in data.get("out", []):
            if output.get("addr"):
                self.received_btc += Decimal(output.get("value", 0)) / Decimal("100000000")  # Satoshis to BTC

    def __repr__(self):
        return f"<Transaction {self.hash[:8]}... {self.received_btc} BTC, {self.confirmations} confs>"


class BlockchainAPI:
    """
    Client for blockchain.info API.

    Rate limit: 1 request per 10 seconds (free tier)
    Fallback: BlockCypher API
    """

    BLOCKCHAIN_INFO_URL = "https://blockchain.info"
    BLOCKCYPHER_URL = "https://api.blockcypher.com/v1/btc/main"
    RATE_LIMIT_DELAY = 10  # seconds

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key
        self._last_request_time = None

    async def _wait_for_rate_limit(self):
        """Enforce rate limiting."""
        if self._last_request_time:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.RATE_LIMIT_DELAY:
                wait_time = self.RATE_LIMIT_DELAY - elapsed
                logger.debug(f"Rate limit: waiting {wait_time:.1f}s")
                await asyncio.sleep(wait_time)
        self._last_request_time = datetime.utcnow()

    async def get_address_transactions(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[Transaction]:
        """
        Get transactions for a Bitcoin address.

        Args:
            address: Bitcoin address to query
            since: Optional datetime to filter transactions after this time

        Returns:
            List of Transaction objects

        Raises:
            BlockchainAPIError: If API request fails
        """
        await self._wait_for_rate_limit()

        try:
            return await self._get_from_blockchain_info(address, since)
        except Exception as e:
            logger.warning(f"blockchain.info API failed: {e}, trying BlockCypher fallback")
            try:
                return await self._get_from_blockcypher(address, since)
            except Exception as e2:
                logger.error(f"BlockCypher API also failed: {e2}")
                raise BlockchainAPIError(
                    f"All Bitcoin APIs failed: blockchain.info={e}, blockcypher={e2}"
                )

    async def _get_from_blockchain_info(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[Transaction]:
        """Get transactions from blockchain.info API."""
        url = f"{self.BLOCKCHAIN_INFO_URL}/rawaddr/{address}?limit=50"

        async with aiohttp.ClientSession() as session:
            async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                if response.status == 429:
                    raise RateLimitError("blockchain.info rate limit exceeded")
                elif response.status != 200:
                    raise BlockchainAPIError(
                        f"blockchain.info returned status {response.status}"
                    )

                data = await response.json()
                transactions = []

                for tx_data in data.get("txs", []):
                    tx = Transaction(tx_data)

                    # Filter by time if specified
                    if since and tx.time < since:
                        continue

                    transactions.append(tx)

                return transactions

    async def _get_from_blockcypher(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[Transaction]:
        """Get transactions from BlockCypher API (fallback)."""
        url = f"{self.BLOCKCYPHER_URL}/addrs/{address}/full"
        params = {"limit": 50}

        if self.api_key:
            params["token"] = self.api_key

        async with aiohttp.ClientSession() as session:
            async with session.get(
                url,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 429:
                    raise RateLimitError("BlockCypher rate limit exceeded")
                elif response.status != 200:
                    raise BlockchainAPIError(
                        f"BlockCypher returned status {response.status}"
                    )

                data = await response.json()
                transactions = []

                for tx_data in data.get("txs", []):
                    # Convert BlockCypher format to our format
                    normalized = {
                        "hash": tx_data.get("hash", ""),
                        "time": datetime.fromisoformat(
                            tx_data.get("received", "").replace("Z", "+00:00")
                        ).timestamp(),
                        "block_height": tx_data.get("confirmations", 0),
                        "out": [
                            {"addr": output.get("addresses", [None])[0], "value": output.get("value", 0)}
                            for output in tx_data.get("outputs", [])
                        ]
                    }
                    tx = Transaction(normalized)

                    # Filter by time if specified
                    if since and tx.time < since:
                        continue

                    transactions.append(tx)

                return transactions

    async def find_payment(
        self,
        address: str,
        expected_amount: Decimal,
        created_at: datetime,
        tolerance: Decimal = Decimal("0.00001")
    ) -> Optional[Transaction]:
        """
        Find a payment to an address within a time window.

        Args:
            address: Bitcoin address to check
            expected_amount: Expected BTC amount
            created_at: Order creation time
            tolerance: Amount matching tolerance (default 0.00001 BTC)

        Returns:
            Transaction if found, None otherwise
        """
        # Search 24-hour window
        since = created_at
        until = created_at + timedelta(hours=24)

        try:
            transactions = await self.get_address_transactions(address, since=since)

            for tx in transactions:
                # Check if transaction is within time window
                if tx.time < since or tx.time > until:
                    continue

                # Check if amount matches (within tolerance)
                amount_diff = abs(tx.received_btc - expected_amount)
                if amount_diff <= tolerance:
                    logger.info(
                        f"Found matching BTC payment: {tx.hash} "
                        f"({tx.received_btc} BTC, {tx.confirmations} confs)"
                    )
                    return tx

            logger.debug(f"No matching payment found for {address}")
            return None

        except Exception as e:
            logger.error(f"Error finding payment: {e}")
            raise

    async def get_transaction_confirmations(self, tx_hash: str) -> int:
        """
        Get the number of confirmations for a transaction.

        Args:
            tx_hash: Transaction hash

        Returns:
            Number of confirmations
        """
        await self._wait_for_rate_limit()

        url = f"{self.BLOCKCHAIN_INFO_URL}/rawtx/{tx_hash}"

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(url, timeout=aiohttp.ClientTimeout(total=30)) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get tx confirmations: status {response.status}")
                        return 0

                    data = await response.json()
                    return data.get("block_height", 0)

        except Exception as e:
            logger.error(f"Error getting transaction confirmations: {e}")
            return 0
