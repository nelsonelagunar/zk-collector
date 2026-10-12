"""
Integration tests for AttendanceCollector with mocked ZK device
"""

import pytest
import time
from datetime import datetime
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from typing import List, Dict

from src.core.collector import AttendanceCollector
from src.core.config import Config
from src.zk.client import ZKClient
from src.zk.attendance import AttendanceRecord
from src.buffer.repository import BufferRepository
from src.buffer.models import AttendanceRecordDB
from src.sync.platform import PlatformSync


class MockZKDevice:
    """Mock ZK device for integration testing"""

    def __init__(self):
        self.connected = False
        self.attendance_records = []
        self.device_disabled = False

    def connect(self):
        self.connected = True

    def disconnect(self):
        self.connected = False

    def disable_device(self):
        self.device_disabled = True

    def enable_device(self):
        self.device_disabled = False

    def get_attendance(self):
        return self.attendance_records

    def clear_attendance(self):
        self.attendance_records = []

    def get_firmware_version(self):
        return "6.60"

    def get_serialnumber(self):
        return "TEST123456"

    def get_platform(self):
        return "ZKTECO"

    def get_device_name(self):
        return "Test Device"

    def get_mac(self):
        return "AA:BB:CC:DD:EE:FF"

    def get_users(self):
        return []

    def get_time(self):
        return datetime.now()

    def set_time(self, new_time):
        pass

    def restart(self):
        pass


def create_mock_zk_attendance(user_id: str, timestamp: datetime, status: int):
    """Create a mock ZK attendance record"""
    mock = Mock()
    mock.user_id = user_id
    mock.timestamp = timestamp
    mock.status = status
    return mock


@pytest.fixture
def mock_zk_class():
    """Fixture to mock the pyzk ZK class"""
    with patch('src.zk.client.ZK') as mock_zk:
        mock_device = MockZKDevice()
        mock_zk.return_value = mock_device
        yield mock_zk, mock_device


@pytest.fixture
def mock_platform_sync():
    """Fixture to mock PlatformSync"""
    with patch('src.core.collector.PlatformSync') as mock_sync_class:
        mock_sync = Mock(spec=PlatformSync)
        mock_sync.sync_attendance.return_value = True
        mock_sync_class.return_value = mock_sync
        yield mock_sync


@pytest.fixture
def temp_config_file(tmp_path):
    """Create a temporary config file for testing"""
    import yaml
    config_data = {
        'platform': {
            'url': 'https://test.example.com',
            'api_key': 'test-api-key',
            'tenant_id': 'test-tenant-id',
            'timeout': 30,
            'retry_attempts': 3,
        },
        'devices': [
            {
                'ip': '192.168.1.101',
                'port': 4370,
                'timeout': 5,
                'password': '0',
                'name': 'Test Device',
                'enabled': True,
            }
        ],
        'poll_interval_seconds': 60,
        'sync_interval_seconds': 10,
        'buffer': {
            'max_records': 1000,
            'cleanup_days': 30,
            'db_path': str(tmp_path / 'test_buffer.db')
        },
        'logging': {
            'level': 'DEBUG',
            'max_size_mb': 10,
            'backup_count': 5,
            'format': 'text'
        }
    }
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, 'w') as f:
        yaml.dump(config_data, f)
    return config_file


@pytest.fixture
def config(temp_config_file):
    """Config fixture"""
    return Config(temp_config_file)


@pytest.fixture
def buffer_repo(tmp_path):
    """BufferRepository fixture with temp DB"""
    db_path = tmp_path / "test_buffer.db"
    return BufferRepository(db_path, max_records=1000)


