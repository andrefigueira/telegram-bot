"""Health check endpoint for monitoring."""

import asyncio
import logging
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
        self.runner = None

    async def root(self, request: web.Request) -> web.Response:
        """Root endpoint with API info."""
        return web.json_response({
            "name": "Telegram Bot API",
            "version": "1.0.0",
            "endpoints": ["/", "/health", "/ready"]
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