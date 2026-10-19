"""
Unit tests for logging module
"""

import json
import logging

from src.utils.logging import JsonFormatter, setup_logging


class TestJsonFormatter:
    """Tests for JsonFormatter"""

    def test_format_basic_log_record(self):
        """Test formatting a basic log record"""
        formatter = JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S")
        record = logging.LogRecord(
            name="test_logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=10,
            msg="Test message",
            args=(),
            exc_info=None,
        )
        result = formatter.format(record)
        log_obj = json.loads(result)
        assert log_obj["logger"] == "test_logger"
        assert log_obj["level"] == "INFO"
        assert log_obj["message"] == "Test message"
        assert "timestamp" in log_obj

    def test_format_log_record_with_exception(self):
        """Test formatting a log record with exception info"""
        formatter = JsonFormatter(datefmt="%Y-%m-%d %H:%M:%S")
        try:
            raise ValueError("test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test_logger",
            level=logging.ERROR,
            pathname="test.py",
            lineno=10,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )
        result = formatter.format(record)
        log_obj = json.loads(result)
        assert log_obj["logger"] == "test_logger"
        assert log_obj["level"] == "ERROR"
        assert log_obj["message"] == "Error occurred"
        assert "exception" in log_obj
        assert "ValueError" in log_obj["exception"]
        assert "test error" in log_obj["exception"]


class TestSetupLogging:
    """Tests for setup_logging function"""

    def test_setup_logging_text_format(self, tmp_path):
        """Test setup_logging with text format"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, level=logging.DEBUG, log_format="text")

        assert logger.name == "attendance_collector"
        assert logger.level == logging.DEBUG
        assert len(logger.handlers) == 3  # console, file, error file

        # Check log files were created
        assert (log_dir / "collector.log").exists()
        assert (log_dir / "error.log").exists()

    def test_setup_logging_json_format(self, tmp_path):
        """Test setup_logging with JSON format"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, level=logging.INFO, log_format="json")

        assert logger.name == "attendance_collector"
        assert logger.level == logging.INFO
        # Should have handlers with JsonFormatter
        formatters = [h.formatter for h in logger.handlers if h.formatter]
        assert any(isinstance(f, JsonFormatter) for f in formatters)

    def test_setup_logging_creates_directory(self, tmp_path):
        """Test setup_logging creates log directory"""
        log_dir = tmp_path / "new_logs"
        assert not log_dir.exists()
        setup_logging(log_dir)
        assert log_dir.exists()

    def test_setup_logging_custom_parameters(self, tmp_path):
        """Test setup_logging with custom max_size and backup_count"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(
            log_dir, level=logging.WARNING, log_format="text", max_size_mb=5, backup_count=3
        )

        # Check rotating file handlers have correct settings
        file_handlers = [h for h in logger.handlers if hasattr(h, "maxBytes")]
        for handler in file_handlers:
            assert handler.maxBytes == 5 * 1024 * 1024
            assert handler.backupCount == 3

    def test_setup_logging_error_handler_level(self, tmp_path):
        """Test error handler only catches ERROR and above"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir, level=logging.DEBUG)

        error_handlers = [h for h in logger.handlers if h.level == logging.ERROR]
        assert len(error_handlers) == 1

    def test_setup_logging_returns_logger(self, tmp_path):
        """Test setup_logging returns the configured logger"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)
        assert isinstance(logger, logging.Logger)
        assert logger.name == "attendance_collector"

    def test_setup_logging_clears_existing_handlers(self, tmp_path):
        """Test setup_logging clears existing handlers"""
        log_dir = tmp_path / "logs"
        logger = setup_logging(log_dir)
        initial_handler_count = len(logger.handlers)

        # Call again - should clear and re-add
        logger2 = setup_logging(log_dir)
        assert logger2 is logger  # Same logger instance
        assert len(logger.handlers) == initial_handler_count

    def test_setup_logging_logs_info(self, tmp_path, caplog):
        """Test setup_logging logs initialization message"""
        log_dir = tmp_path / "logs"
        with caplog.at_level(logging.INFO):
            setup_logging(log_dir)
        assert "Logging configurado" in caplog.text