class TestCollectorIntegration:
    """Integration tests for AttendanceCollector"""

    def test_collector_initialization(self, config, mock_zk_class, mock_platform_sync):
        """Test collector initializes correctly with config"""
        mock_zk, mock_device = mock_zk_class

        collector = AttendanceCollector(config)

        assert collector.config == config
        assert len(collector.zk_clients) == 1
        assert '192.168.1.101' in collector.zk_clients
        assert collector.poll_interval == 60
        assert collector.sync_interval == 10

    def test_poll_devices_success(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test successful polling of devices"""
        mock_zk, mock_device = mock_zk_class

        # Setup mock attendance data
        mock_device.attendance_records = [
            create_mock_zk_attendance("1", datetime(2026, 3, 3, 8, 0, 0), 0),
            create_mock_zk_attendance("2", datetime(2026, 3, 3, 17, 0, 0), 1),
        ]

        collector = AttendanceCollector(config)
        # Replace buffer with test instance
        collector.buffer = buffer_repo

        # Poll devices
        collector.poll_devices()

        # Verify
        assert collector.last_poll is not None
        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 2
        assert stats['pending_sync'] == 2

        # Verify ZK device was used correctly
        mock_zk.assert_called()
        mock_device.connect.assert_called()
        mock_device.disable_device.assert_called()
        mock_device.get_attendance.assert_called()
        mock_device.enable_device.assert_called()
        mock_device.disconnect.assert_called()

    def test_poll_devices_no_records(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test polling when device has no records"""
        mock_zk, mock_device = mock_zk_class
        mock_device.attendance_records = []

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.poll_devices()

        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 0

    def test_poll_devices_connection_failure(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test polling handles connection failure gracefully"""
        mock_zk, mock_device = mock_zk_class
        mock_device.connect.side_effect = Exception("Connection refused")

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.poll_devices()

        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 0

    def test_poll_devices_zk_error(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test polling handles ZK protocol errors"""
        mock_zk, mock_device = mock_zk_class
        mock_device.get_attendance.side_effect = Exception("ZK Protocol error")

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.poll_devices()

        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 0

    def test_sync_to_platform_success(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test successful sync to platform"""
        mock_zk, mock_device = mock_zk_class

        # Add records to buffer first
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime(2026, 3, 3, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            ),
            AttendanceRecordDB(
                user_id="2",
                timestamp=datetime(2026, 3, 3, 17, 0, 0),
                status=1,
                device_ip="192.168.1.101",
                punch_type="salida"
            )
        ]
        buffer_repo.add_records(records)

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.sync_to_platform()

        # Verify sync was called
        mock_platform_sync.sync_attendance.assert_called_once()

        # Verify records marked as synced
        stats = buffer_repo.get_stats()
        assert stats['pending_sync'] == 0
        assert stats['synced'] == 2

        # Verify sync log
        history = buffer_repo.get_sync_history()
        assert len(history) == 1
        assert history[0]['status'] == 'success'
        assert history[0]['records_synced'] == 2

    def test_sync_to_platform_failure(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test sync handles platform failure"""
        mock_zk, mock_device = mock_zk_class
        mock_platform_sync.sync_attendance.return_value = False

        # Add records to buffer
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime(2026, 3, 3, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
        ]
        buffer_repo.add_records(records)

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.sync_to_platform()

        # Verify sync was called
        mock_platform_sync.sync_attendance.assert_called_once()

        # Verify records NOT marked as synced
        stats = buffer_repo.get_stats()
        assert stats['pending_sync'] == 1

        # Verify sync log shows failure
        history = buffer_repo.get_sync_history()
        assert len(history) == 1
        assert history[0]['status'] == 'failed'
        assert history[0]['records_failed'] == 1

    def test_sync_to_platform_no_pending(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test sync when no pending records"""
        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        collector.sync_to_platform()

        # Should not call platform sync
        mock_platform_sync.sync_attendance.assert_not_called()

        # Log should show 0 synced
        history = buffer_repo.get_sync_history()
        assert len(history) == 1
        assert history[0]['records_synced'] == 0

    def test_multiple_devices_polling(self, config, mock_zk_class, mock_platform_sync, buffer_repo, tmp_path):
        """Test polling multiple devices"""
        import yaml

        # Create config with multiple devices
        config_data = {
            'platform': {
                'url': 'https://test.example.com',
                'api_key': 'test-api-key',
                'tenant_id': 'test-tenant-id',
            },
            'devices': [
                {
                    'ip': '192.168.1.101',
                    'port': 4370,
                    'timeout': 5,
                    'password': '0',
                    'name': 'Device 1',
                    'enabled': True,
                },
                {
                    'ip': '192.168.1.102',
                    'port': 4370,
                    'timeout': 5,
                    'password': '0',
                    'name': 'Device 2',
                    'enabled': True,
                },
                {
                    'ip': '192.168.1.103',
                    'port': 4370,
                    'timeout': 5,
                    'password': '0',
                    'name': 'Device 3',
                    'enabled': False,  # Disabled device
                }
            ],
            'poll_interval_seconds': 60,
            'sync_interval_seconds': 10,
            'buffer': {
                'max_records': 1000,
                'cleanup_days': 30,
                'db_path': str(tmp_path / 'test_buffer.db')
            },
            'logging': {
                'level': 'DEBUG',
                'format': 'text'
            }
        }
        config_file = tmp_path / "multi_device_config.yaml"
        with open(config_file, 'w') as f:
            yaml.dump(config_data, f)

        multi_config = Config(config_file)

        mock_zk, mock_device = mock_zk_class
        mock_device.attendance_records = [
            create_mock_zk_attendance("1", datetime(2026, 3, 3, 8, 0, 0), 0),
        ]

        collector = AttendanceCollector(multi_config)
        collector.buffer = buffer_repo

        collector.poll_devices()

        # Should only poll 2 enabled devices
        assert len(collector.zk_clients) == 2
        assert '192.168.1.101' in collector.zk_clients
        assert '192.168.1.102' in collector.zk_clients
        assert '192.168.1.103' not in collector.zk_clients

        stats = buffer_repo.get_stats()
        # 1 record per enabled device = 2 total
        assert stats['total_records'] == 2

    def test_collector_run_loop_single_iteration(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test single iteration of collector run loop"""
        mock_zk, mock_device = mock_zk_class
        mock_device.attendance_records = [
            create_mock_zk_attendance("1", datetime(2026, 3, 3, 8, 0, 0), 0),
        ]

        collector = AttendanceCollector(config)
        collector.buffer = buffer_repo

        # Run one polling cycle
        collector._initialize_devices()
        collector.poll_devices()

        assert collector.last_poll is not None
        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 1

    def test_collector_stop_cleans_up(self, config, mock_zk_class, mock_platform_sync, buffer_repo):
        """Test collector stop cleans up connections"""
        mock_zk, mock_device = mock_zk_class

        collector = AttendanceCollector(config)
        collector._initialize_devices()

        # Manually connect clients
        for client in collector.zk_clients.values():
            client.connect()

        assert all(c.connected for c in collector.zk_clients.values())

        collector.stop()

        # All clients should be disconnected
        assert all(not c.connected for c in collector.zk_clients.values())


class TestConfigIntegration:
    """Integration tests for Config with real YAML files"""

    def test_config_loads_from_yaml(self, temp_config_file):
        """Test config loads from YAML file"""
        config = Config(temp_config_file)

        assert config.get('platform.url') == 'https://test.example.com'
        assert config.get('platform.api_key') == 'test-api-key'
        assert config.get('platform.tenant_id') == 'test-tenant-id'
        assert config.get('poll_interval_seconds') == 60
        assert config.get('sync_interval_seconds') == 10

    def test_config_device_list(self, temp_config_file):
        """Test config handles device list correctly"""
        config = Config(temp_config_file)

        devices = config.get('devices')
        assert len(devices) == 1
        assert devices[0]['ip'] == '192.168.1.101'
        assert devices[0]['port'] == 4370
        assert devices[0]['enabled'] is True

    def test_config_defaults_applied(self, temp_config_file):
        """Test default values are applied"""
        config = Config(temp_config_file)

        # Check defaults from schema
        assert config.get('platform.timeout') == 30
        assert config.get('platform.retry_attempts') == 3
        assert config.get('buffer.max_records') == 1000
        assert config.get('buffer.cleanup_days') == 30
        assert config.get('logging.level') == 'DEBUG'

    def test_config_dot_notation(self, temp_config_file):
        """Test dot notation access"""
        config = Config(temp_config_file)

        assert config.get('platform.url') == 'https://test.example.com'
        assert config.get('devices.0.ip') == '192.168.1.101'
        assert config.get('devices.0.port') == 4370
        assert config.get('nonexistent.key', 'default') == 'default'


class TestBufferIntegration:
    """Integration tests for BufferRepository"""

    def test_full_buffer_lifecycle(self, buffer_repo):
        """Test complete buffer lifecycle: add, get, mark synced, cleanup"""
        # Add records
        records = [
            AttendanceRecordDB(
                user_id=str(i),
                timestamp=datetime(2026, 3, 3, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
            for i in range(10)
        ]
        added = buffer_repo.add_records(records)
        assert added == 10

        # Get unsynced
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 10

        # Mark as synced
        record_ids = [r['id'] for r in unsynced]
        marked = buffer_repo.mark_as_synced(record_ids)
        assert marked == 10

        # Verify no pending
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 0

        # Stats
        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 10
        assert stats['synced'] == 10
        assert stats['pending_sync'] == 0

    def test_buffer_max_records_cleanup(self, buffer_repo):
        """Test buffer cleans up when exceeding max_records"""
        buffer_repo.max_records = 5

        # Add 10 records
        records = [
            AttendanceRecordDB(
                user_id=str(i),
                timestamp=datetime(2026, 3, 3, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
                punch_type="entrada"
            )
            for i in range(10)
        ]
        buffer_repo.add_records(records)

        stats = buffer_repo.get_stats()
        assert stats['total_records'] <= 5

    def test_buffer_sync_log(self, buffer_repo):
        """Test sync logging"""
        buffer_repo.log_sync(5, 0, 'success', duration_seconds=1.5)
        buffer_repo.log_sync(0, 3, 'failed', error_message='Timeout', duration_seconds=30.0)

        history = buffer_repo.get_sync_history()
        assert len(history) == 2
        assert history[0]['status'] == 'failed'  # Latest first
        assert history[0]['records_failed'] == 3
        assert history[1]['status'] == 'success'
        assert history[1]['records_synced'] == 5

    def test_buffer_concurrent_access(self, buffer_repo):
        """Test thread-safe buffer operations"""
        import threading
        import time

        errors = []

        def add_records(thread_id):
            try:
                records = [
                    AttendanceRecordDB(
                        user_id=f"{thread_id}-{i}",
                        timestamp=datetime.now(),
                        status=0,
                        device_ip="192.168.1.101",
                        punch_type="entrada"
                    )
                    for i in range(5)
                ]
                buffer_repo.add_records(records)
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=add_records, args=(i,)) for i in range(5)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert len(errors) == 0
        stats = buffer_repo.get_stats()
        assert stats['total_records'] == 25


class TestPlatformSyncIntegration:
    """Integration tests for PlatformSync with mocked HTTP"""

    @pytest.fixture
    def platform_sync(self):
        """PlatformSync instance with mocked session"""
        with patch('src.sync.platform.requests.Session') as mock_session_class:
            mock_session = Mock()
            mock_session_class.return_value = mock_session

            sync = PlatformSync(
                platform_url='https://test.example.com',
                api_key='test-key',
                tenant_id='test-tenant',
                timeout=30,
                retry_attempts=3
            )
            sync.session = mock_session
            yield sync, mock_session

    def test_sync_attendance_success(self, platform_sync):
        """Test successful attendance sync"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        records = [
            {
                'user_id': '1',
                'timestamp': '2026-03-03T08:00:00',
                'status': 0,
                'device_ip': '192.168.1.101',
                'punch_type': 'entrada'
            }
        ]

        result = sync.sync_attendance(records)

        assert result is True
        mock_session.post.assert_called_once()

        # Verify payload structure
        call_args = mock_session.post.call_args
        assert call_args[0][0] == 'https://test.example.com/api/v1/attendance/sync'
        payload = call_args[1]['json']
        assert len(payload['records']) == 1
        assert payload['records'][0]['user_id'] == '1'
        assert 'synced_at' in payload
        assert 'collector_version' in payload

    def test_sync_attendance_empty(self, platform_sync):
        """Test sync with empty records"""
        sync, mock_session = platform_sync

        result = sync.sync_attendance([])

        assert result is True
        mock_session.post.assert_not_called()

    def test_sync_attendance_timeout(self, platform_sync):
        """Test sync handles timeout"""
        sync, mock_session = platform_sync

        import requests
        mock_session.post.side_effect = requests.exceptions.Timeout("Timeout")

        records = [{'user_id': '1', 'timestamp': '2026-03-03T08:00:00', 'status': 0, 'device_ip': '192.168.1.101'}]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_connection_error(self, platform_sync):
        """Test sync handles connection error"""
        sync, mock_session = platform_sync

        import requests
        mock_session.post.side_effect = requests.exceptions.ConnectionError("Connection refused")

        records = [{'user_id': '1', 'timestamp': '2026-03-03T08:00:00', 'status': 0, 'device_ip': '192.168.1.101'}]

        result = sync.sync_attendance(records)

        assert result is False

    def test_sync_attendance_http_error(self, platform_sync):
        """Test sync handles HTTP error"""
        sync, mock_session = platform_sync

        import requests
        mock_response = Mock()
        mock_response.status_code = 401
        mock_response.raise_for_status.side_effect = requests.exceptions.HTTPError("401 Unauthorized")
        mock_session.post.return_value = mock_response

        records = [{'user_id': '1', 'timestamp': '2026-03-03T08:00:00', 'status': 0, 'device_ip': '192.168.1.101'}]

        result = sync.sync_attendance(records)

        assert result is False

    def test_send_heartbeat(self, platform_sync):
        """Test heartbeat sending"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        metrics = {'cpu': 50, 'memory': 60}
        devices_status = [{'ip': '192.168.1.101', 'status': 'online'}]

        result = sync.send_heartbeat(metrics, devices_status)

        assert result is True
        mock_session.post.assert_called_once()

        call_args = mock_session.post.call_args
        assert call_args[0][0] == 'https://test.example.com/api/v1/collector/heartbeat'
        payload = call_args[1]['json']
        assert payload['metrics'] == metrics
        assert payload['devices'] == devices_status
        assert 'timestamp' in payload
        assert 'version' in payload

    def test_get_config(self, platform_sync):
        """Test getting config from platform"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'poll_interval': 120}
        mock_session.get.return_value = mock_response

        config = sync.get_config()

        assert config == {'poll_interval': 120}
        mock_session.get.assert_called_once_with('https://test.example.com/api/v1/collector/config', timeout=10)

    def test_check_version(self, platform_sync):
        """Test version check"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_response.json.return_value = {'latest_version': '2.0.0'}
        mock_session.get.return_value = mock_response

        version = sync.check_version()

        assert version == '2.0.0'

    def test_report_error(self, platform_sync):
        """Test error reporting"""
        sync, mock_session = platform_sync

        mock_response = Mock()
        mock_response.raise_for_status.return_value = None
        mock_session.post.return_value = mock_response

        result = sync.report_error('sync_error', 'Platform unreachable', {'device': '192.168.1.101'})

        assert result is True
        mock_session.post.assert_called_once()

        call_args = mock_session.post.call_args
        assert call_args[0][0] == 'https://test.example.com/api/v1/collector/error'
        payload = call_args[1]['json']
        assert payload['type'] == 'sync_error'
        assert payload['message'] == 'Platform unreachable'
        assert payload['context']['device'] == '192.168.1.101'