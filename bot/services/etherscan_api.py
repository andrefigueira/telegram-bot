"""Ethereum blockchain API client using Etherscan."""

from __future__ import annotations

import asyncio
import logging
from decimal import Decimal
from datetime import datetime, timedelta
from typing import List, Dict, Optional
import aiohttp

logger = logging.getLogger(__name__)


class EtherscanAPIError(Exception):
    """Base exception for Etherscan API errors."""
    pass


class RateLimitError(EtherscanAPIError):
    """Rate limit exceeded."""
    pass


class EthereumTransaction:
    """Represents an Ethereum transaction."""

    # Wei to ETH conversion (1 ETH = 10^18 Wei)
    WEI_TO_ETH = Decimal("1000000000000000000")

    def __init__(self, data: dict):
        self.hash = data.get("hash", "")
        self.from_address = data.get("from", "").lower()
        self.to_address = data.get("to", "").lower()
        self.value_wei = Decimal(data.get("value", "0"))
        self.value_eth = self.value_wei / self.WEI_TO_ETH
        self.timestamp = datetime.fromtimestamp(int(data.get("timeStamp", 0)))
        self.confirmations = int(data.get("confirmations", 0))
        self.is_error = data.get("isError", "0") == "1"

    def __repr__(self):
        return (
            f"<EthereumTransaction {self.hash[:8]}... "
            f"{self.value_eth} ETH, {self.confirmations} confs>"
        )


