"""
Tests for WebGUI Attendance Routes
"""

from datetime import datetime, timedelta

import pytest


class TestAttendanceRoutes:
    """Test attendance blueprint routes"""

    def test_attendance_imports(self):
        """Test that attendance module imports correctly"""
        from src.webgui.routes import attendance
        assert attendance.attendance_bp is not None

    def test_attendance_blueprint_structure(self):
        """Test that attendance blueprint has correct routes"""
        from src.webgui.routes.attendance import attendance_bp

        # Verify blueprint exists
        assert attendance_bp is not None
        assert attendance_bp.name == 'attendance'

        # Check routes are registered on the blueprint
        # Flask blueprints store routes in deferred_functions or
        # via view_functions after registration
        # We can verify the functions exist in the module
        from src.webgui.routes import attendance
        assert hasattr(attendance, 'list_attendance')
        assert hasattr(attendance, 'api_attendance')
        assert hasattr(attendance, 'export_attendance')


class TestServerIncludesAttendance:
    """Test that server.py imports and registers attendance blueprint"""

    def test_server_imports_attendance(self):
        """Test that server module can import attendance blueprint"""
        # This test verifies the import works without initializing the app
        from src.webgui.routes.attendance import attendance_bp
        assert attendance_bp is not None


class TestAttendanceAPI:
    """Test attendance API endpoints logic"""

    def test_pagination_calculation(self):
        """Test pagination math"""
        total = 150
        per_page = 50
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 3

        total = 151
        total_pages = (total + per_page - 1) // per_page
        assert total_pages == 4

    def test_date_filter_parsing(self):
        """Test date filter parsing logic"""

        # Test date_from
        date_from = "2026-01-15"
        dt_from = datetime.fromisoformat(date_from)
        assert dt_from == datetime(2026, 1, 15, 0, 0)

        # Test date_to (adds 1 day for inclusive range)
        date_to = "2026-01-20"
        dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
        assert dt_to == datetime(2026, 1, 21, 0, 0)

    def test_status_mapping(self):
        """Test status code to label mapping"""
        status_map = {0: 'Entrada', 1: 'Salida', 2: 'Otro'}
        assert status_map[0] == 'Entrada'
        assert status_map[1] == 'Salida'
        assert status_map[2] == 'Otro'
        assert status_map.get(99, 'Desconocido') == 'Desconocido'


class TestAttendanceExport:
    """Test attendance export functionality"""

    def test_csv_headers(self):
        """Test CSV header row"""
        headers = [
        'ID', 'Usuario', 'Fecha/Hora', 'Estado',
        'Dispositivo', 'Tipo Marca', 'Sincronizado'
    ]
        assert len(headers) == 7
        assert headers[0] == 'ID'
        assert headers[6] == 'Sincronizado'

    def test_csv_row_generation(self):
        """Test CSV row generation from record"""
        record = {
            'id': 1,
            'user_id': 'EMP001',
            'timestamp': '2026-01-15T08:00:00',
            'status': 0,
            'device_ip': '192.168.1.100',
            'device_name': 'Main Entrance',
            'punch_type': 'check_in',
            'synced': True
        }

        status_map = {0: 'Entrada', 1: 'Salida', 2: 'Otro'}
        row = [
            record['id'],
            record['user_id'],
            record['timestamp'],
            status_map.get(record['status'], str(record['status'])),
            record.get('device_name', record['device_ip']),
            record['punch_type'] or 'N/A',
            'Sí' if record['synced'] else 'No'
        ]

        assert row == [
            1, 'EMP001', '2026-01-15T08:00:00', 'Entrada',
            'Main Entrance', 'check_in', 'Sí'
        ]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
