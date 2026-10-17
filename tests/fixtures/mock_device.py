"""
Mock ZK Device fixture for unit/integration tests.
Provides a controllable mock of the pyzk ZK class for testing AttendanceCollector.
"""
from datetime import datetime
from typing import Any
from unittest.mock import MagicMock

import pytest


class MockZKDevice:
    """
    Mock ZK device that mimics the pyzk.ZK interface.
    All methods are MagicMock instances with configurable side effects.
    """

    def __init__(
        self,
        host: str = "127.0.0.1",
        port: int = 4370,
        timeout: int = 5,
        password: int = 0,
        force_udp: bool = False,
        ommit_ping: bool = False,
    ):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.password = password
        self.force_udp = force_udp
        self.ommit_ping = ommit_ping

        # Connection state
        self.connected = False
        self.device_disabled = False

        # Synthetic data
        self.attendance_records: list[Any] = []
        self.users: list[Any] = self._generate_synthetic_users()

        # Create mock methods with side effects
        self.connect = MagicMock(side_effect=self._connect)
        self.disconnect = MagicMock(side_effect=self._disconnect)
        self.disable_device = MagicMock(side_effect=self._disable_device)
        self.enable_device = MagicMock(side_effect=self._enable_device)
        self.get_attendance = MagicMock(side_effect=self._get_attendance)
        self.clear_attendance = MagicMock(side_effect=self._clear_attendance)
        self.get_firmware_version = MagicMock(return_value="6.60")
        self.get_serialnumber = MagicMock(return_value="TEST123456")
        self.get_platform = MagicMock(return_value="ZKTECO")
        self.get_device_name = MagicMock(return_value="Test Device")
        self.get_mac = MagicMock(return_value="AA:BB:CC:DD:EE:FF")
        self.get_users = MagicMock(side_effect=self._get_users)
        self.get_time = MagicMock(side_effect=self._get_time)
        self.set_time = MagicMock(return_value=None)
        self.restart = MagicMock(return_value=None)

        # For protocol testing
        self._last_command = None

    def _generate_synthetic_users(self) -> list[Any]:
        """Generate synthetic user objects matching pyzk user structure"""
        users = []
        for i in range(1, 6):
            user = MagicMock()
            user.user_id = str(i)
            user.name = f"Test User {i}"
            user.privilege = 0
            user.password = ""
            user.group_id = "1"
            user.user_role = 0
            users.append(user)
        return users

    def _connect(self):
        """Simulate connection"""
        self.connected = True
        self._last_command = "connect"

    def _disconnect(self):
        """Simulate disconnection"""
        self.connected = False
        self._last_command = "disconnect"

    def _disable_device(self):
        """Disable device operations"""
        self.device_disabled = True
        self._last_command = "disable_device"

    def _enable_device(self):
        """Enable device operations"""
        self.device_disabled = False
        self._last_command = "enable_device"

    def _get_attendance(self) -> list[Any]:
        """Return attendance records"""
        self._last_command = "get_attendance"
        if self.device_disabled:
            raise Exception("Device is disabled")
        return list(self.attendance_records)  # Return copy

    def _clear_attendance(self):
        """Clear attendance buffer"""
        self._last_command = "clear_attendance"
        self.attendance_records.clear()

    def _get_users(self) -> list[Any]:
        """Return user list"""
        self._last_command = "get_users"
        return list(self.users)

    def _get_time(self) -> datetime:
        """Return current time"""
        self._last_command = "get_time"
        return datetime.now()

    def set_attendance_records(self, records: list[Any]):
        """Set attendance records for testing"""
        self.attendance_records = records

    def add_attendance_record(self, record: Any):
        """Add a single attendance record"""
        self.attendance_records.append(record)

    def reset(self):
        """Reset device state"""
        self.connected = False
        self.device_disabled = False
        self.attendance_records.clear()
        self._last_command = None
        # Reset all mock call counts
        for attr_name in dir(self):
            attr = getattr(self, attr_name)
            if isinstance(attr, MagicMock):
                attr.reset_mock()

    def assert_method_called(self, method_name: str):
        """Assert a method was called"""
        method = getattr(self, method_name, None)
        if method and isinstance(method, MagicMock):
            method.assert_called()
        else:
            raise AttributeError(f"Method {method_name} not found or not a mock")

    def assert_method_not_called(self, method_name: str):
        """Assert a method was not called"""
        method = getattr(self, method_name, None)
        if method and isinstance(method, MagicMock):
            method.assert_not_called()
        else:
            raise AttributeError(f"Method {method_name} not found or not a mock")

    def get_call_count(self, method_name: str) -> int:
        """Get call count for a method"""
        method = getattr(self, method_name, None)
        if method and isinstance(method, MagicMock):
            return method.call_count
        return 0


def create_mock_zk_attendance(
    user_id: str, timestamp: datetime, status: int, punch_type: str = "entrada"
) -> Any:
    """Create a mock ZK attendance record matching pyzk structure"""
    mock = MagicMock()
    mock.user_id = user_id
    mock.timestamp = timestamp
    mock.status = status
    mock.punch_type = punch_type
    return mock


@pytest.fixture
def mock_zk_device():
    """Provides a fresh MockZKDevice instance for each test"""
    return MockZKDevice()


@pytest.fixture
def mock_zk_device_with_data():
    """Provides a MockZKDevice pre-populated with test data"""
    device = MockZKDevice()
    device.set_attendance_records([
        create_mock_zk_attendance("1", datetime(2026, 10, 13, 8, 0, 0), 0),
        create_mock_zk_attendance("2", datetime(2026, 10, 13, 12, 0, 0), 1),
        create_mock_zk_attendance("3", datetime(2026, 10, 13, 17, 0, 0), 0),
    ])
    return device


@pytest.fixture
def mock_zk_class(mock_zk_device):
    """Fixture to mock the pyzk ZK class, returning our mock device"""
    with pytest.MonkeyPatch().context() as mp:
        mp.setattr("src.zk_client.client.ZK", lambda *args, **kwargs: mock_zk_device)
        yield mock_zk_device
