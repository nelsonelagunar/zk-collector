"""
Unit tests for ZKClient module
"""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest
from zk.exception import ZKError as PyZKError

from src.zk_client.attendance import AttendanceRecord
from src.zk_client.client import ZKClient
from src.zk_client.exceptions import (
    ZKAttendanceError,
    ZKConnectionError,
)


class TestZKClientInit:
    """Tests for ZKClient initialization"""

    def test_init_defaults(self):
        """Test initialization with defaults"""
        client = ZKClient("192.168.1.101")

        assert client.ip == "192.168.1.101"
        assert client.port == 4370
        assert client.timeout == 5
        assert client.password == "0"
        assert client.force_udp is False
        assert client.ommit_ping is False
        assert client.encoding == "utf-8"
        assert client.zk is None
        assert client.connected is False
        assert client.connection_attempts == 0

    def test_init_custom_params(self):
        """Test initialization with custom parameters"""
        client = ZKClient(
            ip="10.0.0.1",
            port=4371,
            timeout=10,
            password="secret",
            force_udp=True,
            ommit_ping=True,
            encoding="latin-1",
        )

        assert client.ip == "10.0.0.1"
        assert client.port == 4371
        assert client.timeout == 10
        assert client.password == "secret"
        assert client.force_udp is True
        assert client.ommit_ping is True
        assert client.encoding == "latin-1"


class TestZKClientConnect:
    """Tests for connect method"""

    @patch("src.zk_client.client.ZK")
    def test_connect_success(self, mock_zk_class):
        """Test successful connection"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk

        client = ZKClient("192.168.1.101")
        result = client.connect()

        assert result is True
        assert client.connected is True
        assert client.zk == mock_zk
        assert client.last_successful_connection is not None
        assert client.connection_attempts == 0
        mock_zk.connect.assert_called_once()

    @patch("src.zk_client.client.ZK")
    def test_connect_with_custom_params(self, mock_zk_class):
        """Test connection uses custom parameters"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk

        client = ZKClient(
            "192.168.1.101",
            port=4371,
            timeout=10,
            password="secret",
            force_udp=True,
            ommit_ping=True,
            encoding="latin-1",
        )
        client.connect()

        mock_zk_class.assert_called_once_with(
            "192.168.1.101",
            port=4371,
            timeout=10,
            password="secret",
            force_udp=True,
            ommit_ping=True,
            encoding="latin-1",
        )

    @patch("src.zk_client.client.ZK")
    def test_connect_retry_on_timeout(self, mock_zk_class):
        """Test retry on timeout"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk
        mock_zk.connect.side_effect = [TimeoutError("Timeout"), None]

        client = ZKClient("192.168.1.101")
        result = client.connect(max_retries=3, retry_delay=0.01)

        assert result is True
        assert mock_zk.connect.call_count == 2

    @patch("src.zk_client.client.ZK")
    def test_connect_retry_on_zkerror(self, mock_zk_class):
        """Test retry on ZKError"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk
        mock_zk.connect.side_effect = [PyZKError("ZK Error"), None]

        client = ZKClient("192.168.1.101")
        result = client.connect(max_retries=3, retry_delay=0.01)

        assert result is True
        assert mock_zk.connect.call_count == 2

    @patch("src.zk_client.client.ZK")
    def test_connect_fails_after_max_retries(self, mock_zk_class):
        """Test connection fails after max retries"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk
        mock_zk.connect.side_effect = PyZKError("Persistent error")

        client = ZKClient("192.168.1.101")
        result = client.connect(max_retries=3, retry_delay=0.01)

        assert result is False
        assert client.connected is False
        assert mock_zk.connect.call_count == 3

    @patch("src.zk_client.client.ZK")
    def test_connect_connection_refused_raises(self, mock_zk_class):
        """Test connection refused raises ZKConnectionError"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk
        mock_zk.connect.side_effect = ConnectionRefusedError("Refused")

        client = ZKClient("192.168.1.101")
        with pytest.raises(ZKConnectionError):
            client.connect(max_retries=1)

    @patch("src.zk_client.client.ZK")
    def test_connect_unexpected_error_raises(self, mock_zk_class):
        """Test unexpected error raises ZKConnectionError"""
        mock_zk = Mock()
        mock_zk_class.return_value = mock_zk
        mock_zk.connect.side_effect = Exception("Unexpected")

        client = ZKClient("192.168.1.101")
        with pytest.raises(ZKConnectionError):
            client.connect(max_retries=1)

    def test_connect_increments_attempts(self):
        """Test connection_attempts increments on each attempt"""
        with patch("src.zk_client.client.ZK") as mock_zk_class:
            mock_zk = Mock()
            mock_zk_class.return_value = mock_zk
            mock_zk.connect.side_effect = PyZKError("Error")

            client = ZKClient("192.168.1.101")
            client.connect(max_retries=3, retry_delay=0.01)

            assert client.connection_attempts == 3


