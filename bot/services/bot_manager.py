"""Bot manager for multi-tenant bot spawning."""

import asyncio
import logging
from datetime import datetime
from typing import Optional

from telegram.ext import Application, ApplicationBuilder, CommandHandler

from bot.models_multitenant import MultiTenantDatabase, Tenant

logger = logging.getLogger(__name__)


class TenantBotWorker:
    """A single bot instance for a tenant."""

    def __init__(
        self,
        tenant_id: str,
        bot_token: str,
        tenant_xmr_address: str,
        db: MultiTenantDatabase,
        swap_service,
        encryption_key: str
    ):
        self.tenant_id = tenant_id
        self.bot_token = bot_token
        self.tenant_xmr_address = tenant_xmr_address
        self.db = db
        self.swap_service = swap_service
        self.encryption_key = encryption_key
        self.application: Optional[Application] = None
        self.running = False

    async def start(self):
        """Start the bot."""
        if self.running:
            return

        try:
            self.application = (
                ApplicationBuilder()
                .token(self.bot_token)
                .build()
            )

            # Register handlers
            self._register_handlers()

            # Initialize and start polling
            await self.application.initialize()
            await self.application.start()
            await self.application.updater.start_polling()

            self.running = True
            logger.info(f"Bot started for tenant {self.tenant_id}")

        except Exception as e:
            logger.error(f"Failed to start bot for tenant {self.tenant_id}: {e}")
            raise

    async def stop(self):
        """Stop the bot."""
        if not self.running or not self.application:
            return

        try:
            await self.application.updater.stop()
            await self.application.stop()
            await self.application.shutdown()

            self.running = False
            logger.info(f"Bot stopped for tenant {self.tenant_id}")

        except Exception as e:
            logger.error(f"Error stopping bot for tenant {self.tenant_id}: {e}")

    def _register_handlers(self):
        """Register command handlers for this tenant's bot."""
        from bot.services.multicrypto_orders import MultiCryptoOrderService
        from bot.services.crypto_swap import CryptoSwapService

        order_service = MultiCryptoOrderService(self.db, self.swap_service)

        # User commands
        self.application.add_handler(
            CommandHandler("start", self._make_start_handler())
        )
        self.application.add_handler(
            CommandHandler("list", self._make_list_handler())
        )
        self.application.add_handler(
            CommandHandler("order", self._make_order_handler(order_service))
        )
        self.application.add_handler(
            CommandHandler("status", self._make_status_handler(order_service))
        )
        self.application.add_handler(
            CommandHandler("pay", self._make_pay_handler())
        )

    def _make_start_handler(self):
        """Create /start command handler."""
        tenant_id = self.tenant_id
        db = self.db

        async def start(update, context):
            tenant = db.get_tenant(tenant_id)
            shop_name = tenant.shop_name if tenant else "Shop"
            await update.message.reply_text(
                f"Welcome to {shop_name}!\n\n"
                f"Commands:\n"
                f"/list - View products\n"
                f"/order <id> <qty> <address> - Place order\n"
                f"/pay <coin> - Choose payment method (btc, eth, sol, xmr)\n"
                f"/status <order_id> - Check order status"
            )

        return start

    def _make_list_handler(self):
        """Create /list command handler."""
        tenant_id = self.tenant_id
        db = self.db

        async def list_products(update, context):
            products = db.get_products(tenant_id, active_only=True)

            if not products:
                await update.message.reply_text("No products available.")
                return

            lines = ["Available products:\n"]
            for p in products:
                stock = f"({p.inventory} in stock)" if p.inventory > 0 else "(Out of stock)"
                lines.append(f"{p.id}. {p.name} - {p.price_xmr} XMR {stock}")
                if p.description:
                    lines.append(f"   {p.description}")

            await update.message.reply_text("\n".join(lines))

        return list_products

    def _make_order_handler(self, order_service):
        """Create /order command handler."""
        tenant_id = self.tenant_id

        async def order(update, context):
            args = context.args
            if len(args) < 3:
                await update.message.reply_text(
                    "Usage: /order <product_id> <quantity> <delivery_address>\n"
                    "Example: /order 1 2 123 Main St, City"
                )
                return

            try:
                product_id = int(args[0])
                quantity = int(args[1])
                address = " ".join(args[2:])

                # Default to XMR, user can change with /pay
                payment_coin = context.user_data.get("payment_coin", "xmr")

                result = await order_service.create_order(
                    tenant_id=tenant_id,
                    product_id=product_id,
                    customer_telegram_id=update.effective_user.id,
                    quantity=quantity,
                    delivery_address=address,
                    payment_coin=payment_coin
                )

                await update.message.reply_text(
                    f"Order #{result['order_id']} created!\n\n"
                    f"{result['message']}\n\n"
                    f"Use /status {result['order_id']} to check payment status."
                )

            except ValueError as e:
                await update.message.reply_text(f"Error: {e}")
            except Exception as e:
                logger.error(f"Order creation error: {e}")
                await update.message.reply_text(
                    "An error occurred. Please try again."
                )

        return order

    def _make_status_handler(self, order_service):
        """Create /status command handler."""
        tenant_id = self.tenant_id

        async def status(update, context):
            args = context.args
            if not args:
                await update.message.reply_text("Usage: /status <order_id>")
                return

            try:
                order_id = int(args[0])
                result = await order_service.check_order_payment(order_id, tenant_id)

                status_text = (
                    f"Order #{order_id}\n"
                    f"Status: {result['state']}\n"
                    f"Payment: {result['payment_coin'].upper()}"
                )

                if result.get('swap_status'):
                    status_text += f"\nSwap: {result['swap_status']}"

                if result.get('message'):
                    status_text += f"\n\n{result['message']}"

                await update.message.reply_text(status_text)

            except ValueError as e:
                await update.message.reply_text(f"Error: {e}")

        return status

    def _make_pay_handler(self):
        """Create /pay command handler to select payment method."""
        async def pay(update, context):
            args = context.args
            supported = ["xmr", "btc", "eth", "sol", "ltc", "usdt", "usdc"]

            if not args:
                current = context.user_data.get("payment_coin", "xmr")
                await update.message.reply_text(
                    f"Current payment method: {current.upper()}\n\n"
                    f"Supported: {', '.join(c.upper() for c in supported)}\n\n"
                    f"Usage: /pay <coin>\n"
                    f"Example: /pay btc"
                )
                return

            coin = args[0].lower()
            if coin not in supported:
                await update.message.reply_text(
                    f"Unsupported coin. Choose from: {', '.join(c.upper() for c in supported)}"
                )
                return

            context.user_data["payment_coin"] = coin
            await update.message.reply_text(
                f"Payment method set to {coin.upper()}. "
                f"Your next order will be paid in {coin.upper()}."
            )

        return pay


