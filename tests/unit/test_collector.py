"""
Unit tests for AttendanceCollector
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.buffer.repository import BufferRepository
from src.core.collector import AttendanceCollector
from src.core.config import Config
from src.zk.attendance import AttendanceRecord


class TestAttendanceCollector:
    """Tests for AttendanceCollector"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = Mock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            'platform.url': 'http://test-platform:8000',
            'platform.api_key': 'test-key',
            'platform.tenant_id': 'test-tenant',
            'platform.timeout': 30,
            'platform.retry_attempts': 3,
            'buffer.db_path': '/tmp/test_buffer.db',
            'buffer.max_records': 1000,
            'poll_interval_seconds': 1,
            'sync_interval_seconds': 1,
            'health.heartbeat_interval': 300,
            'devices': [
                {
                    'ip': '192.168.1.101',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'enabled': True,
                    'name': 'Device 1',
                },
                {
                    'ip': '192.168.1.102',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'enabled': True,
                    'name': 'Device 2',
                },
            ]
        }.get(key, default)
        return config

    @pytest.fixture
    def temp_db(self, tmp_path):
        return tmp_path / "test_collector.db"

    @pytest.fixture
    def buffer_repo(self, temp_db):
        return BufferRepository(temp_db, max_records=1000)

    def test_init(self, mock_config):
        """Test collector initialization"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer,
            patch('src.core.collector.PlatformSync') as mock_sync,
            patch('src.core.collector.HealthMonitor') as mock_health,
        ):
            collector = AttendanceCollector(mock_config)

            assert collector.config == mock_config
            assert collector.running is False
            assert collector.poll_interval == 1
            assert collector.sync_interval == 1
            assert len(collector.devices_config) == 2
            mock_buffer.assert_called_once()
            mock_sync.assert_called_once()
            mock_health.assert_called_once()

    def test_initialize_devices(self, mock_config):
        """Test device initialization"""
        with (
            patch('src.core.collector.BufferRepository'),
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
            patch('src.core.collector.ZKClient') as mock_zk_client,
        ):
            mock_client = Mock()
            mock_zk_client.return_value = mock_client

            collector = AttendanceCollector(mock_config)
            collector._initialize_devices()

            assert len(collector.zk_clients) == 2
            assert '192.168.1.101' in collector.zk_clients
            assert '192.168.1.102' in collector.zk_clients
            assert mock_zk_client.call_count == 2

    def test_initialize_devices_skips_disabled(self, mock_config):
        """Test that disabled devices are skipped"""
        mock_config.get.side_effect = lambda key, default=None: {
            'platform.url': 'http://test-platform:8000',
            'platform.api_key': 'test-key',
            'platform.tenant_id': 'test-tenant',
            'platform.timeout': 30,
            'platform.retry_attempts': 3,
            'buffer.db_path': '/tmp/test_buffer.db',
            'buffer.max_records': 1000,
            'poll_interval_seconds': 1,
            'sync_interval_seconds': 1,
            'health.heartbeat_interval': 300,
            'devices': [
                {
                    'ip': '192.168.1.101',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'enabled': True,
                },
                {
                    'ip': '192.168.1.102',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'enabled': False,
                },
            ]
        }.get(key, default)

        with (
            patch('src.core.collector.BufferRepository'),
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
            patch('src.core.collector.ZKClient'),
        ):
            collector = AttendanceCollector(mock_config)
            collector._initialize_devices()

            assert len(collector.zk_clients) == 1
            assert '192.168.1.101' in collector.zk_clients
            assert '192.168.1.102' not in collector.zk_clients

    def test_should_run(self, mock_config):
        """Test _should_run logic"""
        with (
            patch('src.core.collector.BufferRepository'),
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
        ):
            collector = AttendanceCollector(mock_config)

            # Never run before
            assert collector._should_run(None, 300) is True

            # Just ran
            collector.last_poll = datetime.now()
            assert collector._should_run(collector.last_poll, 300) is False

            # Enough time passed
            collector.last_poll = datetime.now()
            # Manually set to old time
            from datetime import timedelta
            collector.last_poll = datetime.now() - timedelta(seconds=301)
            assert collector._should_run(collector.last_poll, 300) is True

    def test_poll_devices_success(self, mock_config):
        """Test successful device polling"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer_class.return_value = mock_buffer

            mock_client = Mock()
            mock_client.connect.return_value = True
            mock_client.get_attendance.return_value = [
                AttendanceRecord(
                    user_id="1",
                    timestamp=datetime.now(),
                    status=0,
                    device_ip="192.168.1.101",
                )
            ]

            collector = AttendanceCollector(mock_config)
            collector.zk_clients = {'192.168.1.101': mock_client}

            collector.poll_devices()

            mock_client.connect.assert_called_once_with(max_retries=3, retry_delay=2.0)
            mock_client.get_attendance.assert_called_once()
            mock_client.disconnect.assert_called_once()
            mock_buffer.add_records.assert_called_once()

    def test_poll_devices_connection_failure(self, mock_config):
        """Test device polling with connection failure"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer_class.return_value = mock_buffer

            mock_client = Mock()
            mock_client.connect.return_value = False

            collector = AttendanceCollector(mock_config)
            collector.zk_clients = {'192.168.1.101': mock_client}

            collector.poll_devices()

            mock_client.connect.assert_called_once()
            mock_client.get_attendance.assert_not_called()
            mock_buffer.add_records.assert_not_called()

    def test_poll_devices_exception_handling(self, mock_config):
        """Test device polling handles exceptions"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer_class.return_value = mock_buffer

            mock_client = Mock()
            mock_client.connect.side_effect = Exception("Connection error")

            collector = AttendanceCollector(mock_config)
            collector.zk_clients = {'192.168.1.101': mock_client}

            collector.poll_devices()

            mock_client.connect.assert_called_once()
            # Should still try to disconnect on error
            mock_client.disconnect.assert_called_once()

    def test_sync_to_platform_success(self, mock_config):
        """Test successful sync to platform"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync') as mock_sync_class,
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer.get_unsynced_records.return_value = [
                {
                    'id': 1,
                    'user_id': '1',
                    'timestamp': '2026-03-03T08:00:00',
                    'status': 0,
                    'device_ip': '192.168.1.101',
                    'punch_type': 'entrada',
                },
                {
                    'id': 2,
                    'user_id': '2',
                    'timestamp': '2026-03-03T17:00:00',
                    'status': 1,
                    'device_ip': '192.168.1.101',
                    'punch_type': 'salida',
                },
            ]
            mock_buffer_class.return_value = mock_buffer

            mock_sync = Mock()
            mock_sync.sync_attendance.return_value = True
            mock_sync_class.return_value = mock_sync

            collector = AttendanceCollector(mock_config)
            collector.buffer = mock_buffer
            collector.platform_sync = mock_sync

            collector.sync_to_platform()

            mock_sync.sync_attendance.assert_called_once()
            mock_buffer.mark_as_synced.assert_called_once()
            mock_buffer.log_sync.assert_called_once()

    def test_sync_to_platform_failure(self, mock_config):
        """Test sync to platform failure"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync') as mock_sync_class,
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer.get_unsynced_records.return_value = [
                {
                    'id': 1,
                    'user_id': '1',
                    'timestamp': '2026-03-03T08:00:00',
                    'status': 0,
                    'device_ip': '192.168.1.101',
                    'punch_type': 'entrada',
                },
            ]
            mock_buffer_class.return_value = mock_buffer

            mock_sync = Mock()
            mock_sync.sync_attendance.return_value = False
            mock_sync_class.return_value = mock_sync

            collector = AttendanceCollector(mock_config)
            collector.buffer = mock_buffer
            collector.platform_sync = mock_sync

            collector.sync_to_platform()

            mock_sync.sync_attendance.assert_called_once()
            mock_buffer.mark_sync_failed.assert_called_once()
            mock_buffer.log_sync.assert_called_once()

    def test_sync_to_platform_no_records(self, mock_config):
        """Test sync when no records to sync"""
        with (
            patch('src.core.collector.BufferRepository') as mock_buffer_class,
            patch('src.core.collector.PlatformSync') as mock_sync_class,
            patch('src.core.collector.HealthMonitor'),
        ):
            mock_buffer = Mock()
            mock_buffer.get_unsynced_records.return_value = []
            mock_buffer_class.return_value = mock_buffer

            mock_sync = Mock()
            mock_sync_class.return_value = mock_sync

            collector = AttendanceCollector(mock_config)
            collector.buffer = mock_buffer
            collector.platform_sync = mock_sync

            collector.sync_to_platform()

            mock_sync.sync_attendance.assert_not_called()
            mock_buffer.log_sync.assert_called_once()
            # Check log_sync called with positional args: (0, 0, 'success', duration_seconds=0)
            call_args = mock_buffer.log_sync.call_args
            assert call_args[0][0] == 0  # records_synced
            assert call_args[0][1] == 0  # records_failed
            assert call_args[0][2] == 'success'  # status

    def test_stop(self, mock_config):
        """Test collector stop"""
        with (
            patch('src.core.collector.BufferRepository'),
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor') as mock_health_class,
        ):
            mock_health = Mock()
            mock_health_class.return_value = mock_health

            mock_client = Mock()
            mock_client.connected = True

            collector = AttendanceCollector(mock_config)
            collector.zk_clients = {'192.168.1.101': mock_client}
            collector.health_monitor = mock_health
            collector.running = True

            collector.stop()

            assert collector.running is False
            mock_health.stop.assert_called_once()
            mock_client.disconnect.assert_called_once()