class TestZKClientDisconnect:
    """Tests for disconnect method"""

    def test_disconnect_when_connected(self):
        """Test disconnect when connected"""
        client = ZKClient("192.168.1.101")
        client.zk = Mock()
        client.connected = True

        # Store mock before disconnect sets it to None
        mock_zk = client.zk

        client.disconnect()

        assert client.connected is False
        assert client.zk is None
        mock_zk.disconnect.assert_called_once()

    def test_disconnect_when_not_connected(self):
        """Test disconnect when not connected"""
        client = ZKClient("192.168.1.101")
        client.zk = None
        client.connected = False

        client.disconnect()  # Should not raise

        assert client.connected is False
        assert client.zk is None

    def test_disconnect_handles_error(self):
        """Test disconnect handles errors gracefully"""
        client = ZKClient("192.168.1.101")
        client.zk = Mock()
        client.zk.disconnect.side_effect = Exception("Disconnect error")
        client.connected = True

        client.disconnect()  # Should not raise

        assert client.connected is False
        assert client.zk is None


class TestZKClientGetAttendance:
    """Tests for get_attendance method"""

    def test_get_attendance_not_connected(self):
        """Test get_attendance when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.get_attendance()

        assert result is None

    def test_get_attendance_success(self):
        """Test successful get_attendance"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()

        # Create mock attendance records
        mock_att1 = Mock()
        mock_att1.user_id = "1"
        mock_att1.timestamp = datetime(2026, 3, 3, 8, 0, 0)
        mock_att1.status = 0

        mock_att2 = Mock()
        mock_att2.user_id = "2"
        mock_att2.timestamp = datetime(2026, 3, 3, 17, 0, 0)
        mock_att2.status = 1

        client.zk.get_attendance.return_value = [mock_att1, mock_att2]

        records = client.get_attendance()

        assert records is not None
        assert len(records) == 2
        assert all(isinstance(r, AttendanceRecord) for r in records)
        assert records[0].user_id == "1"
        assert records[0].punch_type == "entrada"
        assert records[1].user_id == "2"
        assert records[1].punch_type == "salida"

        # Verify device disable/enable cycle
        client.zk.disable_device.assert_called_once()
        client.zk.enable_device.assert_called_once()

    def test_get_attendance_empty(self):
        """Test get_attendance with no records"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.return_value = []

        records = client.get_attendance()

        assert records == []

    def test_get_attendance_with_clear_after_read(self):
        """Test get_attendance with clear_after_read=True"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()

        # Create mock attendance records
        mock_att = Mock()
        mock_att.user_id = "1"
        mock_att.timestamp = datetime.now()
        mock_att.status = 0
        client.zk.get_attendance.return_value = [mock_att]

        records = client.get_attendance(clear_after_read=True)

        client.zk.clear_attendance.assert_called_once()

    def test_get_attendance_without_disable_device(self):
        """Test get_attendance with disable_device=False"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.return_value = []

        records = client.get_attendance(disable_device=False)

        client.zk.disable_device.assert_not_called()
        client.zk.enable_device.assert_not_called()

    def test_get_attendance_zkerror_raises(self):
        """Test get_attendance raises ZKAttendanceError on ZKError"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.side_effect = PyZKError("ZK Error")

        with pytest.raises(ZKAttendanceError):
            client.get_attendance()

    def test_get_attendance_unexpected_error_raises(self):
        """Test get_attendance raises ZKAttendanceError on unexpected error"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.side_effect = Exception("Unexpected")

        with pytest.raises(ZKAttendanceError):
            client.get_attendance()

    def test_get_attendance_enable_device_on_error(self):
        """Test device is enabled even on error"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_attendance.side_effect = PyZKError("Error")

        with pytest.raises(ZKAttendanceError):
            client.get_attendance()

        client.zk.enable_device.assert_called_once()


