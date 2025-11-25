"""Tests for logging configuration module."""

import logging
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

from bot.logging_config import setup_logging


class TestLoggingConfig:
    """Test logging configuration functionality."""

    def test_setup_logging_basic(self):
        """Test basic logging setup."""
        # Clear existing handlers
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        setup_logging()
        
        # Check root logger configuration
        assert root_logger.level == logging.INFO
        assert len(root_logger.handlers) == 1
        assert isinstance(root_logger.handlers[0], logging.StreamHandler)

    def test_setup_logging_with_debug_level(self):
        """Test logging setup with DEBUG level."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        setup_logging(log_level="DEBUG")
        
        assert root_logger.level == logging.DEBUG

    def test_setup_logging_with_file(self, tmp_path):
        """Test logging setup with file handler."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        log_file = tmp_path / "test.log"
        setup_logging(log_file=str(log_file))
        
        # Should have both console and file handlers
        assert len(root_logger.handlers) == 2
        
        # Find file handler
        file_handler = None
        for handler in root_logger.handlers:
            if isinstance(handler, logging.handlers.RotatingFileHandler):
                file_handler = handler
                break
        
        assert file_handler is not None
        assert file_handler.maxBytes == 10 * 1024 * 1024  # 10MB
        assert file_handler.backupCount == 5

    def test_setup_logging_creates_log_directory(self, tmp_path):
        """Test that log directory is created if it doesn't exist."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        log_dir = tmp_path / "logs"
        log_file = log_dir / "test.log"
        
        assert not log_dir.exists()
        
        setup_logging(log_file=str(log_file))
        
        assert log_dir.exists()

    def test_setup_logging_external_loggers(self):
        """Test that external library loggers are configured."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        setup_logging()
        
        # Check external logger levels
        assert logging.getLogger("httpx").level == logging.WARNING
        assert logging.getLogger("telegram").level == logging.WARNING
        assert logging.getLogger("sqlalchemy").level == logging.WARNING

    def test_setup_logging_formatter(self):
        """Test that formatter is properly configured."""
        root_logger = logging.getLogger()
        root_logger.handlers.clear()
        
        setup_logging()
        
        handler = root_logger.handlers[0]
        formatter = handler.formatter
        
        # Test formatter format
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None
        )
        
        formatted = formatter.format(record)
        assert "test" in formatted
        assert "INFO" in formatted
        assert "Test message" in formatted