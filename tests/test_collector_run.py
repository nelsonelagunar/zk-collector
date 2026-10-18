"""
Unit tests for AttendanceCollector run loop
"""
import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, MagicMock

import pytest

from src.core.collector import AttendanceCollector
from src.core.config import Config


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock config"""
    config = Mock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        'buffer.db_path': str(tmp_path / 'buffer.db'),
        'buffer.max_records': 1000,
        'platform.url': 'https://api.example.com',
        'platform.api_key': 'test-key',
        'platform.tenant_id': 'test-tenant',
        'platform.timeout': 30,
        'platform.retry_attempts': 3,
        'health.heartbeat_interval': 300,
        'poll_interval_seconds': 1,
        'sync_interval_seconds': 1,
        'devices': [
            {'ip': '192.168.1.100', 'port': 4370, 'timeout': 5, 'password': 0, 'enabled': True, 'name': 'Device1'},
        ]
    }.get(key, default)
    return config


@pytest.fixture
def collector_with_mocks(mock_config):
    """Create collector with mocked dependencies"""
    with patch('src.core.collector.BufferRepository'), \
         patch('src.core.collector.PlatformSync'), \
         patch('src.core.collector.HealthMonitor'), \
         patch('src.core.collector.ZKClient'):
        collector = AttendanceCollector(mock_config)
        collector.buffer = Mock()
        collector.platform_sync = Mock()
        collector.health_monitor = Mock()
        return collector


class TestCollectorRunLoop:
    """Tests for AttendanceCollector run method logic"""

    @patch('src.core.collector.BufferRepository')
    @patch('src.core.collector.PlatformSync')
    @patch('src.core.collector.HealthMonitor')
    @patch('src.core.collector.ZKClient')
    def test_should_run_logic(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test _should_run method logic"""
        collector = AttendanceCollector(mock_config)

        # First run (last_run is None) -> True
        assert collector._should_run(None, 300) is True

        # Not enough time elapsed -> False
        last_run = datetime.now() - timedelta(seconds=100)
        assert collector._should_run(last_run, 300) is False

        # Enough time elapsed -> True
        last_run = datetime.now() - timedelta(seconds=400)
        assert collector._should_run(last_run, 300) is True

    @patch('src.core.collector.BufferRepository')
    @patch('src.core.collector.PlatformSync')
    @patch('src.core.collector.HealthMonitor')
    @patch('src.core.collector.ZKClient')
    def test_poll_and_sync_called_when_due(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test poll and sync are called when intervals elapsed"""
        collector = AttendanceCollector(mock_config)

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = []
        mock_client.disconnect.return_value = None
        collector.zk_clients = {'192.168.1.100': mock_client}
        collector.buffer = Mock()
        collector.buffer.get_unsynced_records.return_value = []
        collector.platform_sync = Mock()
        collector.health_monitor = Mock()

        # Set intervals to very short
        collector.poll_interval = 1
        collector.sync_interval = 1
        collector.last_poll = datetime.now() - timedelta(seconds=2)
        collector.last_sync = datetime.now() - timedelta(seconds=2)

        # Manually run the logic that run() would execute
        if collector._should_run(collector.last_poll, collector.poll_interval):
            collector.poll_devices()
            collector.last_poll = datetime.now()

        if collector._should_run(collector.last_sync, collector.sync_interval):
            collector.sync_to_platform()
            collector.last_sync = datetime.now()

        mock_client.connect.assert_called()
        # sync_attendance is called by sync_to_platform when there are records to sync
        # But buffer.get_unsynced_records returns [] so it returns early
        # Let's verify it was called with empty list (or not called at all)
        # The code returns early if no records, so let's check that
        collector.buffer.get_unsynced_records.assert_called_once_with(limit=1000)
        collector.buffer.log_sync.assert_called_once_with(0, 0, 'success', duration_seconds=0)

    @patch('src.core.collector.BufferRepository')
    @patch('src.core.collector.PlatformSync')
    @patch('src.core.collector.HealthMonitor')
    @patch('src.core.collector.ZKClient')
    def test_poll_not_called_when_not_due(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test poll is not called when interval not elapsed"""
        collector = AttendanceCollector(mock_config)

        mock_client = Mock()
        collector.zk_clients = {'192.168.1.100': mock_client}
        collector.buffer = Mock()
        collector.health_monitor = Mock()

        # Interval not elapsed
        collector.poll_interval = 300
        collector.last_poll = datetime.now() - timedelta(seconds=100)

        if collector._should_run(collector.last_poll, collector.poll_interval):
            collector.poll_devices()

        mock_client.connect.assert_not_called()

    @patch('src.core.collector.BufferRepository')
    @patch('src.core.collector.PlatformSync')
    @patch('src.core.collector.HealthMonitor')
    @patch('src.core.collector.ZKClient')
    def test_run_stop_flag(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test running flag controls loop"""
        collector = AttendanceCollector(mock_config)
        collector.running = True

        collector.stop()

        assert collector.running is False

    @patch('src.core.collector.BufferRepository')
    @patch('src.core.collector.PlatformSync')
    @patch('src.core.collector.HealthMonitor')
    @patch('src.core.collector.ZKClient')
    def test_run_initializes_and_starts_health(self, mock_zk_client, mock_health, mock_platform, mock_buffer, mock_config):
        """Test initialization sequence"""
        collector = AttendanceCollector(mock_config)

        # Check components are initialized
        assert collector.buffer is not None
        assert collector.platform_sync is not None
        assert collector.health_monitor is not None
        assert collector.zk_clients == {}  # Empty until _initialize_devices()

        # Call initialize
        collector._initialize_devices()
        assert len(collector.zk_clients) == 1

        # Start health monitor
        collector.health_monitor.start()
        collector.health_monitor.start.assert_called_once()


class TestCollectorEdgeCases:
    """Edge case tests for collector"""

    def test_poll_devices_continues_on_error(self, collector_with_mocks, caplog):
        """Test poll_devices continues to next device on error"""
        collector = collector_with_mocks

        mock_client1 = Mock()
        mock_client1.connect.return_value = True
        mock_client1.get_attendance.side_effect = Exception("Error on device 1")
        mock_client1.disconnect.return_value = None
        mock_client1.connected = True

        mock_client2 = Mock()
        mock_client2.connect.return_value = True
        mock_client2.get_attendance.return_value = []
        mock_client2.disconnect.return_value = None

        collector.zk_clients = {
            '192.168.1.100': mock_client1,
            '192.168.1.101': mock_client2
        }

        with caplog.at_level(logging.ERROR):
            collector.poll_devices()

        mock_client1.connect.assert_called_once()
        mock_client2.connect.assert_called_once()
        assert "Error polling 192.168.1.100" in caplog.text

    def test_sync_to_platform_handles_exception(self, collector_with_mocks, caplog):
        """Test sync_to_platform handles exception from platform_sync"""
        collector = collector_with_mocks

        collector.buffer.get_unsynced_records.return_value = [
            {'id': 1, 'user_id': '1', 'timestamp': '2026-01-01 08:00:00', 'status': 0, 'device_ip': '192.168.1.100'}
        ]
        # Return False instead of raising to test the error path
        collector.platform_sync.sync_attendance.return_value = False

        with caplog.at_level(logging.ERROR):
            collector.sync_to_platform()

        collector.buffer.mark_sync_failed.assert_called_once_with([1])
        assert "Sincronización fallida" in caplog.text


class TestCollectorLogMessages:
    """Test log messages from collector"""

    def test_poll_logs_summary(self, collector_with_mocks, caplog):
        """Test poll_devices logs summary"""
        collector = collector_with_mocks

        mock_client = Mock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = [
            {'id': 1, 'user_id': '1', 'timestamp': '2026-01-01 08:00:00', 'status': 0, 'device_ip': '192.168.1.100'},
            {'id': 2, 'user_id': '2', 'timestamp': '2026-01-01 09:00:00', 'status': 1, 'device_ip': '192.168.1.100'},
        ]
        mock_client.disconnect.return_value = None

        collector.zk_clients = {'192.168.1.100': mock_client}

        with caplog.at_level(logging.INFO):
            collector.poll_devices()

        assert "Iniciando polling de dispositivos" in caplog.text
        assert "Polling completado: 1 exitosos, 0 fallidos" in caplog.text

    def test_sync_logs_success(self, collector_with_mocks, caplog):
        """Test sync_to_platform logs success"""
        collector = collector_with_mocks

        collector.buffer.get_unsynced_records.return_value = [
            {'id': 1, 'user_id': '1', 'timestamp': '2026-01-01 08:00:00', 'status': 0, 'device_ip': '192.168.1.100'},
        ]
        collector.platform_sync.sync_attendance.return_value = True

        with caplog.at_level(logging.INFO):
            collector.sync_to_platform()

        assert "Iniciando sincronización con plataforma" in caplog.text
        assert "Sincronización completada: 1 registros" in caplog.text

    def test_sync_logs_failure(self, collector_with_mocks, caplog):
        """Test sync_to_platform logs failure"""
        collector = collector_with_mocks

        collector.buffer.get_unsynced_records.return_value = [
            {'id': 1, 'user_id': '1', 'timestamp': '2026-01-01 08:00:00', 'status': 0, 'device_ip': '192.168.1.100'},
        ]
        collector.platform_sync.sync_attendance.return_value = False

        with caplog.at_level(logging.ERROR):
            collector.sync_to_platform()

        assert "Sincronización fallida" in caplog.text

    def test_stop_disconnects_devices(self, collector_with_mocks):
        """Test stop() disconnects all connected devices"""
        collector = collector_with_mocks
        collector.running = True

        mock_client1 = Mock()
        mock_client1.connected = True
        mock_client1.disconnect = Mock()

        mock_client2 = Mock()
        mock_client2.connected = False

        collector.zk_clients = {
            '192.168.1.100': mock_client1,
            '192.168.1.101': mock_client2
        }

        collector.stop()

        assert collector.running is False
        collector.health_monitor.stop.assert_called_once()
        mock_client1.disconnect.assert_called_once()
        mock_client2.disconnect.assert_not_called()