class TestZKClientGetDeviceInfo:
    """Tests for get_device_info method"""

    def test_get_device_info_not_connected(self):
        """Test get_device_info when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.get_device_info()

        assert result is None

    def test_get_device_info_success(self):
        """Test successful get_device_info"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()

        client.zk.get_firmware_version.return_value = "6.60"
        client.zk.get_serialnumber.return_value = "TEST123"
        client.zk.get_platform.return_value = "ZKTECO"
        client.zk.get_device_name.return_value = "Test Device"
        client.zk.get_mac.return_value = "AA:BB:CC:DD:EE:FF"

        info = client.get_device_info()

        assert info is not None
        assert info["firmware_version"] == "6.60"
        assert info["serial_number"] == "TEST123"
        assert info["platform"] == "ZKTECO"
        assert info["device_name"] == "Test Device"
        assert info["mac_address"] == "AA:BB:CC:DD:EE:FF"

    def test_get_device_info_handles_error(self):
        """Test get_device_info handles errors"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.side_effect = Exception("Error")

        result = client.get_device_info()

        assert result is None


class TestZKClientOtherMethods:
    """Tests for other ZKClient methods"""

    def test_get_users(self):
        """Test get_users"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_users.return_value = [{"user_id": "1", "name": "Test"}]

        users = client.get_users()

        assert users == [{"user_id": "1", "name": "Test"}]

    def test_get_users_not_connected(self):
        """Test get_users when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.get_users()

        assert result is None

    def test_get_time(self):
        """Test get_time"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        expected_time = datetime(2026, 3, 3, 12, 0, 0)
        client.zk.get_time.return_value = expected_time

        result = client.get_time()

        assert result == expected_time

    def test_set_time(self):
        """Test set_time"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()

        new_time = datetime(2026, 3, 3, 12, 0, 0)
        result = client.set_time(new_time)

        assert result is True
        client.zk.set_time.assert_called_once_with(new_time)

    def test_set_time_not_connected(self):
        """Test set_time when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.set_time(datetime.now())

        assert result is False

    def test_restart(self):
        """Test restart"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()

        result = client.restart()

        assert result is True
        client.zk.restart.assert_called_once()

    def test_restart_not_connected(self):
        """Test restart when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.restart()

        assert result is False


class TestZKClientIsOnline:
    """Tests for is_online method"""

    def test_is_online_true(self):
        """Test is_online returns True when connected and responsive"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.return_value = "6.60"

        result = client.is_online()

        assert result is True

    def test_is_online_false_not_connected(self):
        """Test is_online returns False when not connected"""
        client = ZKClient("192.168.1.101")
        client.connected = False

        result = client.is_online()

        assert result is False

    def test_is_online_false_on_error(self):
        """Test is_online returns False and disconnects on error"""
        client = ZKClient("192.168.1.101")
        client.connected = True
        client.zk = Mock()
        client.zk.get_firmware_version.side_effect = Exception("Error")

        result = client.is_online()

        assert result is False
        assert client.connected is False


class TestZKClientGetConnectionStatus:
    """Tests for get_connection_status method"""

    def test_get_connection_status(self):
        """Test get_connection_status returns correct structure"""
        client = ZKClient("192.168.1.101", port=4371)
        client.connected = True
        client.last_connection_attempt = datetime(2026, 3, 3, 10, 0, 0)
        client.last_successful_connection = datetime(2026, 3, 3, 10, 0, 5)
        client.connection_attempts = 2

        status = client.get_connection_status()

        assert status["ip"] == "192.168.1.101"
        assert status["port"] == 4371
        assert status["connected"] is True
        assert status["last_attempt"] == "2026-03-03T10:00:00"
        assert status["last_success"] == "2026-03-03T10:00:05"
        assert status["failed_attempts"] == 2


class TestAttendanceRecord:
    """Tests for AttendanceRecord model"""

    def test_from_zk_attendance(self):
        """Test creating AttendanceRecord from ZK attendance object"""
        mock_zk_att = Mock()
        mock_zk_att.user_id = "1"
        mock_zk_att.timestamp = datetime(2026, 3, 3, 8, 0, 0)
        mock_zk_att.status = 0

        record = AttendanceRecord.from_zk_attendance(mock_zk_att, "192.168.1.101")

        assert record.user_id == "1"
        assert record.timestamp == datetime(2026, 3, 3, 8, 0, 0)
        assert record.status == 0
        assert record.device_ip == "192.168.1.101"
        assert record.punch_type == "entrada"

    def test_from_zk_attendance_status_1(self):
        """Test punch_type derivation for status 1 (salida)"""
        mock_zk_att = Mock()
        mock_zk_att.user_id = "1"
        mock_zk_att.timestamp = datetime(2026, 3, 3, 17, 0, 0)
        mock_zk_att.status = 1

        record = AttendanceRecord.from_zk_attendance(mock_zk_att, "192.168.1.101")

        assert record.punch_type == "salida"

    def test_punch_type_derivation(self):
        """Test punch_type property derivation"""
        record = AttendanceRecord(
            user_id="1", timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
        )
        assert record.punch_type == "entrada"

        record2 = AttendanceRecord(
            user_id="1", timestamp=datetime.now(), status=1, device_ip="192.168.1.101"
        )
        assert record2.punch_type == "salida"

    def test_to_dict(self):
        """Test to_dict conversion"""
        record = AttendanceRecord(
            user_id="1",
            timestamp=datetime(2026, 3, 3, 8, 0, 0),
            status=0,
            device_ip="192.168.1.101",
        )

        data = record.to_dict()

        assert data["user_id"] == "1"
        assert data["status"] == 0
        assert data["device_ip"] == "192.168.1.101"
        assert data["punch_type"] == "entrada"
        assert "2026-03-03T08:00:00" in data["timestamp"]