class TestAttendanceCollectorRunLoop:
    """Tests for the collector run loop"""

    @pytest.fixture
    def mock_config(self):
        """Mock configuration"""
        config = Mock(spec=Config)
        config.get.side_effect = lambda key, default=None: {
            'platform.url': 'http://test-platform:8000',
            'platform.api_key': 'test-key',
            'platform.tenant_id': 'test-tenant',
            'platform.timeout': 30,
            'platform.retry_attempts': 3,
            'buffer.db_path': '/tmp/test_buffer.db',
            'buffer.max_records': 1000,
            'poll_interval_seconds': 1,
            'sync_interval_seconds': 1,
            'health.heartbeat_interval': 300,
            'devices': [
                {
                    'ip': '192.168.1.101',
                    'port': 4370,
                    'timeout': 5,
                    'password': 0,
                    'enabled': True,
                    'name': 'Device 1',
                },
            ]
        }.get(key, default)
        return config

    def test_run_loop_exits_on_keyboard_interrupt(self, mock_config):
        """Test run loop handles KeyboardInterrupt"""
        with (
            patch('src.core.collector.BufferRepository'),
            patch('src.core.collector.PlatformSync'),
            patch('src.core.collector.HealthMonitor'),
        ):
            collector = AttendanceCollector(mock_config)
            collector.running = True

            # Mock _should_run to return True once then raise KeyboardInterrupt
            call_count = [0]
            def mock_should_run(last, interval):
                call_count[0] += 1
                if call_count[0] == 1:
                    return True
                raise KeyboardInterrupt()

            collector._should_run = mock_should_run
            collector.poll_devices = Mock()
            collector.sync_to_platform = Mock()
            collector.stop = Mock()

            # run() catches KeyboardInterrupt internally, so we just verify stop is called
            collector.run()

            collector.stop.assert_called_once()
