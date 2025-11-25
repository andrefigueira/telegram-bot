"""Main entry point for multi-tenant DarkPool platform."""

import asyncio
import logging
import os
import signal
import sys
from typing import Optional

from bot.config import get_settings
from bot.logging_config import setup_logging
from bot.models_multitenant import MultiTenantDatabase
from bot.services.crypto_swap import CryptoSwapService
from bot.services.commission import CommissionService
from bot.services.multicrypto_orders import MultiCryptoOrderService
from bot.services.bot_manager import BotManager
from bot.services.tenant import TenantService
from bot.tasks_multitenant import BackgroundTaskManager

logger = logging.getLogger(__name__)


class DarkPoolPlatform:
    """Main platform coordinator for multi-tenant DarkPool."""

    def __init__(
        self,
        database_url: str = "sqlite:///darkpool.db",
        platform_encryption_key: Optional[str] = None,
        platform_xmr_address: Optional[str] = None,
        trocador_api_key: Optional[str] = None,
        changenow_api_key: Optional[str] = None,
        testnet: bool = False
    ):
        self.database_url = database_url
        self.platform_encryption_key = platform_encryption_key or os.urandom(32).hex()
        self.platform_xmr_address = platform_xmr_address or ""
        self.trocador_api_key = trocador_api_key
        self.changenow_api_key = changenow_api_key
        self.testnet = testnet

        # Initialize components
        self.db: Optional[MultiTenantDatabase] = None
        self.swap_service: Optional[CryptoSwapService] = None
        self.tenant_service: Optional[TenantService] = None
        self.order_service: Optional[MultiCryptoOrderService] = None
        self.commission_service: Optional[CommissionService] = None
        self.bot_manager: Optional[BotManager] = None
        self.task_manager: Optional[BackgroundTaskManager] = None

        self._running = False

    def initialize(self):
        """Initialize all services."""
        logger.info("Initializing DarkPool platform...")

        # Database
        self.db = MultiTenantDatabase(self.database_url)
        logger.info(f"Database initialized: {self.database_url}")

        # Crypto swap service
        self.swap_service = CryptoSwapService(
            trocador_api_key=self.trocador_api_key,
            changenow_api_key=self.changenow_api_key,
            testnet=self.testnet
        )
        logger.info("Crypto swap service initialized")

        # Tenant service
        self.tenant_service = TenantService(self.db)
        logger.info("Tenant service initialized")

        # Order service
        self.order_service = MultiCryptoOrderService(self.db, self.swap_service)
        logger.info("Order service initialized")

        # Commission service
        self.commission_service = CommissionService(
            self.db,
            self.platform_xmr_address
        )
        logger.info("Commission service initialized")

        # Bot manager
        self.bot_manager = BotManager(
            self.db,
            self.platform_encryption_key,
            self.swap_service
        )
        logger.info("Bot manager initialized")

        # Background task manager
        self.task_manager = BackgroundTaskManager(
            self.db,
            self.order_service,
            self.commission_service
        )
        logger.info("Background task manager initialized")

        logger.info("DarkPool platform initialized successfully")

    async def start(self):
        """Start the platform."""
        if self._running:
            logger.warning("Platform already running")
            return

        self._running = True
        logger.info("Starting DarkPool platform...")

        # Start background tasks
        await self.task_manager.start()

        # Start all active tenant bots
        result = await self.bot_manager.start_all_bots()
        logger.info(f"Started {result['started']} bots, {result['failed']} failed")

        logger.info("DarkPool platform started successfully")

    async def stop(self):
        """Stop the platform gracefully."""
        if not self._running:
            return

        logger.info("Stopping DarkPool platform...")
        self._running = False

        # Stop background tasks
        if self.task_manager:
            await self.task_manager.stop()

        # Stop all bots
        if self.bot_manager:
            await self.bot_manager.stop_all_bots()

        # Close swap service session
        if self.swap_service:
            await self.swap_service.close()

        logger.info("DarkPool platform stopped")

    async def run_forever(self):
        """Run the platform until interrupted."""
        # Setup signal handlers
        loop = asyncio.get_event_loop()

        def signal_handler():
            logger.info("Received shutdown signal")
            asyncio.create_task(self.stop())

        for sig in (signal.SIGINT, signal.SIGTERM):
            loop.add_signal_handler(sig, signal_handler)

        # Start platform
        await self.start()

        # Keep running
        while self._running:
            await asyncio.sleep(1)

    def get_services(self) -> dict:
        """Get all services for use in API."""
        return {
            "db": self.db,
            "tenant_service": self.tenant_service,
            "order_service": self.order_service,
            "commission_service": self.commission_service,
            "bot_manager": self.bot_manager,
            "swap_service": self.swap_service,
        }


# Global platform instance
_platform: Optional[DarkPoolPlatform] = None


def get_platform() -> DarkPoolPlatform:
    """Get the global platform instance."""
    global _platform
    if _platform is None:
        raise RuntimeError("Platform not initialized. Call create_platform() first.")
    return _platform


def create_platform(
    database_url: Optional[str] = None,
    platform_encryption_key: Optional[str] = None,
    platform_xmr_address: Optional[str] = None,
    trocador_api_key: Optional[str] = None,
    changenow_api_key: Optional[str] = None,
    testnet: bool = False
) -> DarkPoolPlatform:
    """Create and initialize the global platform instance."""
    global _platform

    # Get from environment if not provided
    database_url = database_url or os.getenv("DATABASE_URL", "sqlite:///darkpool.db")
    platform_encryption_key = platform_encryption_key or os.getenv("PLATFORM_ENCRYPTION_KEY")
    platform_xmr_address = platform_xmr_address or os.getenv("PLATFORM_XMR_ADDRESS", "")
    trocador_api_key = trocador_api_key or os.getenv("TROCADOR_API_KEY")
    changenow_api_key = changenow_api_key or os.getenv("CHANGENOW_API_KEY")
    testnet = testnet or os.getenv("TESTNET", "false").lower() == "true"

    _platform = DarkPoolPlatform(
        database_url=database_url,
        platform_encryption_key=platform_encryption_key,
        platform_xmr_address=platform_xmr_address,
        trocador_api_key=trocador_api_key,
        changenow_api_key=changenow_api_key,
        testnet=testnet
    )

    _platform.initialize()
    return _platform


async def main():
    """Main entry point."""
    # Setup logging
    setup_logging()

    logger.info("=" * 60)
    logger.info("DarkPool Multi-Tenant Platform")
    logger.info("=" * 60)

    # Create and start platform
    platform = create_platform()

    try:
        await platform.run_forever()
    except KeyboardInterrupt:
        logger.info("Keyboard interrupt received")
    finally:
        await platform.stop()

    logger.info("Goodbye!")


if __name__ == "__main__":
    asyncio.run(main())
