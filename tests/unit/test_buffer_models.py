"""
Unit tests for Buffer Models
"""

from datetime import datetime

from src.buffer.models import AttendanceRecordDB


class TestAttendanceRecordDB:
    """Tests for AttendanceRecordDB model"""

    def test_init(self):
        """Test initialization"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 3, 3, 8, 0, 0),
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada"
        )

        assert record.user_id == "1"
        assert record.timestamp == datetime(2026, 3, 3, 8, 0, 0)
        assert record.status == 0
        assert record.device_ip == "192.168.1.101"
        assert record.punch_type == "entrada"
        assert record.synced is False
        assert record.sync_attempts == 0

    def test_init_with_optional_fields(self):
        """Test initialization with optional fields"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 3, 3, 8, 0, 0),
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada",
            synced=True,
            sync_attempts=3
        )

        assert record.synced is True
        assert record.sync_attempts == 3

    def test_to_dict_with_datetime(self):
        """Test to_dict with datetime object"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 3, 3, 8, 0, 0),
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada"
        )

        data = record.to_dict()

        assert data['user_id'] == "1"
        assert data['timestamp'] == "2026-03-03T08:00:00"
        assert data['status'] == 0
        assert data['device_ip'] == "192.168.1.101"
        assert data['punch_type'] == "entrada"
        assert data['synced'] is False
        assert data['sync_attempts'] == 0

    def test_to_dict_with_string_timestamp(self):
        """Test to_dict with string timestamp"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp="2026-03-03T08:00:00",
            status=0,
            device_ip="192.168.1.101",
            punch_type="entrada"
        )

        data = record.to_dict()

        assert data['timestamp'] == "2026-03-03T08:00:00"
