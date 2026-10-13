"""
Unit tests for AttendanceCollector module
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.buffer.repository import BufferRepository
from src.core.collector import AttendanceCollector
from src.core.config import Config
from src.zk_client.attendance import AttendanceRecord
from src.zk_client.client import ZKClient


@pytest.fixture
def mock_config(tmp_path):
    """Create a mock Config object"""
    config = Mock(spec=Config)
    config.get.side_effect = lambda key, default=None: {
        "platform.url": "https://test.example.com",
        "platform.api_key": "test-api-key",
        "platform.tenant_id": "test-tenant-id",
        "platform.timeout": 30,
        "platform.retry_attempts": 3,
        "poll_interval_seconds": 60,
        "sync_interval_seconds": 10,
        "buffer.max_records": 1000,
        "buffer.cleanup_days": 30,
        "buffer.db_path": str(tmp_path / "test_buffer.db"),
        "health.heartbeat_interval": 300,
        "devices": [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": "0",
                "name": "Test Device",
                "enabled": True,
            }
        ],
    }.get(key, default)
    return config


@pytest.fixture
def mock_zk_client():
    """Create a mock ZKClient"""
    client = Mock(spec=ZKClient)
    client.ip = "192.168.1.101"
    client.port = 4370
    client.connected = False
    client.connect.return_value = True
    client.disconnect.return_value = None
    client.get_attendance.return_value = []
    client.get_device_info.return_value = {
        "firmware_version": "6.60",
        "serial_number": "TEST123",
    }
    return client


@pytest.fixture
def mock_buffer_repo():
    """Create a mock BufferRepository"""
    buffer = Mock(spec=BufferRepository)
    buffer.add_records.return_value = 0
    buffer.get_unsynced_records.return_value = []
    buffer.mark_as_synced.return_value = 0
    buffer.mark_sync_failed.return_value = None
    buffer.log_sync.return_value = None
    buffer.get_stats.return_value = {
        "total_records": 0,
        "pending_sync": 0,
        "synced": 0,
        "oldest_pending": None,
        "newest_record": None,
        "max_records": 1000,
        "usage_percent": 0,
    }
    return buffer


@pytest.fixture
def mock_platform_sync():
    """Create a mock PlatformSync"""
    sync = Mock()
    sync.sync_attendance.return_value = True
    sync.send_heartbeat.return_value = True
    return sync


@pytest.fixture
def mock_health_monitor():
    """Create a mock HealthMonitor"""
    monitor = Mock()
    monitor.start.return_value = None
    monitor.stop.return_value = None
    return monitor


class TestAttendanceCollectorInit:
    """Tests for AttendanceCollector initialization"""

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_init(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test collector initialization"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_platform_instance = Mock()
        mock_platform.return_value = mock_platform_instance
        mock_health_instance = Mock()
        mock_health.return_value = mock_health_instance

        collector = AttendanceCollector(mock_config)

        assert collector.config == mock_config
        assert collector.running is False
        assert collector.poll_interval == 60
        assert collector.sync_interval == 10
        assert len(collector.zk_clients) == 0  # Not initialized yet
        assert collector.last_poll is None
        assert collector.last_sync is None

        # Verify components initialized
        mock_buffer.assert_called_once()
        mock_platform.assert_called_once()
        mock_health.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_init_with_custom_intervals(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test initialization with custom intervals"""
        mock_config.get.side_effect = lambda key, default=None: {
            "platform.url": "https://test.example.com",
            "platform.api_key": "key",
            "platform.tenant_id": "tenant",
            "poll_interval_seconds": 120,
            "sync_interval_seconds": 30,
            "buffer.max_records": 5000,
            "health.heartbeat_interval": 600,
            "devices": [],
        }.get(key, default)

        collector = AttendanceCollector(mock_config)

        assert collector.poll_interval == 120
        assert collector.sync_interval == 30


class TestInitializeDevices:
    """Tests for _initialize_devices method"""

    @patch("src.core.collector.ZKClient")
    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_initialize_devices_enabled(
        self, mock_health, mock_platform, mock_buffer, mock_zk_class, mock_config
    ):
        """Test initializing enabled devices"""
        mock_zk_instance = Mock()
        mock_zk_class.return_value = mock_zk_instance

        collector = AttendanceCollector(mock_config)
        collector._initialize_devices()

        assert len(collector.zk_clients) == 1
        assert "192.168.1.101" in collector.zk_clients
        mock_zk_class.assert_called_once_with(
            ip="192.168.1.101", port=4370, timeout=5, password="0"
        )

    @patch("src.core.collector.ZKClient")
    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_initialize_devices_disabled(
        self, mock_health, mock_platform, mock_buffer, mock_zk_class, mock_config
    ):
        """Test disabled devices are skipped"""

        def mock_get(key, default=None):
            if key == "devices":
                return [
                    {
                        "ip": "192.168.1.101",
                        "enabled": False,
                    },
                    {
                        "ip": "192.168.1.102",
                        "enabled": True,
                    },
                ]
            return default

        mock_config.get.side_effect = mock_get

        collector = AttendanceCollector(mock_config)
        collector._initialize_devices()

        assert len(collector.zk_clients) == 1
        assert "192.168.1.102" in collector.zk_clients
        assert "192.168.1.101" not in collector.zk_clients

    @patch("src.core.collector.ZKClient")
    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_initialize_devices_defaults(
        self, mock_health, mock_platform, mock_buffer, mock_zk_class, mock_config
    ):
        """Test device defaults are applied"""
        mock_config.get.return_value = [
            {
                "ip": "192.168.1.101",
                # No port, timeout, password - should use defaults
            }
        ]

        collector = AttendanceCollector(mock_config)
        collector._initialize_devices()

        mock_zk_class.assert_called_once_with(
            ip="192.168.1.101",
            port=4370,  # default
            timeout=5,  # default
            password="0",  # default
        )


