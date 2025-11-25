"""Tests for health check module."""

import pytest
from unittest.mock import MagicMock, patch, AsyncMock
from aiohttp import web
from aiohttp.test_utils import make_mocked_request

from bot.health import HealthCheckServer
from bot.models import Database


class TestHealthCheckServer:
    """Test health check server functionality."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database."""
        return MagicMock(spec=Database)

    @pytest.fixture
    def health_server(self, mock_db):
        """Create health check server instance."""
        return HealthCheckServer(mock_db)

    @pytest.mark.asyncio
    async def test_health_check(self, health_server):
        """Test basic health check endpoint."""
        request = make_mocked_request('GET', '/health')
        response = await health_server.health_check(request)
        
        assert response.status == 200
        assert response.content_type == 'application/json'
        # Check response body
        body = response.body
        assert b'{"status": "healthy"}' in body

    @pytest.mark.asyncio
    async def test_readiness_check_success(self, health_server, mock_db):
        """Test readiness check with healthy database."""
        # Mock successful database connection
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock()
        mock_db.session = MagicMock(return_value=mock_session)
        
        request = make_mocked_request('GET', '/ready')
        response = await health_server.readiness_check(request)
        
        assert response.status == 200
        assert response.content_type == 'application/json'
        body = response.body
        assert b'"status": "ready"' in body
        assert b'"database": "ok"' in body

    @pytest.mark.asyncio
    async def test_readiness_check_db_failure(self, health_server, mock_db):
        """Test readiness check with database failure."""
        # Mock database connection failure
        mock_db.session = MagicMock(side_effect=Exception("DB connection failed"))
        
        request = make_mocked_request('GET', '/ready')
        response = await health_server.readiness_check(request)
        
        assert response.status == 503
        assert response.content_type == 'application/json'
        body = response.body
        assert b'"status": "not ready"' in body
        assert b'"database": "failed"' in body

    @pytest.mark.asyncio
    async def test_start_enabled(self, health_server):
        """Test starting health check server when enabled."""
        with patch('bot.health.get_settings') as mock_settings:
            mock_settings.return_value.health_check_enabled = True
            mock_settings.return_value.health_check_port = 8080
            
            with patch('aiohttp.web.AppRunner') as mock_runner:
                mock_runner_instance = AsyncMock()
                mock_runner.return_value = mock_runner_instance
                
                with patch('aiohttp.web.TCPSite') as mock_site:
                    mock_site_instance = AsyncMock()
                    mock_site.return_value = mock_site_instance
                    
                    await health_server.start()
                    
                    mock_runner.assert_called_once()
                    mock_runner_instance.setup.assert_called_once()
                    mock_site.assert_called_once_with(mock_runner_instance, "0.0.0.0", 8080)
                    mock_site_instance.start.assert_called_once()
                    assert health_server.runner is mock_runner_instance

    @pytest.mark.asyncio
    async def test_start_disabled(self, health_server):
        """Test starting health check server when disabled."""
        with patch('bot.health.get_settings') as mock_settings:
            mock_settings.return_value.health_check_enabled = False
            
            await health_server.start()
            
            # Runner should not be created
            assert health_server.runner is None

    @pytest.mark.asyncio
    async def test_stop_with_runner(self, health_server):
        """Test stopping health check server with active runner."""
        mock_runner = AsyncMock()
        health_server.runner = mock_runner
        
        await health_server.stop()
        
        mock_runner.cleanup.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_without_runner(self, health_server):
        """Test stopping health check server without runner."""
        health_server.runner = None
        
        # Should not raise exception
        await health_server.stop()