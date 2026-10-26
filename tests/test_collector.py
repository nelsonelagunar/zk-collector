"""
Unit tests for AttendanceCollector module
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest

from src.core.collector import AttendanceCollector
from src.core.config import Config


class TestAttendanceCollector:
    """Tests for AttendanceCollector class"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config"""
        # We'll create a minimal config object using mocking
        config = Mock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            "buffer.db_path": str(tmp_path / "buffer.db"),
            "buffer.max_records": 1000,
            "platform.url": "https://api.example.com",
            "platform.api_key": "test-key",
            "platform.tenant_id": "test-tenant",
            "platform.timeout": 30,
            "platform.retry_attempts": 3,
            "health.heartbeat_interval": 300,
            "poll_interval_seconds": 300,
            "sync_interval_seconds": 60,
            "devices": [
                {
                    "ip": "192.168.1.100",
                    "port": 4370,
                    "timeout": 5,
                    "password": 0,
                    "enabled": True,
                    "name": "Device1",
                },
                {
                    "ip": "192.168.1.101",
                    "port": 4370,
                    "timeout": 5,
                    "password": 0,
                    "enabled": True,
                    "name": "Device2",
                },
            ],
        }.get(key, default)
        return config

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_init(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, tmp_path
    ):
        """Test AttendanceCollector initialization"""
        collector = AttendanceCollector(mock_config)

        assert collector.config == mock_config
        assert collector.running is False
        assert collector.poll_interval == 300
        assert collector.sync_interval == 60
        assert len(collector.devices_config) == 2
        mock_buffer.assert_called_once()
        mock_platform.assert_called_once()
        mock_health.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_initialize_devices(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, caplog
    ):
        """Test device initialization"""
        collector = AttendanceCollector(mock_config)

        with caplog.at_level(logging.INFO):
            collector._initialize_devices()

        # Should create ZKClient for each enabled device
        assert mock_zk_client.call_count == 2
        assert len(collector.zk_clients) == 2
        assert "192.168.1.100" in collector.zk_clients
        assert "192.168.1.101" in collector.zk_clients

        # Check log messages
        assert "Dispositivo configurado: 192.168.1.100" in caplog.text
        assert "Dispositivo configurado: 192.168.1.101" in caplog.text

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_initialize_devices_skips_disabled(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, caplog
    ):
        """Test disabled devices are skipped"""

        # Modify config to have one disabled device
        # Need to override the side_effect for 'devices' key specifically
        def get_side_effect(key, default=None):
            if key == "devices":
                return [
                    {
                        "ip": "192.168.1.100",
                        "port": 4370,
                        "timeout": 5,
                        "password": 0,
                        "enabled": True,
                        "name": "Device1",
                    },
                    {
                        "ip": "192.168.1.101",
                        "port": 4370,
                        "timeout": 5,
                        "password": 0,
                        "enabled": False,
                        "name": "Device2",
                    },
                ]
            return {
                "buffer.db_path": "/tmp/buffer.db",
                "buffer.max_records": 1000,
                "platform.url": "https://api.example.com",
                "platform.api_key": "test-key",
                "platform.tenant_id": "test-tenant",
                "platform.timeout": 30,
                "platform.retry_attempts": 3,
                "health.heartbeat_interval": 300,
                "poll_interval_seconds": 300,
                "sync_interval_seconds": 60,
            }.get(key, default)

        mock_config.get.side_effect = get_side_effect

        collector = AttendanceCollector(mock_config)

        with caplog.at_level(logging.INFO):
            collector._initialize_devices()

        # ZKClient is called for each device, but disabled ones are skipped
        # The mock is called twice because it's called during init for both
        # Actually it's called during _initialize_devices, so should be 1
        assert mock_zk_client.call_count == 1
        assert len(collector.zk_clients) == 1
        assert "192.168.1.100" in collector.zk_clients
        assert "Dispositivo deshabilitado: 192.168.1.101" in caplog.text

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_poll_devices_success(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test successful device polling"""
        collector = AttendanceCollector(mock_config)

        # Setup mock ZK clients
        mock_client1 = Mock()
        mock_client1.connect.return_value = True
        mock_client1.get_attendance.return_value = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        mock_client1.disconnect.return_value = None

        mock_client2 = Mock()
        mock_client2.connect.return_value = True
        mock_client2.get_attendance.return_value = []
        mock_client2.disconnect.return_value = None

        collector.zk_clients = {"192.168.1.100": mock_client1, "192.168.1.101": mock_client2}
        collector.buffer = Mock()

        collector.poll_devices()

        # Verify calls
        mock_client1.connect.assert_called_once_with(max_retries=3, retry_delay=2.0)
        mock_client1.get_attendance.assert_called_once_with(
            clear_after_read=False, disable_device=True, timezone=None
        )
        mock_client1.disconnect.assert_called_once()

        mock_client2.connect.assert_called_once()
        mock_client2.get_attendance.assert_called_once()
        mock_client2.disconnect.assert_called_once()

        # Buffer should be called with records from first device
        collector.buffer.add_records.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_poll_devices_connection_failure(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, caplog
    ):
        """Test polling handles connection failures"""
        collector = AttendanceCollector(mock_config)

        mock_client = Mock()
        mock_client.connect.return_value = False
        collector.zk_clients = {"192.168.1.100": mock_client}
        collector.buffer = Mock()

        with caplog.at_level(logging.ERROR):
            collector.poll_devices()

        assert "No se pudo conectar a 192.168.1.100" in caplog.text
        collector.buffer.add_records.assert_not_called()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_poll_devices_exception_handling(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config, caplog
    ):
        """Test polling handles exceptions"""
        collector = AttendanceCollector(mock_config)

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.side_effect = Exception("Device error")
        mock_client.disconnect.return_value = None
        mock_client.connected = True

        collector.zk_clients = {"192.168.1.100": mock_client}
        collector.buffer = Mock()

        with caplog.at_level(logging.ERROR):
            collector.poll_devices()

        assert "Error polling 192.168.1.100" in caplog.text
        mock_client.disconnect.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_sync_to_platform_no_records(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test sync with no unsynced records"""
        collector = AttendanceCollector(mock_config)
        collector.buffer = Mock()
        collector.buffer.get_unsynced_records.return_value = []
        collector.platform_sync = Mock()

        collector.sync_to_platform()

        collector.buffer.get_unsynced_records.assert_called_once_with(limit=1000)
        collector.buffer.log_sync.assert_called_once_with(0, 0, "success", duration_seconds=0)
        collector.platform_sync.sync_attendance.assert_not_called()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_sync_to_platform_success(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test successful sync"""
        collector = AttendanceCollector(mock_config)

        unsynced_records = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            },
            {
                "id": 2,
                "user_id": "2",
                "timestamp": "2026-01-01 09:00:00",
                "status": 1,
                "device_ip": "192.168.1.100",
            },
        ]

        collector.buffer = Mock()
        collector.buffer.get_unsynced_records.return_value = unsynced_records
        collector.platform_sync = Mock()
        collector.platform_sync.sync_attendance.return_value = True

        collector.sync_to_platform()

        collector.platform_sync.sync_attendance.assert_called_once_with(unsynced_records)
        collector.buffer.mark_as_synced.assert_called_once_with([1, 2])
        collector.buffer.log_sync.assert_called_once()
        call_args = collector.buffer.log_sync.call_args
        assert call_args[1]["records_synced"] == 2
        assert call_args[1]["records_failed"] == 0
        assert call_args[1]["status"] == "success"

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_sync_to_platform_failure(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test sync failure handling"""
        collector = AttendanceCollector(mock_config)

        unsynced_records = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            },
        ]

        collector.buffer = Mock()
        collector.buffer.get_unsynced_records.return_value = unsynced_records
        collector.platform_sync = Mock()
        collector.platform_sync.sync_attendance.return_value = False

        collector.sync_to_platform()

        collector.buffer.mark_sync_failed.assert_called_once_with([1])
        collector.buffer.log_sync.assert_called_once()
        call_args = collector.buffer.log_sync.call_args
        assert call_args[1]["records_synced"] == 0
        assert call_args[1]["records_failed"] == 1
        assert call_args[1]["status"] == "failed"
        assert call_args[1]["error_message"] == "Platform error"

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_should_run_first_time(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test _should_run returns True when last_run is None"""
        collector = AttendanceCollector(mock_config)
        assert collector._should_run(None, 300) is True

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_should_run_interval_not_elapsed(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test _should_run returns False when interval not elapsed"""
        collector = AttendanceCollector(mock_config)
        last_run = datetime.now() - timedelta(seconds=100)
        assert collector._should_run(last_run, 300) is False

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_should_run_interval_elapsed(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test _should_run returns True when interval elapsed"""
        collector = AttendanceCollector(mock_config)
        last_run = datetime.now() - timedelta(seconds=400)
        assert collector._should_run(last_run, 300) is True

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_stop(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test stop method"""
        collector = AttendanceCollector(mock_config)
        collector.running = True

        mock_client1 = Mock()
        mock_client1.connected = True
        mock_client1.disconnect = Mock()

        mock_client2 = Mock()
        mock_client2.connected = False

        collector.zk_clients = {"192.168.1.100": mock_client1, "192.168.1.101": mock_client2}
        collector.health_monitor = Mock()

        collector.stop()

        assert collector.running is False
        collector.health_monitor.stop.assert_called_once()
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_not_called()


class TestCollectorIntegration:
    """Integration-style tests for collector"""

    @pytest.fixture
    def mock_config(self, tmp_path):
        """Create a mock config"""
        config = Mock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            "buffer.db_path": str(tmp_path / "buffer.db"),
            "buffer.max_records": 1000,
            "platform.url": "https://api.example.com",
            "platform.api_key": "test-key",
            "platform.tenant_id": "test-tenant",
            "platform.timeout": 30,
            "platform.retry_attempts": 3,
            "health.heartbeat_interval": 300,
            "poll_interval_seconds": 300,
            "sync_interval_seconds": 60,
            "devices": [
                {
                    "ip": "192.168.1.100",
                    "port": 4370,
                    "timeout": 5,
                    "password": 0,
                    "enabled": True,
                    "name": "Device1",
                },
            ],
        }.get(key, default)
        return config

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.ZKClient")
    def test_full_poll_and_sync_cycle(
        self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test complete poll and sync cycle"""
        collector = AttendanceCollector(mock_config)

        # Setup mocks
        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        mock_client.disconnect.return_value = None

        collector.zk_clients = {"192.168.1.100": mock_client}
        collector.buffer = Mock()
        collector.buffer.get_unsynced_records.return_value = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-01-01 08:00:00",
                "status": 0,
                "device_ip": "192.168.1.100",
            }
        ]
        collector.platform_sync = Mock()
        collector.platform_sync.sync_attendance.return_value = True

        # Run poll
        collector.poll_devices()
        assert collector.last_poll is not None

        # Run sync
        collector.sync_to_platform()
        assert collector.last_sync is not None

        # Verify both operations completed
        mock_client.connect.assert_called()
        collector.buffer.add_records.assert_called()
        collector.platform_sync.sync_attendance.assert_called()
        collector.buffer.mark_as_synced.assert_called()