class EtherscanAPI:
    """
    Client for Etherscan API.

    Rate limit: 5 requests per second (free tier)
    API key: Required (free at etherscan.io/apis)
    Fallback: Infura JSON-RPC
    """

    ETHERSCAN_URL = "https://api.etherscan.io/api"
    INFURA_URL = "https://mainnet.infura.io/v3"
    RATE_LIMIT_DELAY = 0.2  # seconds (5 req/s)

    def __init__(self, api_key: str, infura_project_id: Optional[str] = None):
        if not api_key:
            raise ValueError("Etherscan API key is required")

        self.api_key = api_key
        self.infura_project_id = infura_project_id
        self._last_request_time = None

    async def _wait_for_rate_limit(self):
        """Enforce rate limiting."""
        if self._last_request_time:
            elapsed = (datetime.utcnow() - self._last_request_time).total_seconds()
            if elapsed < self.RATE_LIMIT_DELAY:
                wait_time = self.RATE_LIMIT_DELAY - elapsed
                await asyncio.sleep(wait_time)
        self._last_request_time = datetime.utcnow()

    async def get_address_transactions(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[EthereumTransaction]:
        """
        Get transactions for an Ethereum address.

        Args:
            address: Ethereum address to query (0x...)
            since: Optional datetime to filter transactions after this time

        Returns:
            List of EthereumTransaction objects

        Raises:
            EtherscanAPIError: If API request fails
        """
        await self._wait_for_rate_limit()

        try:
            return await self._get_from_etherscan(address, since)
        except Exception as e:
            logger.warning(f"Etherscan API failed: {e}")
            if self.infura_project_id:
                logger.info("Trying Infura fallback")
                try:
                    return await self._get_from_infura(address, since)
                except Exception as e2:
                    logger.error(f"Infura also failed: {e2}")
            raise EtherscanAPIError(f"All Ethereum APIs failed: etherscan={e}")

    async def _get_from_etherscan(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[EthereumTransaction]:
        """Get transactions from Etherscan API."""
        params = {
            "module": "account",
            "action": "txlist",
            "address": address,
            "startblock": 0,
            "endblock": 99999999,
            "page": 1,
            "offset": 100,  # Last 100 transactions
            "sort": "desc",  # Newest first
            "apikey": self.api_key
        }

        async with aiohttp.ClientSession() as session:
            async with session.get(
                self.ETHERSCAN_URL,
                params=params,
                timeout=aiohttp.ClientTimeout(total=30)
            ) as response:
                if response.status == 429:
                    raise RateLimitError("Etherscan rate limit exceeded")
                elif response.status != 200:
                    raise EtherscanAPIError(f"Etherscan returned status {response.status}")

                data = await response.json()

                if data.get("status") != "1":
                    error_msg = data.get("message", "Unknown error")
                    raise EtherscanAPIError(f"Etherscan error: {error_msg}")

                transactions = []

                for tx_data in data.get("result", []):
                    tx = EthereumTransaction(tx_data)

                    # Skip error transactions
                    if tx.is_error:
                        continue

                    # Filter by time if specified
                    if since and tx.timestamp < since:
                        continue

                    # Only include incoming transactions
                    if tx.to_address.lower() == address.lower():
                        transactions.append(tx)

                return transactions

    async def _get_from_infura(
        self,
        address: str,
        since: Optional[datetime] = None
    ) -> List[EthereumTransaction]:
        """Get transactions from Infura JSON-RPC (fallback)."""
        # Note: This is a simplified fallback
        # Infura JSON-RPC doesn't have a direct "get transactions" method
        # Would need to scan recent blocks, which is expensive
        # For now, raise NotImplementedError
        raise NotImplementedError("Infura fallback not fully implemented")

    async def find_payment(
        self,
        address: str,
        expected_amount: Decimal,
        created_at: datetime,
        tolerance: Decimal = Decimal("0.001")
    ) -> Optional[EthereumTransaction]:
        """
        Find a payment to an address within a time window.

        Args:
            address: Ethereum address to check (0x...)
            expected_amount: Expected ETH amount
            created_at: Order creation time
            tolerance: Amount matching tolerance (default 0.001 ETH)

        Returns:
            EthereumTransaction if found, None otherwise
        """
        # Search 24-hour window
        since = created_at
        until = created_at + timedelta(hours=24)

        try:
            transactions = await self.get_address_transactions(address, since=since)

            for tx in transactions:
                # Check if transaction is within time window
                if tx.timestamp < since or tx.timestamp > until:
                    continue

                # Check if amount matches (within tolerance)
                amount_diff = abs(tx.value_eth - expected_amount)
                if amount_diff <= tolerance:
                    logger.info(
                        f"Found matching ETH payment: {tx.hash} "
                        f"({tx.value_eth} ETH, {tx.confirmations} confs)"
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
            tx_hash: Transaction hash (0x...)

        Returns:
            Number of confirmations
        """
        await self._wait_for_rate_limit()

        params = {
            "module": "proxy",
            "action": "eth_getTransactionReceipt",
            "txhash": tx_hash,
            "apikey": self.api_key
        }

        try:
            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self.ETHERSCAN_URL,
                    params=params,
                    timeout=aiohttp.ClientTimeout(total=30)
                ) as response:
                    if response.status != 200:
                        logger.warning(f"Failed to get tx confirmations: status {response.status}")
                        return 0

                    data = await response.json()
                    receipt = data.get("result")

                    if not receipt or not receipt.get("blockNumber"):
                        return 0

                    # Get current block number
                    block_params = {
                        "module": "proxy",
                        "action": "eth_blockNumber",
                        "apikey": self.api_key
                    }

                    async with session.get(
                        self.ETHERSCAN_URL,
                        params=block_params,
                        timeout=aiohttp.ClientTimeout(total=30)
                    ) as block_response:
                        if block_response.status != 200:
                            return 0

                        block_data = await block_response.json()
                        current_block = int(block_data.get("result", "0"), 16)
                        tx_block = int(receipt.get("blockNumber", "0"), 16)

                        confirmations = current_block - tx_block + 1
                        return max(0, confirmations)

        except Exception as e:
            logger.error(f"Error getting transaction confirmations: {e}")
            return 0

    @staticmethod
    def eth_to_wei(eth_amount: Decimal) -> int:
        """Convert ETH to Wei."""
        return int(eth_amount * EthereumTransaction.WEI_TO_ETH)

    @staticmethod
    def wei_to_eth(wei_amount: int) -> Decimal:
        """Convert Wei to ETH."""
        return Decimal(wei_amount) / EthereumTransaction.WEI_TO_ETH
