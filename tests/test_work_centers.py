"""
Tests for work_centers feature (CT-1, MYK-427)
"""

from datetime import datetime

import pytest

from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository
from src.webgui.database import Database
from src.zk_client.attendance import AttendanceRecord


class TestWorkCentersModels:
    """Tests for work_center field in models"""

    def test_attendance_record_db_with_work_center(self):
        """Test AttendanceRecordDB with work_center field"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
            work_center="Planta Norte",
        )
        assert record.work_center == "Planta Norte"
        d = record.to_dict()
        assert d["work_center"] == "Planta Norte"

    def test_attendance_record_db_without_work_center(self):
        """Test AttendanceRecordDB without work_center (backwards compatible)"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        assert record.work_center is None
        d = record.to_dict()
        assert d["work_center"] is None

    def test_attendance_record_with_work_center(self):
        """Test AttendanceRecord (zk_client) with work_center field"""
        record = AttendanceRecord(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            work_center="Planta Norte",
        )
        assert record.work_center == "Planta Norte"
        d = record.to_dict()
        assert d["work_center"] == "Planta Norte"

    def test_attendance_record_from_zk_attendance_with_work_center(self):
        """Test from_zk_attendance class method with work_center"""
        class MockAttendance:
            user_id = "1"
            timestamp = datetime(2026, 1, 1, 8, 0, 0)
            status = 0

        record = AttendanceRecord.from_zk_attendance(
            MockAttendance(), "192.168.1.100", work_center="Planta Norte"
        )
        assert record.work_center == "Planta Norte"


class TestBufferRepositoryWorkCenter:
    """Tests for BufferRepository work_center handling"""

    @pytest.fixture
    def temp_db(self, tmp_path):
        """Create a temporary buffer database"""
        db_path = tmp_path / "test_buffer.db"
        repo = BufferRepository(db_path)
        yield repo

    def test_add_record_with_work_center(self, temp_db):
        """Test adding record with work_center"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
            work_center="Planta Norte",
        )
        inserted = temp_db.add_records([record])
        assert inserted == 1

        # Verify it was stored
        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 1
        assert unsynced[0]["work_center"] == "Planta Norte"

    def test_add_record_without_work_center(self, temp_db):
        """Test adding record without work_center (backwards compatible)"""
        record = AttendanceRecordDB(
            user_id="1",
            timestamp=datetime(2026, 1, 1, 8, 0, 0),
            status=0,
            device_ip="192.168.1.100",
            punch_type="checkin",
        )
        inserted = temp_db.add_records([record])
        assert inserted == 1

        # Verify it was stored with None work_center
        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 1
        assert unsynced[0]["work_center"] is None

    def test_multiple_records_different_work_centers(self, temp_db):
        """Test multiple records with different work_centers"""
        records = [
            AttendanceRecordDB(
                user_id="1",
                timestamp=datetime(2026, 1, 1, 8, 0, 0),
                status=0,
                device_ip="192.168.1.100",
                punch_type="checkin",
                work_center="Planta Norte",
            ),
            AttendanceRecordDB(
                user_id="2",
                timestamp=datetime(2026, 1, 1, 9, 0, 0),
                status=0,
                device_ip="192.168.1.101",
                punch_type="checkin",
                work_center="Sucursal Tijuana",
            ),
            AttendanceRecordDB(
                user_id="3",
                timestamp=datetime(2026, 1, 1, 10, 0, 0),
                status=0,
                device_ip="192.168.1.102",
                punch_type="checkin",
            ),
        ]
        inserted = temp_db.add_records(records)
        assert inserted == 3

        unsynced = temp_db.get_unsynced_records()
        assert len(unsynced) == 3
        work_centers = {r["work_center"] for r in unsynced}
        assert "Planta Norte" in work_centers
        assert "Sucursal Tijuana" in work_centers
        assert None in work_centers


class TestWorkCentersDatabase:
    """Tests for work_centers database operations (webgui.db)"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a test database with work_centers and devices tables"""
        db_path = tmp_path / "webgui.db"
        db = Database(db_path)
        # Create work_centers table directly (migrations will handle it in production)
        db.execute("""
            CREATE TABLE IF NOT EXISTS work_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                rfc_pattern TEXT,
                imss_registro_patronal TEXT,
                direccion TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create devices table with work_center_id
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                zone TEXT,
                address TEXT NOT NULL,
                port INTEGER DEFAULT 4370,
                password INTEGER DEFAULT 0,
                timeout INTEGER DEFAULT 5,
                protocol TEXT DEFAULT 'tcp',
                status TEXT DEFAULT 'unknown',
                is_enabled BOOLEAN DEFAULT 1,
                firmware_version TEXT,
                serial_number TEXT,
                last_seen DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                work_center_id INTEGER
            )
        """)
        yield db

    def test_create_work_center(self, db):
        """Test creating a work center"""
        wc_id = db.create_work_center({
            "nombre": "Planta Norte",
            "rfc_pattern": "ABC123456XYZ",
            "imss_registro_patronal": "12345678901",
            "direccion": "Av. Principal 123, Col. Centro",
        })
        assert wc_id > 0

        wc = db.get_work_center_by_id(wc_id)
        assert wc is not None
        assert wc["nombre"] == "Planta Norte"
        assert wc["rfc_pattern"] == "ABC123456XYZ"
        assert wc["imss_registro_patronal"] == "12345678901"
        assert wc["direccion"] == "Av. Principal 123, Col. Centro"

    def test_get_work_centers(self, db):
        """Test getting all work centers"""
        db.create_work_center({"nombre": "Planta Norte"})
        db.create_work_center({"nombre": "Sucursal Tijuana"})

        wcs = db.get_work_centers()
        assert len(wcs) == 2
        nombres = [wc["nombre"] for wc in wcs]
        assert "Planta Norte" in nombres
        assert "Sucursal Tijuana" in nombres

    def test_update_work_center(self, db):
        """Test updating a work center"""
        wc_id = db.create_work_center({"nombre": "Planta Norte"})

        updated = db.update_work_center(wc_id, {
            "nombre": "Planta Sur",
            "direccion": "Nueva direccion",
        })
        assert updated == 1

        wc = db.get_work_center_by_id(wc_id)
        assert wc["nombre"] == "Planta Sur"
        assert wc["direccion"] == "Nueva direccion"

    def test_delete_work_center_no_devices(self, db):
        """Test deleting a work center with no linked devices"""
        wc_id = db.create_work_center({"nombre": "Planta Norte"})

        deleted = db.delete_work_center(wc_id)
        assert deleted == 1

        wc = db.get_work_center_by_id(wc_id)
        assert wc is None

    def test_delete_work_center_with_devices_raises(self, db):
        """Test deleting a work center with linked devices raises error"""
        wc_id = db.create_work_center({"nombre": "Planta Norte"})

        # Create a device linked to this work center
        db.insert("devices", {
            "name": "Test Device",
            "address": "192.168.1.100",
            "work_center_id": wc_id,
        })

        with pytest.raises(ValueError, match="dispositivos vinculados"):
            db.delete_work_center(wc_id)


