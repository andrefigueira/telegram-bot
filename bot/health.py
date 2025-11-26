"""Health check endpoint for monitoring."""

import asyncio
import logging
from datetime import datetime
from aiohttp import web
from typing import Any, Dict

from .models import Database
from .config import get_settings

logger = logging.getLogger(__name__)


class HealthCheckServer:
    """Simple HTTP server for health checks."""

    def __init__(self, db: Database):
        self.db = db
        self.app = web.Application()
        self.app.router.add_get("/", self.root)
        self.app.router.add_get("/health", self.health_check)
        self.app.router.add_get("/ready", self.readiness_check)
        self.app.router.add_get("/status", self.full_status)
        self.runner = None
        self.start_time = datetime.utcnow()

    async def root(self, request: web.Request) -> web.Response:
        """Root endpoint with API info."""
        return web.json_response({
            "name": "Telegram Bot API",
            "version": "1.0.0",
            "endpoints": ["/", "/health", "/ready", "/status"]
        })

    async def health_check(self, request: web.Request) -> web.Response:
        """Basic health check - service is running."""
        return web.json_response({"status": "healthy"})

    async def readiness_check(self, request: web.Request) -> web.Response:
        """Readiness check - service is ready to accept traffic."""
        checks: Dict[str, Any] = {
            "status": "ready",
            "checks": {}
        }

        # Check database connection
        try:
            from sqlmodel import text
            with self.db.session() as session:
                session.exec(text("SELECT 1"))
            checks["checks"]["database"] = "ok"
        except Exception as e:
            logger.error(f"Database health check failed: {e}")
            checks["checks"]["database"] = "failed"
            checks["status"] = "not ready"
            return web.json_response(checks, status=503)

        return web.json_response(checks)

    async def full_status(self, request: web.Request) -> web.Response:
        """Full status check of all services."""
        settings = get_settings()
        uptime = (datetime.utcnow() - self.start_time).total_seconds()

        status: Dict[str, Any] = {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "uptime_seconds": int(uptime),
            "environment": settings.environment,
            "services": {}
        }

        all_ok = True

        # 1. Database check
        try:
            from sqlmodel import text, select
            from .models import Order, Vendor, Product
            with self.db.session() as session:
                session.exec(text("SELECT 1"))
                # Get counts
                order_count = len(list(session.exec(select(Order))))
                vendor_count = len(list(session.exec(select(Vendor))))
                product_count = len(list(session.exec(select(Product))))
            status["services"]["database"] = {
                "status": "ok",
                "orders": order_count,
                "vendors": vendor_count,
                "products": product_count
            }
        except Exception as e:
            logger.error(f"Database status check failed: {e}")
            status["services"]["database"] = {"status": "error", "error": str(e)}
            all_ok = False

        # 2. Monero RPC check
        if settings.monero_rpc_url:
            try:
                import httpx

                # Use digest auth (Monero RPC requires digest, not basic)
                auth = None
                if settings.monero_rpc_user and settings.monero_rpc_password:
                    auth = httpx.DigestAuth(settings.monero_rpc_user, settings.monero_rpc_password)

                async with httpx.AsyncClient(timeout=5.0) as client:
                    resp = await client.post(
                        settings.monero_rpc_url + "/json_rpc",
                        json={"jsonrpc": "2.0", "id": "0", "method": "get_height"},
                        auth=auth
                    )

                if resp.status_code == 200:
                    data = resp.json()
                    if "error" in data:
                        # RPC responded but with error (e.g., no wallet)
                        status["services"]["monero_rpc"] = {
                            "status": "connected",
                            "url": settings.monero_rpc_url,
                            "note": data["error"].get("message", "RPC error")
                        }
                    else:
                        height = data.get("result", {}).get("height", "unknown")
                        status["services"]["monero_rpc"] = {
                            "status": "ok",
                            "url": settings.monero_rpc_url,
                            "wallet_height": height
                        }
                elif resp.status_code == 401:
                    status["services"]["monero_rpc"] = {
                        "status": "auth_error",
                        "url": settings.monero_rpc_url,
                        "error": "Authentication failed"
                    }
                    all_ok = False
                else:
                    status["services"]["monero_rpc"] = {
                        "status": "error",
                        "url": settings.monero_rpc_url,
                        "http_status": resp.status_code
                    }
                    all_ok = False
            except asyncio.TimeoutError:
                status["services"]["monero_rpc"] = {
                    "status": "timeout",
                    "url": settings.monero_rpc_url,
                    "error": "Connection timed out"
                }
                all_ok = False
            except Exception as e:
                status["services"]["monero_rpc"] = {
                    "status": "error",
                    "url": settings.monero_rpc_url,
                    "error": str(e)
                }
                all_ok = False
        else:
            status["services"]["monero_rpc"] = {
                "status": "not_configured",
                "note": "Using vendor wallet fallback mode"
            }

        # 3. Telegram Bot check (verify token is set)
        if settings.telegram_token:
            try:
                import aiohttp
                async with aiohttp.ClientSession() as client:
                    async with client.get(
                        f"https://api.telegram.org/bot{settings.telegram_token}/getMe",
                        timeout=aiohttp.ClientTimeout(total=5)
                    ) as resp:
                        if resp.status == 200:
                            data = await resp.json()
                            bot_info = data.get("result", {})
                            status["services"]["telegram"] = {
                                "status": "ok",
                                "bot_username": bot_info.get("username"),
                                "bot_id": bot_info.get("id")
                            }
                        else:
                            status["services"]["telegram"] = {
                                "status": "error",
                                "http_status": resp.status
                            }
                            all_ok = False
            except Exception as e:
                status["services"]["telegram"] = {"status": "error", "error": str(e)}
                all_ok = False
        else:
            status["services"]["telegram"] = {"status": "not_configured"}
            all_ok = False

        # 4. Encryption key check
        if settings.encryption_key:
            try:
                import base64
                key_bytes = base64.b64decode(settings.encryption_key)
                if len(key_bytes) == 32:
                    status["services"]["encryption"] = {"status": "ok", "key_length": 256}
                else:
                    status["services"]["encryption"] = {"status": "warning", "key_length": len(key_bytes) * 8}
            except Exception as e:
                status["services"]["encryption"] = {"status": "error", "error": "Invalid key format"}
                all_ok = False
        else:
            status["services"]["encryption"] = {"status": "not_configured"}
            all_ok = False

        # Overall status
        if not all_ok:
            status["status"] = "degraded"

        return web.json_response(status)
    
    async def start(self) -> None:
        """Start the health check server."""
        settings = get_settings()
        if not settings.health_check_enabled:
            return
            
        self.runner = web.AppRunner(self.app)
        await self.runner.setup()
        site = web.TCPSite(self.runner, "0.0.0.0", settings.health_check_port)
        await site.start()
        logger.info(f"Health check server started on port {settings.health_check_port}")
    
    async def stop(self) -> None:
        """Stop the health check server."""
        if self.runner:
            await self.runner.cleanup()
            logger.info("Health check server stopped")