class TestPollDevices:
    """Tests for poll_devices method"""

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_poll_devices_success(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test successful polling"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_buffer_instance.add_records.return_value = 2

        mock_zk = Mock()
        mock_zk.connect.return_value = True
        mock_zk.get_attendance.return_value = [
            AttendanceRecord(
                user_id="1", timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
            ),
            AttendanceRecord(
                user_id="2", timestamp=datetime.now(), status=1, device_ip="192.168.1.101"
            ),
        ]

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk}
        collector.buffer = mock_buffer_instance

        collector.poll_devices()

        assert collector.last_poll is not None
        mock_zk.connect.assert_called_once_with(max_retries=3, retry_delay=2.0)
        mock_zk.get_attendance.assert_called_once_with(clear_after_read=False, disable_device=True)
        mock_zk.disconnect.assert_called_once()
        mock_buffer_instance.add_records.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_poll_devices_connection_failure(
        self, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test polling handles connection failure"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance

        mock_zk = Mock()
        mock_zk.connect.return_value = False

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk}
        collector.buffer = mock_buffer_instance

        collector.poll_devices()

        assert collector.last_poll is not None
        mock_zk.connect.assert_called_once()
        mock_zk.get_attendance.assert_not_called()
        mock_zk.disconnect.assert_not_called()
        mock_buffer_instance.add_records.assert_not_called()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_poll_devices_no_records(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test polling when device returns no records"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance

        mock_zk = Mock()
        mock_zk.connect.return_value = True
        mock_zk.get_attendance.return_value = []

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk}
        collector.buffer = mock_buffer_instance

        collector.poll_devices()

        mock_buffer_instance.add_records.assert_not_called()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_poll_devices_exception_handling(
        self, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test polling handles exceptions gracefully"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance

        mock_zk = Mock()
        mock_zk.connect.return_value = True
        mock_zk.get_attendance.side_effect = Exception("ZK Error")

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk}
        collector.buffer = mock_buffer_instance

        collector.poll_devices()  # Should not raise

        mock_zk.disconnect.assert_called_once()
        mock_buffer_instance.add_records.assert_not_called()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.AttendanceCollector._load_devices_from_webgui_db")
    def test_poll_devices_multiple_devices(
        self, mock_load_devices, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test polling multiple devices"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_buffer_instance.add_records.return_value = 1

        mock_zk1 = Mock()
        mock_zk1.connect.return_value = True
        mock_zk1.get_attendance.return_value = [
            AttendanceRecord(
                user_id="1", timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
            )
        ]

        mock_zk2 = Mock()
        mock_zk2.connect.return_value = True
        mock_zk2.get_attendance.return_value = [
            AttendanceRecord(
                user_id="2", timestamp=datetime.now(), status=0, device_ip="192.168.1.102"
            )
        ]

        # Mock WebGUI DB to return two devices
        mock_load_devices.return_value = [
            {"ip": "192.168.1.101", "port": 4370, "timeout": 5, "password": "0", "name": "Device 1", "enabled": True},
            {"ip": "192.168.1.102", "port": 4370, "timeout": 5, "password": "0", "name": "Device 2", "enabled": True},
        ]

        # Mock ZKClient creation
        with patch("src.core.collector.ZKClient") as mock_zk_class:
            mock_zk_class.side_effect = [mock_zk1, mock_zk2]

            collector = AttendanceCollector(mock_config)
            collector.buffer = mock_buffer_instance

            collector.poll_devices()

            assert mock_zk1.connect.called
            assert mock_zk2.connect.called
            assert mock_buffer_instance.add_records.call_count == 2


class TestSyncToPlatform:
    """Tests for sync_to_platform method"""

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_sync_to_platform_success(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test successful sync to platform"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_buffer_instance.get_unsynced_records.return_value = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
                "punch_type": "entrada",
            },
            {
                "id": 2,
                "user_id": "2",
                "timestamp": "2026-03-03T17:00:00",
                "status": 1,
                "device_ip": "192.168.1.101",
                "punch_type": "salida",
            },
        ]

        mock_platform_instance = Mock()
        mock_platform.return_value = mock_platform_instance
        mock_platform_instance.sync_attendance.return_value = True

        collector = AttendanceCollector(mock_config)
        collector.buffer = mock_buffer_instance
        collector.platform_sync = mock_platform_instance

        collector.sync_to_platform()

        assert collector.last_sync is not None
        mock_buffer_instance.get_unsynced_records.assert_called_once_with(limit=1000)
        mock_platform_instance.sync_attendance.assert_called_once()
        mock_buffer_instance.mark_as_synced.assert_called_once_with([1, 2])
        mock_buffer_instance.log_sync.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_sync_to_platform_failure(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test sync handles platform failure"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_buffer_instance.get_unsynced_records.return_value = [
            {
                "id": 1,
                "user_id": "1",
                "timestamp": "2026-03-03T08:00:00",
                "status": 0,
                "device_ip": "192.168.1.101",
                "punch_type": "entrada",
            },
        ]

        mock_platform_instance = Mock()
        mock_platform.return_value = mock_platform_instance
        mock_platform_instance.sync_attendance.return_value = False

        collector = AttendanceCollector(mock_config)
        collector.buffer = mock_buffer_instance
        collector.platform_sync = mock_platform_instance

        collector.sync_to_platform()

        mock_platform_instance.sync_attendance.assert_called_once()
        mock_buffer_instance.mark_as_synced.assert_not_called()
        mock_buffer_instance.mark_sync_failed.assert_called_once_with([1])
        mock_buffer_instance.log_sync.assert_called_once()

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_sync_to_platform_no_pending(
        self, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test sync when no pending records"""
        mock_buffer_instance = Mock()
        mock_buffer.return_value = mock_buffer_instance
        mock_buffer_instance.get_unsynced_records.return_value = []

        collector = AttendanceCollector(mock_config)
        collector.buffer = mock_buffer_instance

        collector.sync_to_platform()

        mock_buffer_instance.get_unsynced_records.assert_called_once()
        # Should not call platform sync
        mock_platform.sync_attendance.assert_not_called()
        mock_buffer_instance.log_sync.assert_called_once_with(0, 0, "success", duration_seconds=0)


class TestShouldRun:
    """Tests for _should_run method"""

    def test_should_run_first_time(self, mock_config):
        """Test should_run returns True for first run"""
        collector = AttendanceCollector(mock_config)
        assert collector._should_run(None, 60) is True

    def test_should_run_elapsed(self, mock_config):
        """Test should_run returns True when interval elapsed"""
        collector = AttendanceCollector(mock_config)
        collector.last_poll = datetime.now()
        # Can't easily test elapsed time without time manipulation
        # Just verify the method exists and runs
        result = collector._should_run(collector.last_poll, 0)
        assert result is True

    def test_should_run_not_elapsed(self, mock_config):
        """Test should_run returns False when interval not elapsed"""
        collector = AttendanceCollector(mock_config)
        collector.last_poll = datetime.now()
        result = collector._should_run(collector.last_poll, 3600)  # 1 hour
        assert result is False


class TestStop:
    """Tests for stop method"""

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    def test_stop(self, mock_health, mock_platform, mock_buffer, mock_config):
        """Test stop cleans up properly"""
        mock_health_instance = Mock()
        mock_health.return_value = mock_health_instance

        mock_zk1 = Mock()
        mock_zk1.connected = True
        mock_zk2 = Mock()
        mock_zk2.connected = False

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk1, "192.168.1.102": mock_zk2}
        collector.health_monitor = mock_health_instance
        collector.running = True

        collector.stop()

        assert collector.running is False
        mock_health_instance.stop.assert_called_once()
        mock_zk1.disconnect.assert_called_once()
        mock_zk2.disconnect.assert_not_called()  # Not connected


class TestRunLoop:
    """Tests for run method (main loop)"""

    @patch("src.core.collector.BufferRepository")
    @patch("src.core.collector.PlatformSync")
    @patch("src.core.collector.HealthMonitor")
    @patch("src.core.collector.time.sleep")
    def test_run_single_iteration(
        self, mock_sleep, mock_health, mock_platform, mock_buffer, mock_config
    ):
        """Test run loop executes one iteration"""
        mock_buffer_instance = Mock()
        mock_buffer_instance.get_unsynced_records.return_value = []
        mock_buffer_instance.log_sync.return_value = None
        mock_buffer.return_value = mock_buffer_instance
        mock_health_instance = Mock()
        mock_health.return_value = mock_health_instance

        # Create a mock ZK client
        mock_zk = Mock()
        mock_zk.connect.return_value = True
        mock_zk.get_attendance.return_value = []

        collector = AttendanceCollector(mock_config)
        collector.zk_clients = {"192.168.1.101": mock_zk}
        collector.buffer = mock_buffer_instance
        collector.health_monitor = mock_health_instance

        # Make run loop exit after one iteration
        collector.running = True
        original_should_run = collector._should_run

        call_count = [0]

        def mock_should_run(last, interval):
            call_count[0] += 1
            if call_count[0] > 2:
                collector.running = False
            return original_should_run(last, interval)

        collector._should_run = mock_should_run

        collector.run()

        mock_health_instance.start.assert_called_once()
        mock_health_instance.stop.assert_called_once()