class BotManager:
    """Manages multiple bot instances for tenants."""

    def __init__(
        self,
        db: MultiTenantDatabase,
        platform_encryption_key: str,
        swap_service
    ):
        self.db = db
        self.platform_encryption_key = platform_encryption_key
        self.swap_service = swap_service
        self.active_bots: dict[str, TenantBotWorker] = {}

    async def start_bot(self, tenant_id: str) -> bool:
        """Start a bot for a tenant."""
        if tenant_id in self.active_bots:
            logger.warning(f"Bot already running for tenant {tenant_id}")
            return True

        tenant = self.db.get_tenant(tenant_id)
        if not tenant:
            logger.error(f"Tenant not found: {tenant_id}")
            return False

        if not tenant.bot_active:
            logger.warning(f"Bot not active for tenant {tenant_id}")
            return False

        if not tenant.bot_token_encrypted:
            logger.error(f"No bot token for tenant {tenant_id}")
            return False

        if not tenant.monero_wallet_address:
            logger.error(f"No Monero wallet for tenant {tenant_id}")
            return False

        # Check for overdue invoices
        overdue = self.db.get_overdue_invoices(tenant_id)
        if overdue:
            logger.warning(f"Tenant {tenant_id} has overdue invoices, not starting bot")
            return False

        # Decrypt bot token
        token = self._decrypt_token(tenant.bot_token_encrypted)
        if not token:
            logger.error(f"Failed to decrypt bot token for tenant {tenant_id}")
            return False

        try:
            worker = TenantBotWorker(
                tenant_id=tenant_id,
                bot_token=token,
                tenant_xmr_address=tenant.monero_wallet_address,
                db=self.db,
                swap_service=self.swap_service,
                encryption_key=tenant.encryption_key
            )

            await worker.start()
            self.active_bots[tenant_id] = worker

            self.db.log_action(
                action="bot_started",
                tenant_id=tenant_id
            )

            return True

        except Exception as e:
            logger.error(f"Failed to start bot for tenant {tenant_id}: {e}")
            return False

    async def stop_bot(self, tenant_id: str) -> bool:
        """Stop a tenant's bot."""
        if tenant_id not in self.active_bots:
            return False

        try:
            await self.active_bots[tenant_id].stop()
            del self.active_bots[tenant_id]

            self.db.log_action(
                action="bot_stopped",
                tenant_id=tenant_id
            )

            return True

        except Exception as e:
            logger.error(f"Error stopping bot for tenant {tenant_id}: {e}")
            return False

    async def restart_bot(self, tenant_id: str) -> bool:
        """Restart a tenant's bot."""
        await self.stop_bot(tenant_id)
        return await self.start_bot(tenant_id)

    async def start_all_bots(self):
        """Start bots for all active tenants."""
        tenants = self.db.get_active_tenants()
        started = 0
        failed = 0

        for tenant in tenants:
            success = await self.start_bot(tenant.id)
            if success:
                started += 1
            else:
                failed += 1

        logger.info(f"Started {started} bots, {failed} failed")
        return {"started": started, "failed": failed}

    async def stop_all_bots(self):
        """Stop all running bots."""
        tenant_ids = list(self.active_bots.keys())
        for tenant_id in tenant_ids:
            await self.stop_bot(tenant_id)

        logger.info(f"Stopped {len(tenant_ids)} bots")

    def get_running_bots(self) -> list[str]:
        """Get list of tenant IDs with running bots."""
        return list(self.active_bots.keys())

    def is_bot_running(self, tenant_id: str) -> bool:
        """Check if a tenant's bot is running."""
        return tenant_id in self.active_bots

    def _decrypt_token(self, encrypted_token: str) -> Optional[str]:
        """Decrypt a bot token."""
        from nacl.secret import SecretBox
        import base64

        try:
            key = base64.b64decode(self.platform_encryption_key)
            box = SecretBox(key)
            encrypted = base64.b64decode(encrypted_token)
            decrypted = box.decrypt(encrypted)
            return decrypted.decode('utf-8')
        except Exception as e:
            logger.error(f"Failed to decrypt token: {e}")
            return None

    async def health_check(self) -> dict:
        """Get health status of bot manager."""
        return {
            "active_bots": len(self.active_bots),
            "tenant_ids": list(self.active_bots.keys()),
            "timestamp": datetime.utcnow().isoformat()
        }
