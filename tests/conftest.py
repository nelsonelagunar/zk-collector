"""
Fixtures y configuración común para tests
"""

import os
from datetime import date, timedelta
from pathlib import Path
from unittest.mock import Mock

import pytest
from flask import Flask


def _day(offset: int) -> str:
    """Fecha ISO relativa a hoy — evita time-bombs por fechas hardcodeadas (MYK-466)."""
    return (date.today() + timedelta(days=offset)).isoformat()


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
        timestamp = f"{_day(0)} 08:00:00"
        status = 0

    return AttendanceData()


# --- Fixtures de la app real (create_app) para tests de UI (MYK-377) ---

os.environ.setdefault("WEBGUI_SKIP_APP_CREATE", "1")

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
STRONG_PASSWORD = "Sup3rSecret!Pass"


@pytest.fixture
def webgui_app(tmp_path, monkeypatch):
    """App de produccion (create_app) con layout Docker y todas las migraciones."""
    import shutil as _shutil

    _shutil.copytree(MIGRATIONS_DIR, tmp_path / "migrations")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DB_PATH", str(data_dir / "webgui.db"))
    monkeypatch.setenv("BUFFER_DB_PATH", str(data_dir / "buffer.db"))
    monkeypatch.setenv("WEBGUI_SECRET_KEY", "test-secret-key")
    monkeypatch.setenv("ZK_DEMO_SEED", "1")
    from src.webgui.server import create_app

    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def logged_client(webgui_app):
    """Admin autenticado: inserta la cuenta, hace login y devuelve el client."""
    webgui_app.db.insert(
        "users",
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": webgui_app.auth.hash_password(STRONG_PASSWORD),
            "full_name": "Admin Test",
            "role": "admin",
        },
    )
    client = webgui_app.test_client()
    client.post(
        "/auth/login",
        data={"username": "admin", "password": STRONG_PASSWORD},
        follow_redirects=True,
    )
    return webgui_app, client


@pytest.fixture
def user_role_client(webgui_app):
    """Usuario con rol 'user' autenticado (para probar admin_required)."""
    webgui_app.db.insert(
        "users",
        {
            "username": "normal.user",
            "email": "normal@example.com",
            "password_hash": webgui_app.auth.hash_password(STRONG_PASSWORD),
            "full_name": "Usuario Normal",
            "role": "user",
        },
    )
    client = webgui_app.test_client()
    client.post(
        "/auth/login",
        data={"username": "normal.user", "password": STRONG_PASSWORD},
        follow_redirects=True,
    )
    return webgui_app, client
