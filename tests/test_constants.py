"""
Unit tests for constants module
"""
import pytest

from src.core import constants


class TestConstants:
    """Tests for constants module"""

    def test_version_constant(self):
        """Test VERSION is defined and is a string"""
        assert hasattr(constants, 'VERSION')
        assert isinstance(constants.VERSION, str)
        assert len(constants.VERSION) > 0

    def test_timeout_constants(self):
        """Test timeout constants"""
        assert hasattr(constants, 'DEFAULT_TIMEOUT')
        assert constants.DEFAULT_TIMEOUT == 30
        assert hasattr(constants, 'ZK_DEFAULT_TIMEOUT')
        assert constants.ZK_DEFAULT_TIMEOUT == 5
        assert hasattr(constants, 'ZK_DEFAULT_PORT')
        assert constants.ZK_DEFAULT_PORT == 4370

    def test_interval_constants(self):
        """Test interval constants"""
        assert hasattr(constants, 'DEFAULT_POLL_INTERVAL')
        assert constants.DEFAULT_POLL_INTERVAL == 300
        assert hasattr(constants, 'DEFAULT_SYNC_INTERVAL')
        assert constants.DEFAULT_SYNC_INTERVAL == 60
        assert hasattr(constants, 'DEFAULT_HEARTBEAT_INTERVAL')
        assert constants.DEFAULT_HEARTBEAT_INTERVAL == 300
        assert hasattr(constants, 'DEFAULT_UPDATE_CHECK_INTERVAL')
        assert constants.DEFAULT_UPDATE_CHECK_INTERVAL == 86400

    def test_buffer_constants(self):
        """Test buffer constants"""
        assert hasattr(constants, 'DEFAULT_MAX_RECORDS')
        assert constants.DEFAULT_MAX_RECORDS == 10000
        assert hasattr(constants, 'DEFAULT_CLEANUP_DAYS')
        assert constants.DEFAULT_CLEANUP_DAYS == 30

    def test_retry_constants(self):
        """Test retry constants"""
        assert hasattr(constants, 'MAX_RETRIES')
        assert constants.MAX_RETRIES == 3
        assert hasattr(constants, 'RETRY_DELAY')
        assert constants.RETRY_DELAY == 2.0
        assert hasattr(constants, 'SYNC_MAX_RETRIES')
        assert constants.SYNC_MAX_RETRIES == 5

    def test_logging_constants(self):
        """Test logging constants"""
        assert hasattr(constants, 'DEFAULT_LOG_LEVEL')
        assert constants.DEFAULT_LOG_LEVEL == "INFO"
        assert hasattr(constants, 'DEFAULT_LOG_FORMAT')
        assert constants.DEFAULT_LOG_FORMAT == "text"
        assert hasattr(constants, 'DEFAULT_LOG_MAX_SIZE_MB')
        assert constants.DEFAULT_LOG_MAX_SIZE_MB == 10
        assert hasattr(constants, 'DEFAULT_LOG_BACKUP_COUNT')
        assert constants.DEFAULT_LOG_BACKUP_COUNT == 5

    def test_path_constants(self):
        """Test path constants"""
        assert hasattr(constants, 'DEFAULT_CONFIG_PATH')
        assert constants.DEFAULT_CONFIG_PATH == "/etc/attendance/collector.yaml"
        assert hasattr(constants, 'DEFAULT_DATA_DIR')
        assert constants.DEFAULT_DATA_DIR == "/opt/attendance/data"
        assert hasattr(constants, 'DEFAULT_LOG_DIR')
        assert constants.DEFAULT_LOG_DIR == "/var/log/attendance"
        assert hasattr(constants, 'DEFAULT_APP_DIR')
        assert constants.DEFAULT_APP_DIR == "/opt/attendance"

    def test_security_constants(self):
        """Test security constants"""
        assert hasattr(constants, 'ENCRYPTION_ALGORITHM')
        assert constants.ENCRYPTION_ALGORITHM == "AES-256"

    def test_http_constants(self):
        """Test HTTP constants"""
        assert hasattr(constants, 'HTTP_TIMEOUT')
        assert constants.HTTP_TIMEOUT == 30
        assert hasattr(constants, 'HTTP_RETRY_ATTEMPTS')
        assert constants.HTTP_RETRY_ATTEMPTS == 3