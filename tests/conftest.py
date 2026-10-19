"""
Fixtures y configuración común para tests
"""

from unittest.mock import Mock

import pytest
from flask import Flask


@pytest.fixture
def app():
    """Flask app para tests que requieren contexto de aplicación"""
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    with app.app_context():
        yield app


@pytest.fixture
def client(app):
    """Test client for Flask app"""
    return app.test_client()


@pytest.fixture
def sample_config_data():
    """Datos de configuración de ejemplo para tests"""
    return {
        "platform": {
            "url": "https://test.example.com",
            "api_key": "test-api-key",
            "tenant_id": "test-tenant-id",
            "timeout": 30,
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
        "poll_interval_seconds": 300,
        "sync_interval_seconds": 60,
    }


@pytest.fixture
def temp_config_file(tmp_path, sample_config_data):
    """Crear archivo de configuración temporal"""
    import yaml

    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(sample_config_data, f)
    return config_file


@pytest.fixture
def mock_zk_device():
    """Mock para dispositivo ZK"""
    mock = Mock()
    mock.connect.return_value = True
    mock.disconnect.return_value = None
    mock.disable_device.return_value = None
    mock.enable_device.return_value = None
    mock.get_attendance.return_value = []
    mock.get_firmware_version.return_value = "6.60"
    mock.get_serialnumber.return_value = "TEST123"
    return mock


@pytest.fixture
def sample_attendance_record():
    """Registro de asistencia de ejemplo"""

    class AttendanceData:
        user_id = "1"
        timestamp = "2026-03-03 08:00:00"
        status = 0

    return AttendanceData()
