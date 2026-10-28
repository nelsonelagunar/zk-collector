"""
Detailed unit tests for ZKClient module to improve coverage
"""

import logging
from datetime import datetime, timedelta
from unittest.mock import Mock, patch

import pytest
from zk.exception import ZKError as PyZKError

from src.zk_client.attendance import AttendanceRecord
from src.zk_client.client import ZKClient
from src.zk_client.exceptions import ZKAttendanceError, ZKConnectionError


def _dt(days_ago: int = 365, hours: int = 12, minutes: int = 0, seconds: int = 0) -> datetime:
    """Relative datetime for tests — avoids time-bombs (MYK-466)."""
    base = datetime.now().replace(
        hour=hours, minute=minutes, second=seconds, microsecond=0
    )
    return base - timedelta(days=days_ago)


class TestZKClientDetailed:
    """Detailed tests for ZKClient to improve coverage"""

    @pytest.fixture
    def zk_client(self):
        """Create ZKClient instance"""
        return ZKClient("192.168.1.100", port=4370, timeout=5, password=0)

    @patch("src.zk_client.client.ZK")
    def test_connect_success(self, mock_zk_class, zk_client):
        """Test successful connection"""
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_zk_class.return_value = mock_instance

        result = zk_client.connect(max_retries=1)

        assert result is True
        assert zk_client.connected is True
        assert zk_client.zk == mock_instance
        assert zk_client.last_successful_connection is not None
        assert zk_client.connection_attempts == 0  # reset on success
        mock_zk_class.assert_called_once_with(
            "192.168.1.100",
            port=4370,
            timeout=5,
            password=0,
            force_udp=False,
            ommit_ping=False,
            encoding="utf-8",
        )
        mock_instance.connect.assert_called_once()

    @patch("src.zk_client.client.ZK")
    def test_connect_pyzkerror_retry(self, mock_zk_class, zk_client):
        """Test PyZKError triggers retry"""
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_zk_class.side_effect = [PyZKError("first error"), mock_instance]

        result = zk_client.connect(max_retries=3, retry_delay=0.01)

        assert result is True
        assert mock_zk_class.call_count == 2
        # connection_attempts is reset to 0 on success (line 86 in client.py)
        assert zk_client.connection_attempts == 0

    @patch("src.zk_client.client.ZK")
    def test_connect_timeout_retry(self, mock_zk_class, zk_client):
        """Test TimeoutError triggers retry"""
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_zk_class.side_effect = [TimeoutError("timeout"), mock_instance]

        result = zk_client.connect(max_retries=3, retry_delay=0.01)

        assert result is True
        assert mock_zk_class.call_count == 2

    @patch("src.zk_client.client.ZK")
    def test_connect_connection_refused_raises(self, mock_zk_class, zk_client):
        """Test ConnectionRefusedError raises ZKConnectionError immediately"""
        mock_zk_class.side_effect = ConnectionRefusedError("refused")

        with pytest.raises(ZKConnectionError, match="Conexión rechazada"):
            zk_client.connect(max_retries=3)
        assert mock_zk_class.call_count == 1

    @patch("src.zk_client.client.ZK")
    def test_connect_generic_exception_raises(self, mock_zk_class, zk_client):
        """Test generic Exception raises ZKConnectionError immediately"""
        mock_zk_class.side_effect = Exception("unexpected error")

        with pytest.raises(ZKConnectionError, match="Error inesperado"):
            zk_client.connect(max_retries=3)
        assert mock_zk_class.call_count == 1

    @patch("src.zk_client.client.ZK")
    def test_connect_max_retries_exhausted(self, mock_zk_class, zk_client):
        """Test max retries exhausted returns False"""
        mock_zk_class.side_effect = PyZKError("persistent error")

        result = zk_client.connect(max_retries=3, retry_delay=0.01)

        assert result is False
        assert zk_client.connected is False
        assert mock_zk_class.call_count == 3

    @patch("src.zk_client.client.ZK")
    def test_connect_with_password(self, mock_zk_class, zk_client):
        """Test connect with password parameter"""
        zk_client.password = 12345
        mock_instance = Mock()
        mock_instance.connect.return_value = True
        mock_zk_class.return_value = mock_instance

        zk_client.connect()

        mock_zk_class.assert_called_once_with(
            "192.168.1.100",
            port=4370,
            timeout=5,
            password=12345,
            force_udp=False,
            ommit_ping=False,
            encoding="utf-8",
        )

    def test_disconnect_when_connected(self, zk_client):
        """Test disconnect when connected"""
        mock_zk = Mock()
        zk_client.zk = mock_zk
        zk_client.connected = True

        zk_client.disconnect()

        mock_zk.disconnect.assert_called_once()
        assert zk_client.connected is False
        assert zk_client.zk is None

    def test_disconnect_when_not_connected(self, zk_client):
        """Test disconnect when not connected (no-op)"""
        zk_client.zk = None
        zk_client.connected = False

        zk_client.disconnect()  # Should not raise

    def test_disconnect_handles_exception(self, zk_client, caplog):
        """Test disconnect handles exception gracefully"""
        mock_zk = Mock()
        mock_zk.disconnect.side_effect = Exception("disconnect error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        with caplog.at_level(logging.WARNING):
            zk_client.disconnect()

        assert "Error cerrando conexión" in caplog.text
        assert zk_client.connected is False

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_success(self, mock_zk_class, zk_client):
        """Test successful attendance retrieval"""
        mock_zk = Mock()
        mock_zk.get_attendance.return_value = [
            Mock(user_id="1", timestamp="2026-01-01 08:00:00", status=0),
            Mock(user_id="2", timestamp="2026-01-01 09:00:00", status=1),
        ]
        zk_client.zk = mock_zk
        zk_client.connected = True

        records = zk_client.get_attendance()

        assert len(records) == 2
        assert isinstance(records[0], AttendanceRecord)
        assert records[0].user_id == "1"
        assert records[1].user_id == "2"
        mock_zk.disable_device.assert_called_once()
        mock_zk.get_attendance.assert_called_once()
        mock_zk.enable_device.assert_called_once()

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_empty(self, mock_zk_class, zk_client):
        """Test attendance retrieval with no records"""
        mock_zk = Mock()
        mock_zk.get_attendance.return_value = []
        zk_client.zk = mock_zk
        zk_client.connected = True

        records = zk_client.get_attendance()

        assert records == []
        mock_zk.disable_device.assert_called_once()
        mock_zk.enable_device.assert_called_once()

    def test_get_attendance_not_connected(self, zk_client, caplog):
        """Test get_attendance when not connected"""
        zk_client.connected = False

        records = zk_client.get_attendance()

        assert records is None
        assert "No hay conexión activa" in caplog.text

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_pyzkerror(self, mock_zk_class, zk_client):
        """Test get_attendance handles PyZKError"""
        mock_zk = Mock()
        mock_zk.get_attendance.side_effect = PyZKError("attendance error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        with pytest.raises(ZKAttendanceError, match="Error obteniendo attendance"):
            zk_client.get_attendance()
        mock_zk.enable_device.assert_called_once()  # Called in finally

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_generic_exception(self, mock_zk_class, zk_client):
        """Test get_attendance handles generic Exception"""
        mock_zk = Mock()
        mock_zk.get_attendance.side_effect = Exception("unexpected")
        zk_client.zk = mock_zk
        zk_client.connected = True

        with pytest.raises(ZKAttendanceError, match="Error inesperado"):
            zk_client.get_attendance()
        mock_zk.enable_device.assert_called_once()

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_clear_after_read(self, mock_zk_class, zk_client):
        """Test get_attendance with clear_after_read=True"""
        mock_zk = Mock()
        mock_zk.get_attendance.return_value = [
            Mock(user_id="1", timestamp="2026-01-01 08:00:00", status=0)
        ]
        zk_client.zk = mock_zk
        zk_client.connected = True

        zk_client.get_attendance(clear_after_read=True)

        mock_zk.clear_attendance.assert_called_once()

    @patch("src.zk_client.client.ZK")
    def test_get_attendance_disable_device_false(self, mock_zk_class, zk_client):
        """Test get_attendance with disable_device=False"""
        mock_zk = Mock()
        mock_zk.get_attendance.return_value = [
            Mock(user_id="1", timestamp="2026-01-01 08:00:00", status=0)
        ]
        zk_client.zk = mock_zk
        zk_client.connected = True

        zk_client.get_attendance(disable_device=False)

        mock_zk.disable_device.assert_not_called()
        mock_zk.enable_device.assert_not_called()

    @patch("src.zk_client.client.ZK")
    def test_get_device_info_success(self, mock_zk_class, zk_client):
        """Test successful device info retrieval"""
        mock_zk = Mock()
        mock_zk.get_firmware_version.return_value = "6.60"
        mock_zk.get_serialnumber.return_value = "SN123456"
        mock_zk.get_platform.return_value = "ZKPlatform"
        mock_zk.get_device_name.return_value = "Device1"
        mock_zk.get_mac.return_value = "AA:BB:CC:DD:EE:FF"
        zk_client.zk = mock_zk
        zk_client.connected = True

        info = zk_client.get_device_info()

        assert info["firmware_version"] == "6.60"
        assert info["serial_number"] == "SN123456"
        assert info["platform"] == "ZKPlatform"
        assert info["device_name"] == "Device1"
        assert info["mac_address"] == "AA:BB:CC:DD:EE:FF"
        assert zk_client._device_info_cache == info

    def test_get_device_info_not_connected(self, zk_client):
        """Test get_device_info when not connected"""
        zk_client.connected = False
        assert zk_client.get_device_info() is None

    @patch("src.zk_client.client.ZK")
    def test_get_device_info_exception(self, mock_zk_class, zk_client, caplog):
        """Test get_device_info handles exception"""
        mock_zk = Mock()
        mock_zk.get_firmware_version.side_effect = Exception("error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        info = zk_client.get_device_info()

        assert info is None
        assert "Error obteniendo información del dispositivo" in caplog.text

    @patch("src.zk_client.client.ZK")
    def test_get_users_success(self, mock_zk_class, zk_client):
        """Test successful users retrieval"""
        mock_zk = Mock()
        mock_zk.get_users.return_value = [
            {"uid": 1, "name": "User1", "privilege": 0},
            {"uid": 2, "name": "User2", "privilege": 1},
        ]
        zk_client.zk = mock_zk
        zk_client.connected = True

        users = zk_client.get_users()

        assert len(users) == 2
        assert users[0]["name"] == "User1"

    def test_get_users_not_connected(self, zk_client):
        """Test get_users when not connected"""
        zk_client.connected = False
        assert zk_client.get_users() is None

    @patch("src.zk_client.client.ZK")
    def test_get_users_exception(self, mock_zk_class, zk_client, caplog):
        """Test get_users handles exception"""
        mock_zk = Mock()
        mock_zk.get_users.side_effect = Exception("error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        users = zk_client.get_users()

        assert users is None
        assert "Error obteniendo usuarios" in caplog.text

    @patch("src.zk_client.client.ZK")
    def test_get_time_success(self, mock_zk_class, zk_client):
        """Test successful time retrieval"""
        mock_zk = Mock()
        expected_time = _dt()
        mock_zk.get_time.return_value = expected_time
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.get_time()

        assert result == expected_time

    def test_get_time_not_connected(self, zk_client):
        """Test get_time when not connected"""
        zk_client.connected = False
        assert zk_client.get_time() is None

    @patch("src.zk_client.client.ZK")
    def test_get_time_not_datetime(self, mock_zk_class, zk_client):
        """Test get_time when return is not datetime"""
        mock_zk = Mock()
        mock_zk.get_time.return_value = "not a datetime"
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.get_time()

        assert result is None

    @patch("src.zk_client.client.ZK")
    def test_set_time_success(self, mock_zk_class, zk_client):
        """Test successful time setting"""
        mock_zk = Mock()
        zk_client.zk = mock_zk
        zk_client.connected = True

        new_time = _dt()
        result = zk_client.set_time(new_time)

        assert result is True
        mock_zk.set_time.assert_called_once_with(new_time)

    def test_set_time_not_connected(self, zk_client):
        """Test set_time when not connected"""
        zk_client.connected = False
        assert zk_client.set_time(datetime.now()) is False

    @patch("src.zk_client.client.ZK")
    def test_set_time_exception(self, mock_zk_class, zk_client, caplog):
        """Test set_time handles exception"""
        mock_zk = Mock()
        mock_zk.set_time.side_effect = Exception("error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.set_time(datetime.now())

        assert result is False
        assert "Error estableciendo hora" in caplog.text

    @patch("src.zk_client.client.ZK")
    def test_restart_success(self, mock_zk_class, zk_client):
        """Test successful device restart"""
        mock_zk = Mock()
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.restart()

        assert result is True
        mock_zk.restart.assert_called_once()

    def test_restart_not_connected(self, zk_client):
        """Test restart when not connected"""
        zk_client.connected = False
        assert zk_client.restart() is False

    @patch("src.zk_client.client.ZK")
    def test_restart_exception(self, mock_zk_class, zk_client, caplog):
        """Test restart handles exception"""
        mock_zk = Mock()
        mock_zk.restart.side_effect = Exception("error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.restart()

        assert result is False
        assert "Error reiniciando dispositivo" in caplog.text

    @patch("src.zk_client.client.ZK")
    def test_is_online_true(self, mock_zk_class, zk_client):
        """Test is_online returns True when device responds"""
        mock_zk = Mock()
        mock_zk.get_firmware_version.return_value = "6.60"
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.is_online()

        assert result is True

    @patch("src.zk_client.client.ZK")
    def test_is_online_false_on_exception(self, mock_zk_class, zk_client):
        """Test is_online returns False on exception"""
        mock_zk = Mock()
        mock_zk.get_firmware_version.side_effect = Exception("error")
        zk_client.zk = mock_zk
        zk_client.connected = True

        result = zk_client.is_online()

        assert result is False
        assert zk_client.connected is False

    def test_is_online_not_connected(self, zk_client):
        """Test is_online when not connected"""
        zk_client.connected = False
        assert zk_client.is_online() is False

    @patch("src.zk_client.client.ZK")
    def test_get_connection_status(self, mock_zk_class, zk_client):
        """Test get_connection_status"""
        zk_client.connected = True
        attempt_dt = _dt(days_ago=365, hours=10)
        success_dt = _dt(days_ago=365, hours=10, minutes=0, seconds=5)
        zk_client.last_connection_attempt = attempt_dt
        zk_client.last_successful_connection = success_dt
        zk_client.connection_attempts = 0

        status = zk_client.get_connection_status()

        assert status["ip"] == "192.168.1.100"
        assert status["port"] == 4370
        assert status["connected"] is True
        assert status["last_attempt"] == attempt_dt.isoformat()
        assert status["last_success"] == success_dt.isoformat()
        assert status["failed_attempts"] == 0

    def test_get_connection_status_no_attempts(self, zk_client):
        """Test get_connection_status with no attempts"""
        status = zk_client.get_connection_status()

        assert status["last_attempt"] is None
        assert status["last_success"] is None
        assert status["failed_attempts"] == 0
