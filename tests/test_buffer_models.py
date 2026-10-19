"""
Unit tests for buffer models module
"""

from datetime import datetime

from src.buffer.models import AttendanceRecordDB


class TestAttendanceRecordDB:
    """Tests for AttendanceRecordDB dataclass"""

    def test_init_required_fields(self):
        """Test creating AttendanceRecordDB with required fields"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        assert record.user_id == "1"
        assert record.timestamp == datetime(2026, 1, 1, 8, 0, 0)
        assert record.status == 0
        assert record.device_ip == "192.168.1.100"
        assert record.punch_type == "checkin"
        assert record.synced is False  # default
        assert record.sync_attempts == 0  # default

    def test_init_with_optional_fields(self):
        """Test creating AttendanceRecordDB with optional fields"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
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
            timestamp=datetime(2026, 3, 15, 14, 30, 45),
            status=0,
            device_ip="192.168.1.50",
            punch_type="checkin",
            synced=True,
            sync_attempts=1,
        )
        d = record.to_dict()
        assert d["user_id"] == "123"
        assert d["timestamp"] == "2026-03-15T14:30:45"
        assert d["status"] == 0
        assert d["device_ip"] == "192.168.1.50"
        assert d["punch_type"] == "checkin"
        assert d["synced"] is True
        assert d["sync_attempts"] == 1

    def test_to_dict_with_string_timestamp(self):
        """Test to_dict handles string timestamp (if already string)"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp="2026-01-01T08:00:00",  # string timestamp
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        d = record.to_dict()
        assert d["timestamp"] == "2026-01-01T08:00:00"

    def test_to_dict_timestamp_none(self):
        """Test to_dict with None timestamp"""
        record = AttendanceRecordDB(
            user_id="1", timestamp=None, status=0, device_ip="192.168.1.100", punch_type="checkin"
        )
        d = record.to_dict()
        assert d["timestamp"] == "None"

    def test_dataclass_equality(self):
        """Test dataclass equality comparison"""
        dt = datetime(2026, 1, 1, 8, 0, 0)
        record1 = AttendanceRecordDB("1", dt, 0, "192.168.1.100", "checkin")
        record2 = AttendanceRecordDB("1", dt, 0, "192.168.1.100", "checkin")
        record3 = AttendanceRecordDB("2", dt, 0, "192.168.1.100", "checkin")
        assert record1 == record2
        assert record1 != record3
