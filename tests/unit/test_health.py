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

    @pytest.mark.asyncio
    async def test_root_endpoint(self, health_server):
        """Test root endpoint returns API info."""
        request = make_mocked_request('GET', '/')
        response = await health_server.root(request)

        assert response.status == 200
        assert response.content_type == 'application/json'
        body = response.body
        assert b'"name": "Telegram Bot API"' in body
        assert b'"version": "1.0.0"' in body
        assert b'/health' in body
        assert b'/ready' in body
        assert b'/status' in body

    @pytest.mark.asyncio
    async def test_full_status_all_healthy(self, health_server, mock_db):
        """Test full status with all services healthy."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            request = make_mocked_request('GET', '/status')
            response = await health_server.full_status(request)

            assert response.status == 200
            body = response.body
            assert b'"status"' in body

    @pytest.mark.asyncio
    async def test_full_status_db_error(self, health_server, mock_db):
        """Test full status with database error."""
        mock_db.session = MagicMock(side_effect=Exception("DB error"))

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            request = make_mocked_request('GET', '/status')
            response = await health_server.full_status(request)

            assert response.status == 200
            body = response.body
            assert b'"database"' in body
            assert b'"error"' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_success(self, health_server, mock_db):
        """Test full status with Monero RPC responding."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"result": {"height": 1000}}

                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"monero_rpc"' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_with_auth(self, health_server, mock_db):
        """Test full status with Monero RPC using authentication."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = 'user'
            settings.monero_rpc_password = 'pass'
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"result": {"height": 1000}}

                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_error_response(self, health_server, mock_db):
        """Test full status with Monero RPC returning error."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 200
                mock_response.json.return_value = {"error": {"message": "No wallet"}}

                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"monero_rpc"' in body
                assert b'"connected"' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_auth_error(self, health_server, mock_db):
        """Test full status with Monero RPC auth failure."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 401

                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"auth_error"' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_http_error(self, health_server, mock_db):
        """Test full status with Monero RPC HTTP error."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_response = MagicMock()
                mock_response.status_code = 500

                mock_client_instance = AsyncMock()
                mock_client_instance.post.return_value = mock_response
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"http_status": 500' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_timeout(self, health_server, mock_db):
        """Test full status with Monero RPC timeout."""
        import asyncio
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.side_effect = asyncio.TimeoutError()
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"timeout"' in body

    @pytest.mark.asyncio
    async def test_full_status_monero_rpc_exception(self, health_server, mock_db):
        """Test full status with Monero RPC general exception."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = 'http://localhost:18082'
            settings.monero_rpc_user = None
            settings.monero_rpc_password = None
            settings.telegram_token = None
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('httpx.AsyncClient') as mock_client:
                mock_client_instance = AsyncMock()
                mock_client_instance.post.side_effect = Exception("Connection error")
                mock_client.return_value.__aenter__.return_value = mock_client_instance

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"error"' in body

    @pytest.mark.asyncio
    async def test_full_status_telegram_success(self, health_server, mock_db):
        """Test full status with Telegram API success."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = '123:ABC'
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('aiohttp.ClientSession') as mock_session_cls:
                mock_resp = AsyncMock()
                mock_resp.status = 200
                mock_resp.json = AsyncMock(return_value={
                    "ok": True,
                    "result": {"id": 123, "username": "test_bot"}
                })

                mock_cm = AsyncMock()
                mock_cm.__aenter__.return_value = mock_resp

                mock_client = MagicMock()
                mock_client.get.return_value = mock_cm
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_session_cls.return_value = mock_client

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"telegram"' in body

    @pytest.mark.asyncio
    async def test_full_status_telegram_error(self, health_server, mock_db):
        """Test full status with Telegram API error."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = '123:ABC'
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('aiohttp.ClientSession') as mock_session_cls:
                mock_resp = AsyncMock()
                mock_resp.status = 401

                mock_cm = AsyncMock()
                mock_cm.__aenter__.return_value = mock_resp

                mock_client = MagicMock()
                mock_client.get.return_value = mock_cm
                mock_client.__aenter__ = AsyncMock(return_value=mock_client)
                mock_client.__aexit__ = AsyncMock()
                mock_session_cls.return_value = mock_client

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"telegram"' in body
                assert b'"http_status": 401' in body

    @pytest.mark.asyncio
    async def test_full_status_telegram_exception(self, health_server, mock_db):
        """Test full status with Telegram API exception."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = '123:ABC'
            settings.encryption_key = None
            mock_settings.return_value = settings

            with patch('aiohttp.ClientSession') as mock_session_cls:
                mock_session_cls.side_effect = Exception("Network error")

                request = make_mocked_request('GET', '/status')
                response = await health_server.full_status(request)

                assert response.status == 200
                body = response.body
                assert b'"telegram"' in body
                assert b'"error"' in body

    @pytest.mark.asyncio
    async def test_full_status_encryption_key_valid(self, health_server, mock_db):
        """Test full status with valid encryption key."""
        import base64
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        valid_key = base64.b64encode(b'x' * 32).decode()

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = None
            settings.encryption_key = valid_key
            mock_settings.return_value = settings

            request = make_mocked_request('GET', '/status')
            response = await health_server.full_status(request)

            assert response.status == 200
            body = response.body
            assert b'"encryption"' in body
            assert b'"key_length": 256' in body

    @pytest.mark.asyncio
    async def test_full_status_encryption_key_wrong_length(self, health_server, mock_db):
        """Test full status with wrong length encryption key."""
        import base64
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        short_key = base64.b64encode(b'x' * 16).decode()

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = None
            settings.encryption_key = short_key
            mock_settings.return_value = settings

            request = make_mocked_request('GET', '/status')
            response = await health_server.full_status(request)

            assert response.status == 200
            body = response.body
            assert b'"encryption"' in body
            assert b'"warning"' in body

    @pytest.mark.asyncio
    async def test_full_status_encryption_key_invalid(self, health_server, mock_db):
        """Test full status with invalid encryption key."""
        mock_session = MagicMock()
        mock_session.__enter__ = MagicMock(return_value=mock_session)
        mock_session.__exit__ = MagicMock(return_value=None)
        mock_session.exec = MagicMock(return_value=[])
        mock_db.session = MagicMock(return_value=mock_session)

        with patch('bot.health.get_settings') as mock_settings:
            settings = MagicMock()
            settings.environment = 'test'
            settings.monero_rpc_url = None
            settings.telegram_token = None
            settings.encryption_key = 'not-valid-base64!!!'
            mock_settings.return_value = settings

            request = make_mocked_request('GET', '/status')
            response = await health_server.full_status(request)

            assert response.status == 200
            body = response.body
            assert b'"encryption"' in body
            assert b'"error"' in body