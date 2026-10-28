"""
Unit tests for buffer models module
"""

from datetime import datetime, timedelta

from src.buffer.models import AttendanceRecordDB


def _dt(days_ago: int = 0, hours: int = 8, minutes: int = 0, seconds: int = 0) -> datetime:
    """Relative datetime for tests — avoids time-bombs (MYK-466)."""
    base = datetime.now().replace(
        hour=hours, minute=minutes, second=seconds, microsecond=0
    )
    return base - timedelta(days=days_ago)


class TestAttendanceRecordDB:
    """Tests for AttendanceRecordDB dataclass"""

    def test_init_required_fields(self):
        """Test creating AttendanceRecordDB with required fields"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=_dt(days_ago=365),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        assert record.user_id == "1"
        assert record.timestamp == _dt(days_ago=365)
        assert record.status == 0
        assert record.device_ip == "192.168.1.100"
        assert record.punch_type == "checkin"
        assert record.synced is False  # default
        assert record.sync_attempts == 0  # default

    def test_init_with_optional_fields(self):
        """Test creating AttendanceRecordDB with optional fields"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=_dt(days_ago=365),
            status=1,
            device_ip="192.168.1.100",
            punch_type="checkout",
            synced=True,
            sync_attempts=2,
        )

        assert record.synced is True
        assert record.sync_attempts == 2

    def test_to_dict(self):
        """Test to_dict conversion"""
        record = AttendanceRecordDB(
            user_id="123",
            timestamp=_dt(days_ago=200, hours=14, minutes=30, seconds=45),
            status=0,
            device_ip="192.168.1.50",
            punch_type="checkin",
            synced=True,
            sync_attempts=1,
        )
        d = record.to_dict()
        assert d["user_id"] == "123"
        assert d["timestamp"] == _dt(days_ago=200, hours=14, minutes=30, seconds=45).isoformat()
        assert d["status"] == 0
        assert d["device_ip"] == "192.168.1.50"
        assert d["punch_type"] == "checkin"
        assert d["synced"] is True
        assert d["sync_attempts"] == 1

    def test_to_dict_with_string_timestamp(self):
        """Test to_dict handles string timestamp (if already string)"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=_dt(days_ago=365).isoformat(),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        d = record.to_dict()
        assert d["timestamp"] == _dt(days_ago=365).isoformat()

    def test_to_dict_timestamp_none(self):
        """Test to_dict with None timestamp"""
        record = AttendanceRecordDB(
            user_id="1", timestamp=None, status=0, device_ip="192.168.1.100", punch_type="checkin"
        )
        d = record.to_dict()
        assert d["timestamp"] == "None"

    def test_dataclass_equality(self):
        """Test dataclass equality comparison"""
        dt = _dt(days_ago=365)
        record1 = AttendanceRecordDB("1", dt, 0, "192.168.1.100", "checkin")
        record2 = AttendanceRecordDB("1", dt, 0, "192.168.1.100", "checkin")
        record3 = AttendanceRecordDB("2", dt, 0, "192.168.1.100", "checkin")
        assert record1 == record2
        assert record1 != record3
