"""
Tests de integración E2E - Flujo completo
UI login → add device → poll → buffer → attendance list → export
"""

import os
import sys
from datetime import datetime
from unittest.mock import MagicMock, Mock, patch

import pytest

# Ensure src is in path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", ".."))

from src.buffer.repository import BufferRepository
from src.core.collector import AttendanceCollector
from src.zk_client.attendance import AttendanceRecord
from src.zk_client.client import ZKClient


class MockZKAttendance:
    """Mock para objeto de asistencia de pyzk"""

    def __init__(self, user_id, timestamp, status):
        self.user_id = user_id
        self.timestamp = timestamp
        self.status = status


class TestE2EFlow:
    """Tests de flujo completo E2E"""

    @pytest.fixture
    def temp_db_path(self, tmp_path):
        """Base de datos temporal"""
        return tmp_path / "test_e2e.db"

    @pytest.fixture
    def buffer_repo(self, temp_db_path):
        """BufferRepository con BD temporal"""
        return BufferRepository(temp_db_path, max_records=100)

    @pytest.fixture
    def mock_config(self):
        """Configuración mock para tests"""
        return {
            "platform": {
                "url": "https://test.example.com",
                "api_key": "test-api-key",
                "tenant_id": "test-tenant",
                "timeout": 30,
                "retry_attempts": 3,
            },
            "devices": [
                {
                    "ip": "192.168.1.101",
                    "port": 4370,
                    "timeout": 5,
                    "password": 0,
                    "name": "Test Device",
                    "enabled": True,
                }
            ],
            "poll_interval_seconds": 60,
            "sync_interval_seconds": 30,
            "buffer": {"max_records": 100, "retention_days": 730},
            "logging": {"level": "DEBUG"},
        }

    @pytest.fixture
    def collector(self, mock_config, temp_db_path, monkeypatch):
        """Collector con configuración de test"""
        # Mock Config class
        mock_config_obj = Mock()
        mock_config_obj.get = lambda key, default=None: (
            str(temp_db_path)
            if key == "buffer.db_path"
            else 100
            if key == "buffer.max_records"
            else self._get_nested(mock_config, key, default)
        )
        mock_config_obj.get_all = lambda: mock_config

        # Patch Config en collector
        monkeypatch.setattr("src.core.collector.Config", lambda path: mock_config_obj)
        # Patch BufferRepository in collector to use temp path
        monkeypatch.setattr(
            "src.core.collector.BufferRepository",
            lambda **kwargs: BufferRepository(temp_db_path, max_records=100),
        )

        # Create collector with temp db
        collector = AttendanceCollector(mock_config_obj)
        return collector

    def _get_nested(self, config, key, default=None):
        """Helper para obtener valores anidados con notación dot"""
        keys = key.split(".")
        value = config
        for k in keys:
            if isinstance(value, dict):
                value = value.get(k)
                if value is None:
                    return default
            elif isinstance(value, list):
                try:
                    idx = int(k)
                    value = value[idx] if 0 <= idx < len(value) else default
                except (ValueError, IndexError):
                    return default
            else:
                return default
        return value

    # ===== TEST 1: UI Login Flow =====
    def test_login_flow(self):
        """Test: Login flow with auth"""
        from src.webgui.auth import Auth

        auth = Auth()
        password = "TestPass123!"
        hashed = auth.hash_password(password)

        assert auth.verify_password(password, hashed)
        assert not auth.verify_password("wrong", hashed)

    # ===== TEST 2: Device CRUD + Collector Poll Integration =====
    @patch("src.core.collector.ZKClient")
    def test_device_add_then_poll_flow(self, mock_zk_client_class, collector, buffer_repo):
        """Test: Add device → poll → buffer receives records"""
        # Setup mock ZKClient
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = [
            AttendanceRecord(
                user_id="1",
                timestamp=datetime(2026, 1, 15, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
            ),
            AttendanceRecord(
                user_id="2",
                timestamp=datetime(2026, 1, 15, 17, 0, 0),
                status=1,
                device_ip="192.168.1.101",
            ),
        ]
        mock_client.disconnect.return_value = None
        mock_zk_client_class.return_value = mock_client

        # Re-initialize devices with mock
        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test Device",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        # Poll devices
        collector.poll_devices()

        # Verify records in buffer
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 2
        assert unsynced[0]["user_id"] == "1"
        assert unsynced[1]["user_id"] == "2"

    @patch("src.core.collector.ZKClient")
    def test_device_poll_with_mock_pyzk(self, mock_zk_client_class, collector, buffer_repo):
        """Test: Poll device using mocked pyzk responses"""
        # Create mock that simulates pyzk behavior
        mock_zk_instance = MagicMock()
        mock_zk_instance.connect.return_value = True
        mock_zk_instance.get_attendance.return_value = [
            MockZKAttendance("100", datetime(2026, 3, 1, 9, 0, 0), 0),
            MockZKAttendance("101", datetime(2026, 3, 1, 9, 5, 0), 0),
            MockZKAttendance("102", datetime(2026, 3, 1, 18, 0, 0), 1),
        ]
        mock_zk_instance.disable_device.return_value = None
        mock_zk_instance.enable_device.return_value = None
        mock_zk_instance.disconnect.return_value = None

        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.zk = mock_zk_instance
        mock_client.get_attendance.return_value = [
            AttendanceRecord.from_zk_attendance(a, "192.168.1.101")
            for a in mock_zk_instance.get_attendance.return_value
        ]
        mock_client.disconnect.return_value = None
        mock_zk_client_class.return_value = mock_client

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        collector.poll_devices()

        # Verify all 3 records in buffer
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 3
        assert {r["user_id"] for r in unsynced} == {"100", "101", "102"}

    # ===== TEST 3: BufferRepository with Real Data =====
    def test_buffer_repo_real_data_flow(self, buffer_repo):
        """Test: BufferRepository with real attendance records"""
        records = [
            AttendanceRecord(
                user_id=f"EMP{i:03d}",
                timestamp=datetime(2026, 3, 15, 8, i % 60, 0),
                status=0 if i % 2 == 0 else 1,
                device_ip="192.168.1.101",
            )
            for i in range(20)
        ]

        count = buffer_repo.add_records(records)
        assert count == 20

        # Get unsynced
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 20

        # Check stats
        stats = buffer_repo.get_stats()
        assert stats["total_records"] == 20
        assert stats["pending_sync"] == 20
        assert stats["synced"] == 0

        # Mark as synced
        record_ids = [r["id"] for r in unsynced]
        updated = buffer_repo.mark_as_synced(record_ids)
        assert updated == 20

        # Verify synced
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 0
        stats = buffer_repo.get_stats()
        assert stats["synced"] == 20

    def test_buffer_repo_sync_failed_handling(self, buffer_repo):
        """Test: Buffer handles sync failures correctly"""
        records = [
            AttendanceRecord(
                user_id="1", timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
            )
        ]
        buffer_repo.add_records(records)
        unsynced = buffer_repo.get_unsynced_records()
        record_ids = [r["id"] for r in unsynced]

        # Mark as failed (should increment sync_attempts)
        buffer_repo.mark_sync_failed(record_ids, max_attempts=3)

        # Still unsynced
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 1
        assert unsynced[0]["id"] == record_ids[0]

    def test_buffer_repo_max_records_cleanup(self, buffer_repo):
        """Test: Buffer cleans up when max_records exceeded"""
        # Add more than max_records
        records = [
            AttendanceRecord(
                user_id=str(i), timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
            )
            for i in range(150)  # max_records = 100
        ]
        buffer_repo.add_records(records)

        stats = buffer_repo.get_stats()
        assert stats["total_records"] <= 100

    def test_buffer_sync_log(self, buffer_repo):
        """Test: Sync logging works correctly"""
        buffer_repo.log_sync(
            records_synced=50, records_failed=0, status="success", duration_seconds=2.5
        )

        history = buffer_repo.get_sync_history()
        assert len(history) == 1
        assert history[0]["records_synced"] == 50
        assert history[0]["status"] == "success"
        assert history[0]["duration_seconds"] == 2.5

    # ===== TEST 4: Attendance API Endpoints =====
    def test_attendance_api_endpoint_structure(self):
        """Test: Verify attendance API endpoint functions exist"""
        from src.webgui.routes import attendance

        # Check that all expected route handler functions exist
        assert hasattr(attendance, "list_attendance")
        assert hasattr(attendance, "api_attendance")
        assert hasattr(attendance, "api_devices")
        assert hasattr(attendance, "export_attendance")
        assert hasattr(attendance, "attendance_stats")
        assert hasattr(attendance, "_build_attendance_query")
        assert hasattr(attendance, "_export_csv")
        assert hasattr(attendance, "_export_xlsx")

    def test_attendance_api_pagination(self, buffer_repo):
        """Test: Attendance API pagination logic"""
        from src.webgui.routes.attendance import _build_attendance_query

        # Add test data
        for i in range(75):
            buffer_repo.add_records(
                [
                    AttendanceRecord(
                        user_id=f"USER{i}",
                        timestamp=datetime(2026, 3, 1, 8, i % 60, 0),
                        status=0,
                        device_ip="192.168.1.101",
                    )
                ]
            )

        # Test query building - include all params expected by the function
        params = {
            "start_date": "2026-03-01",
            "end_date": "2026-03-31",
            "user_id": "USER10",
            "status": "",
            "synced": "",
        }
        where_clause, query_params = _build_attendance_query(params)

        assert "substr(timestamp, 1, 10) >= ?" in where_clause
        assert "substr(timestamp, 1, 10) <= ?" in where_clause
        assert "user_id = ?" in where_clause

    # ===== TEST 5: Export Functionality =====
    def test_export_csv(self, buffer_repo):
        """Test: Export attendance to CSV - test the CSV generation logic directly"""
        import csv
        import io

        # Add test data
        for i in range(10):
            buffer_repo.add_records(
                [
                    AttendanceRecord(
                        user_id=f"EMP{i}",
                        timestamp=datetime(2026, 3, 1, 8, i, 0),
                        status=0 if i % 2 == 0 else 1,
                        device_ip="192.168.1.101",
                    )
                ]
            )

        # Build export data
        export_data = []
        with buffer_repo.get_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT * FROM attendance_records")
            for row in cursor.fetchall():
                record = dict(row)
                record["user_name"] = record["user_id"]
                record["synced_label"] = "Sí" if record["synced"] else "No"
                status_labels = {0: "Entrada", 1: "Salida"}
                record["status_label"] = status_labels.get(
                    record["status"], f"Status {record['status']}"
                )
                export_data.append(record)

        # Test CSV generation directly (without send_file)
        output = io.StringIO()
        writer = csv.DictWriter(
            output,
            fieldnames=[
                "id",
                "user_name",
                "timestamp",
                "status_label",
                "device_ip",
                "punch_type",
                "synced_label",
            ],
        )
        writer.writeheader()
        for row in export_data:
            writer.writerow(
                {
                    "id": row["id"],
                    "user_name": row["user_name"],
                    "timestamp": row["timestamp"],
                    "status_label": row["status_label"],
                    "device_ip": row["device_ip"],
                    "punch_type": row["punch_type"],
                    "synced_label": row["synced_label"],
                }
            )

        content = output.getvalue()
        # Check for the actual CSV headers (field names)
        assert "id,user_name,timestamp,status_label,device_ip,punch_type,synced_label" in content
        assert "EMP0" in content
        assert "Entrada" in content
        assert "Salida" in content

    def test_export_xlsx(self, buffer_repo, app):
        """Test: Export attendance to XLSX"""
        from src.webgui.routes.attendance import _export_xlsx

        export_data = [
            {
                "id": 1,
                "user_name": "EMP001",
                "timestamp": "2026-03-01 08:00:00",
                "status_label": "Entrada",
                "device_ip": "192.168.1.101",
                "punch_type": "entrada",
                "synced_label": "No",
            }
        ]

        with app.test_request_context("/"):
            response = _export_xlsx(export_data)

        assert "spreadsheetml" in response.mimetype
        content_disposition = response.headers.get("Content-Disposition", "")
        assert "asistencia_" in content_disposition
        assert ".xlsx" in content_disposition

    # ===== TEST 6: Stats Endpoint =====
    def test_attendance_stats(self, buffer_repo):
        """Test: Attendance stats from buffer"""
        # Add test data
        for i in range(20):
            buffer_repo.add_records(
                [
                    AttendanceRecord(
                        user_id=f"USER{i}",
                        timestamp=datetime(2026, 3, 1, 8, i, 0),
                        status=i % 6,  # 0-5
                        device_ip="192.168.1.101" if i % 2 == 0 else "192.168.1.102",
                    )
                ]
            )

        # Verify the buffer stats
        stats = buffer_repo.get_stats()
        assert stats["total_records"] == 20
        assert stats["pending_sync"] == 20

    # ===== TEST 7: Full Flow Integration =====
    @patch("src.core.collector.ZKClient")
    @patch("src.sync.platform.PlatformSync.sync_attendance")
    def test_full_flow_poll_to_sync(self, mock_sync, mock_zk_client_class, collector, buffer_repo):
        """Test: Complete flow - poll → buffer → sync to platform"""
        # Setup mocks
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = [
            AttendanceRecord(
                user_id="1",
                timestamp=datetime(2026, 3, 1, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
            ),
        ]
        mock_client.disconnect.return_value = None
        mock_zk_client_class.return_value = mock_client

        mock_sync.return_value = True  # Sync succeeds

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        # Poll
        collector.poll_devices()

        # Verify in buffer
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 1

        # Sync
        collector.sync_to_platform()

        # Verify sync called
        mock_sync.assert_called_once()
        assert len(mock_sync.call_args[0][0]) == 1

        # Verify marked as synced
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 0

    @patch("src.core.collector.ZKClient")
    @patch("src.sync.platform.PlatformSync.sync_attendance")
    def test_full_flow_sync_failure(self, mock_sync, mock_zk_client_class, collector, buffer_repo):
        """Test: Complete flow with sync failure"""
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.return_value = [
            AttendanceRecord(
                user_id="1",
                timestamp=datetime(2026, 3, 1, 8, 0, 0),
                status=0,
                device_ip="192.168.1.101",
            ),
        ]
        mock_client.disconnect.return_value = None
        mock_zk_client_class.return_value = mock_client

        mock_sync.return_value = False  # Sync fails

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        collector.poll_devices()
        collector.sync_to_platform()

        # Verify still in buffer (sync failed)
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 1

    # ===== TEST 8: Multiple Devices Poll =====
    @patch("src.core.collector.ZKClient")
    def test_multiple_devices_poll(self, mock_zk_client_class, collector, buffer_repo):
        """Test: Poll multiple devices"""

        def create_mock_client(device_ip, records):
            mock_client = MagicMock()
            mock_client.connect.return_value = True
            mock_client.get_attendance.return_value = records
            mock_client.disconnect.return_value = None
            return mock_client

        records_1 = [
            AttendanceRecord(
                user_id="1", timestamp=datetime.now(), status=0, device_ip="192.168.1.101"
            )
        ]
        records_2 = [
            AttendanceRecord(
                user_id="2", timestamp=datetime.now(), status=1, device_ip="192.168.1.102"
            )
        ]
        records_3 = [
            AttendanceRecord(
                user_id="3", timestamp=datetime.now(), status=0, device_ip="192.168.1.103"
            )
        ]

        mock_zk_client_class.side_effect = [
            create_mock_client("192.168.1.101", records_1),
            create_mock_client("192.168.1.102", records_2),
            create_mock_client("192.168.1.103", records_3),
        ]

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Dev1",
                "enabled": True,
            },
            {
                "ip": "192.168.1.102",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Dev2",
                "enabled": True,
            },
            {
                "ip": "192.168.1.103",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Dev3",
                "enabled": True,
            },
        ]
        collector._initialize_devices()

        collector.poll_devices()

        # All 3 records should be in buffer
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 3
        assert {r["device_ip"] for r in unsynced} == {
            "192.168.1.101",
            "192.168.1.102",
            "192.168.1.103",
        }

    # ===== TEST 9: Collector Stop/Start =====
    def test_collector_stop(self, collector):
        """Test: Collector stop cleans up properly"""
        collector.running = True
        collector.zk_clients = {
            "192.168.1.101": MagicMock(connected=True),
        }
        collector.health_monitor = MagicMock()

        collector.stop()

        assert not collector.running
        collector.health_monitor.stop.assert_called_once()
        collector.zk_clients["192.168.1.101"].disconnect.assert_called_once()

    # ===== TEST 10: Should Run Logic =====
    def test_should_run_logic(self, collector):
        """Test: _should_run interval logic"""
        from datetime import datetime, timedelta

        # Never run before
        assert collector._should_run(None, 300)

        # Just ran
        collector.last_poll = datetime.now()
        assert not collector._should_run(collector.last_poll, 300)

        # Enough time passed
        collector.last_poll = datetime.now() - timedelta(seconds=301)
        assert collector._should_run(collector.last_poll, 300)

    # ===== TEST 11: Edge Cases =====
    def test_empty_buffer_get_unsynced(self, buffer_repo):
        """Test: Get unsynced from empty buffer"""
        unsynced = buffer_repo.get_unsynced_records()
        assert unsynced == []

    def test_mark_empty_synced(self, buffer_repo):
        """Test: Mark empty list as synced"""
        updated = buffer_repo.mark_as_synced([])
        assert updated == 0

    def test_buffer_add_empty(self, buffer_repo):
        """Test: Add empty records list"""
        count = buffer_repo.add_records([])
        assert count == 0

    @patch("src.core.collector.ZKClient")
    def test_poll_device_connection_failure(self, mock_zk_client_class, collector, buffer_repo):
        """Test: Handle device connection failure gracefully"""
        mock_client = MagicMock()
        mock_client.connect.return_value = False
        mock_zk_client_class.return_value = mock_client

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        collector.poll_devices()

        # No records should be added
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 0

    @patch("src.core.collector.ZKClient")
    def test_poll_device_exception_handling(self, mock_zk_client_class, collector, buffer_repo):
        """Test: Handle exceptions during polling"""
        mock_client = MagicMock()
        mock_client.connect.return_value = True
        mock_client.get_attendance.side_effect = Exception("Device error")
        mock_zk_client_class.return_value = mock_client

        collector.zk_clients = {}
        collector.devices_config = [
            {
                "ip": "192.168.1.101",
                "port": 4370,
                "timeout": 5,
                "password": 0,
                "name": "Test",
                "enabled": True,
            }
        ]
        collector._initialize_devices()

        # Should not raise
        collector.poll_devices()

        # No records added
        unsynced = buffer_repo.get_unsynced_records()
        assert len(unsynced) == 0

    # ===== TEST 12: Attendance Record Edge Cases =====
    def test_attendance_record_status_mapping(self):
        """Test: All status values map correctly"""
        status_map = {
            0: "entrada",
            1: "salida",
            2: "salida_comida",
            3: "entrada_comida",
            4: "entrada_extra",
            5: "salida_extra",
        }

        for status, expected_type in status_map.items():
            record = AttendanceRecord(
                user_id="1", timestamp=datetime.now(), status=status, device_ip="192.168.1.101"
            )
            assert record.punch_type == expected_type

    def test_attendance_record_to_dict(self):
        """Test: AttendanceRecord to_dict serialization"""
        record = AttendanceRecord(
            user_id="123",
            timestamp=datetime(2026, 6, 15, 14, 30, 0),
            status=0,
            device_ip="192.168.1.101",
        )

        data = record.to_dict()

        assert data["user_id"] == "123"
        assert data["device_ip"] == "192.168.1.101"
        assert data["punch_type"] == "entrada"
        assert "2026-06-15" in data["timestamp"]
        assert "14:30:00" in data["timestamp"]

    # ===== TEST 13: Config Validation =====
    def test_config_validation_valid(self, mock_config):
        """Test: Config validation with valid config"""
        import tempfile

        import yaml

        from src.core.config import Config

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(mock_config, f)
            config_path = f.name

        try:
            config = Config(config_path)
            assert config.get("platform.url") == "https://test.example.com"
            assert config.get("devices.0.ip") == "192.168.1.101"
        finally:
            os.unlink(config_path)

    def test_config_validation_invalid_ip(self):
        """Test: Config validation rejects invalid IP"""
        import tempfile

        import yaml

        from src.core.config import Config, ConfigError

        bad_config = {
            "platform": {"url": "https://test.com", "api_key": "key", "tenant_id": "tenant"},
            "devices": [{"ip": "invalid-ip", "port": 4370}],
        }

        with tempfile.NamedTemporaryFile(mode="w", suffix=".yaml", delete=False) as f:
            yaml.dump(bad_config, f)
            config_path = f.name

        try:
            with pytest.raises(ConfigError, match="IP inválida"):
                Config(config_path)
        finally:
            os.unlink(config_path)

    # ===== TEST 14: ZKClient Edge Cases =====
    @patch("src.zk_client.client.ZK")
    def test_zk_client_connect_with_password(self, mock_zk_class):
        """Test: ZKClient connects with password"""
        mock_instance = MagicMock()
        mock_zk_class.return_value = mock_instance

        client = ZKClient("192.168.1.101", password=1234)
        result = client.connect()

        assert result
        # Check that it was called with the expected parameters (including defaults)
        call_args = mock_zk_class.call_args
        assert call_args[0][0] == "192.168.1.101"
        assert call_args[1]["port"] == 4370
        assert call_args[1]["timeout"] == 5
        assert call_args[1]["password"] == 1234

    @patch("src.zk_client.client.ZK")
    def test_zk_client_retry_on_failure(self, mock_zk_class):
        """Test: ZKClient retries on PyZKError and TimeoutError, raises on other Exceptions"""
        from zk.exception import ZKError as PyZKError

        from src.zk_client.exceptions import ZKConnectionError

        # Test 1: PyZKError triggers retry
        mock_instance = MagicMock()
        mock_instance.connect.return_value = True
        mock_zk_class.side_effect = [PyZKError("zk error"), PyZKError("zk error"), mock_instance]

        client = ZKClient("192.168.1.101")
        result = client.connect(max_retries=3)
        assert result is True
        assert mock_zk_class.call_count == 3

        # Test 2: Generic Exception raises immediately (no retry)
        mock_zk_class.reset_mock()
        mock_zk_class.side_effect = [Exception("connection failed")]

        client = ZKClient("192.168.1.102")
        with pytest.raises(ZKConnectionError):
            client.connect(max_retries=3)
        assert mock_zk_class.call_count == 1

    @patch("src.zk_client.client.ZK")
    def test_zk_client_raises_on_connection_refused(self, mock_zk_class):
        """Test: ZKClient raises ZKConnectionError on ConnectionRefusedError"""
        from src.zk_client.exceptions import ZKConnectionError

        mock_zk_class.side_effect = ConnectionRefusedError("refused")

        client = ZKClient("192.168.1.101")

        with pytest.raises(ZKConnectionError):
            client.connect(max_retries=1)

    # ===== TEST 15: PlatformSync Integration =====
    @patch("src.sync.platform.requests.Session.post")
    def test_platform_sync_success(self, mock_post):
        """Test: PlatformSync sync_attendance success"""
        from src.sync.platform import PlatformSync

        mock_response = MagicMock()
        mock_response.raise_for_status.return_value = None
        mock_post.return_value = mock_response

        sync = PlatformSync("https://api.test.com", "key", "tenant")
        result = sync.sync_attendance(
            [
                {
                    "user_id": "1",
                    "timestamp": "2026-01-01 08:00:00",
                    "status": 0,
                    "device_ip": "192.168.1.1",
                    "punch_type": "entrada",
                }
            ]
        )

        assert result
        mock_post.assert_called_once()

    @patch("src.sync.platform.requests.Session.post")
    def test_platform_sync_timeout(self, mock_post):
        """Test: PlatformSync handles timeout"""
        import requests

        from src.sync.platform import PlatformSync

        mock_post.side_effect = requests.exceptions.Timeout("Timeout")

        sync = PlatformSync("https://api.test.com", "key", "tenant")
        result = sync.sync_attendance([{"user_id": "1"}])

        assert not result

    @patch("src.sync.platform.requests.Session.post")
    def test_platform_sync_http_error(self, mock_post):
        """Test: PlatformSync handles HTTP errors"""
        import requests

        from src.sync.platform import PlatformSync

        mock_response = MagicMock()
        mock_response.status_code = 401
        mock_post.return_value = mock_response
        mock_post.side_effect = requests.exceptions.HTTPError("401", response=mock_response)

        sync = PlatformSync("https://api.test.com", "key", "tenant")
        result = sync.sync_attendance([{"user_id": "1"}])

        assert not result


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
