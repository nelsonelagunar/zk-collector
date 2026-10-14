"""
Extended unit tests for ZK Client to improve coverage
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.zk.client import ZKClient
from src.zk.exceptions import ZKAttendanceError, ZKConnectionError


class TestZKClientExtended:
    """Extended tests for ZKClient to improve coverage"""

    @pytest.fixture
    def client(self):
        return ZKClient('192.168.1.101', port=4370, timeout=5, password=0)

    def test_connect_max_retries_exhausted(self, client):
        """Test connect when all retries fail"""
        with patch('src.zk.client.ZK') as mock_zk:
            mock_zk.side_effect = Exception("Connection failed")

            with pytest.raises(ZKConnectionError):
                client.connect(max_retries=2, retry_delay=0.01)

    def test_connect_connection_refused(self, client):
        """Test connect with ConnectionRefusedError"""
        with patch('src.zk.client.ZK') as mock_zk:
            mock_zk.side_effect = ConnectionRefusedError("Refused")

            with pytest.raises(ZKConnectionError):
                client.connect(max_retries=1)

    def test_connect_timeout_error(self, client):
        """Test connect with TimeoutError - returns False after retries"""
        with patch('src.zk.client.ZK') as mock_zk:
            mock_zk.side_effect = TimeoutError("Timeout")

            # With max_retries=1, it tries once and returns False (doesn't raise)
            result = client.connect(max_retries=1)
            assert result is False

    def test_disconnect_when_not_connected(self, client):
        """Test disconnect when not connected"""
        client.connected = False
        client.zk = None

        client.disconnect()
        assert client.connected is False
        assert client.zk is None

    def test_get_attendance_not_connected(self, client):
        """Test get_attendance when not connected"""
        client.connected = False
        client.zk = None

        result = client.get_attendance()
        assert result is None

    def test_get_attendance_with_clear_after_read(self, client):
        """Test get_attendance with clear_after_read=True"""
        client.connected = True
        client.zk = Mock()

        mock_attendance = Mock()
        mock_attendance.user_id = "1"
        mock_attendance.timestamp = datetime.now()
        mock_attendance.status = 0

        client.zk.get_attendance.return_value = [mock_attendance]
        client.zk.clear_attendance.return_value = True

        records = client.get_attendance(clear_after_read=True, disable_device=True)

        assert len(records) == 1
        client.zk.clear_attendance.assert_called_once()
        client.zk.enable_device.assert_called_once()

    def test_get_attendance_zk_error(self, client):
        """Test get_attendance with ZKError"""
        from zk.exception import ZKError as PyZKError

        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.side_effect = PyZKError("ZK Error")

        with pytest.raises(ZKAttendanceError):
            client.get_attendance()

    def test_get_attendance_unexpected_error(self, client):
        """Test get_attendance with unexpected error"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.side_effect = Exception("Unexpected")

        with pytest.raises(ZKAttendanceError):
            client.get_attendance()

    def test_get_attendance_enable_device_error(self, client):
        """Test get_attendance when enable_device fails"""
        client.connected = True
        client.zk = Mock()

        mock_attendance = Mock()
        mock_attendance.user_id = "1"
        mock_attendance.timestamp = datetime.now()
        mock_attendance.status = 0

        client.zk.get_attendance.return_value = [mock_attendance]
        client.zk.enable_device.side_effect = Exception("Enable failed")

        # Should not raise, just log warning
        records = client.get_attendance(disable_device=True)
        assert len(records) == 1

    def test_get_device_info_not_connected(self, client):
        """Test get_device_info when not connected"""
        client.connected = False
        client.zk = None

        result = client.get_device_info()
        assert result is None

    def test_get_device_info_exception(self, client):
        """Test get_device_info with exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.side_effect = Exception("Error")

        result = client.get_device_info()
        assert result is None

    def test_get_users_not_connected(self, client):
        """Test get_users when not connected"""
        client.connected = False
        client.zk = None

        result = client.get_users()
        assert result is None

    def test_get_users_exception(self, client):
        """Test get_users with exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_users.side_effect = Exception("Error")

        result = client.get_users()
        assert result is None

    def test_get_time_not_connected(self, client):
        """Test get_time when not connected"""
        client.connected = False
        client.zk = None

        result = client.get_time()
        assert result is None

    def test_get_time_exception(self, client):
        """Test get_time with exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_time.side_effect = Exception("Error")

        result = client.get_time()
        assert result is None

    def test_set_time_not_connected(self, client):
        """Test set_time when not connected"""
        client.connected = False
        client.zk = None

        result = client.set_time(datetime.now())
        assert result is False

    def test_set_time_success(self, client):
        """Test set_time success"""
        client.connected = True
        client.zk = Mock()

        result = client.set_time(datetime.now())
        assert result is True
        client.zk.set_time.assert_called_once()

    def test_set_time_exception(self, client):
        """Test set_time with exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.set_time.side_effect = Exception("Error")

        result = client.set_time(datetime.now())
        assert result is False

    def test_restart_not_connected(self, client):
        """Test restart when not connected"""
        client.connected = False
        client.zk = None

        result = client.restart()
        assert result is False

    def test_restart_success(self, client):
        """Test restart success"""
        client.connected = True
        client.zk = Mock()

        result = client.restart()
        assert result is True
        client.zk.restart.assert_called_once()

    def test_restart_exception(self, client):
        """Test restart with exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.restart.side_effect = Exception("Error")

        result = client.restart()
        assert result is False

    def test_is_online_true(self, client):
        """Test is_online returns True"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.return_value = "6.60"

        result = client.is_online()
        assert result is True

    def test_is_online_false_exception(self, client):
        """Test is_online returns False on exception"""
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.side_effect = Exception("Error")

        result = client.is_online()
        assert result is False
        assert client.connected is False

    def test_is_online_false_not_connected(self, client):
        """Test is_online when not connected"""
        client.connected = False
        client.zk = None

        result = client.is_online()
        assert result is False

    def test_get_connection_status(self, client):
        """Test get_connection_status"""
        client.last_connection_attempt = datetime(2026, 3, 3, 8, 0, 0)
        client.last_successful_connection = datetime(2026, 3, 3, 8, 5, 0)
        client.connection_attempts = 3

        status = client.get_connection_status()

        assert status['ip'] == '192.168.1.101'
        assert status['port'] == 4370
        assert status['connected'] is False
        assert status['last_attempt'] == '2026-03-03T08:00:00'
        assert status['last_success'] == '2026-03-03T08:05:00'
        assert status['failed_attempts'] == 3

    def test_get_connection_status_none_times(self, client):
        """Test get_connection_status with None times"""
        client.last_connection_attempt = None
        client.last_successful_connection = None
        client.connection_attempts = 0

        status = client.get_connection_status()

        assert status['last_attempt'] is None
        assert status['last_success'] is None
        assert status['failed_attempts'] == 0

    def test_connect_success_updates_timestamps(self, client):
        """Test connect updates timestamps correctly"""
        with patch('src.zk.client.ZK') as mock_zk:
            mock_instance = Mock()
            mock_zk.return_value = mock_instance

            result = client.connect()

            assert result is True
            assert client.connected is True
            assert client.last_connection_attempt is not None
            assert client.last_successful_connection is not None
            assert client.connection_attempts == 0