class TestDevicesWithWorkCenter:
    """Tests for devices with work_center field"""

    @pytest.fixture
    def db(self, tmp_path):
        """Create a test database with devices and work_centers tables"""
        db_path = tmp_path / "webgui.db"
        db = Database(db_path)
        # Create work_centers table directly
        db.execute("""
            CREATE TABLE IF NOT EXISTS work_centers (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                nombre TEXT NOT NULL,
                rfc_pattern TEXT,
                imss_registro_patronal TEXT,
                direccion TEXT,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        """)
        # Create devices table with work_center_id
        db.execute("""
            CREATE TABLE IF NOT EXISTS devices (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                name TEXT NOT NULL,
                location TEXT,
                zone TEXT,
                address TEXT NOT NULL,
                port INTEGER DEFAULT 4370,
                password INTEGER DEFAULT 0,
                timeout INTEGER DEFAULT 5,
                protocol TEXT DEFAULT 'tcp',
                status TEXT DEFAULT 'unknown',
                is_enabled BOOLEAN DEFAULT 1,
                firmware_version TEXT,
                serial_number TEXT,
                last_seen DATETIME,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                work_center_id INTEGER
            )
        """)
        yield db

    def test_device_with_work_center_id(self, db):
        """Test device with work_center_id FK"""
        wc_id = db.create_work_center({"nombre": "Planta Norte"})

        device_id = db.insert("devices", {
            "name": "Entrada Principal",
            "address": "192.168.1.100",
            "work_center_id": wc_id,
        })

        device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        assert device["work_center_id"] == wc_id

    def test_device_without_work_center(self, db):
        """Test device without work_center (nullable FK)"""
        device_id = db.insert("devices", {
            "name": "Entrada Principal",
            "address": "192.168.1.100",
        })

        device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))
        assert device["work_center_id"] is None
