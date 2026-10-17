"""
Tests de integración del WebGUI DB — MYK-250

Valida el contrato de esquema unificado (migrations/001_initial_schema.sql):
- La DB del WebGUI se inicializa desde las migraciones reales.
- GET /attendance/api/devices responde 200 con columnas del esquema real
  (address, is_enabled) — no ip/enabled.
- GET /devices/ renderiza 200.
- El empaquetado Docker copia migrations/ (root cause del 500 en deploy).
"""

import shutil
import sqlite3
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))


@pytest.fixture
def webgui_env(tmp_path, monkeypatch):
    """Replica el layout del contenedor: <root>/data/webgui.db + <root>/migrations/"""
    data_dir = tmp_path / "data"
    data_dir.mkdir()
    shutil.copytree(REPO_ROOT / "migrations", tmp_path / "migrations")
    db_path = data_dir / "webgui.db"

    monkeypatch.setenv("WEBGUI_DB_PATH", str(db_path))
    monkeypatch.setenv("BUFFER_DB_PATH", str(data_dir / "buffer.db"))
    monkeypatch.setenv("WEBGUI_SKIP_APP_CREATE", "1")
    return db_path


def _initialize_db(db_path):
    from src.webgui.database import Database

    db = Database(db_path)
    db.initialize()
    return db


def _seed_device(db_path, name="Reloj Test", address="192.168.1.50",
                 is_enabled=1, status="unknown"):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO devices (name, address, port, password, timeout, "
            "protocol, status, is_enabled) VALUES (?, ?, ?, ?, ?, ?, ?, ?)",
            (name, address, 4370, 0, 5, "tcp", status, is_enabled),
        )


class TestWebguiDbSchemaContract:
    """El esquema de devices tiene UNA sola verdad: migrations/001 (address/is_enabled)"""

    def test_migration_defines_address_and_is_enabled(self):
        sql = (REPO_ROOT / "migrations" / "001_initial_schema.sql").read_text()
        assert "address TEXT NOT NULL" in sql
        assert "is_enabled" in sql
        assert "ip " not in sql.replace("device_ip", "").replace("smtp", "")

    def test_dockerfile_copies_migrations(self):
        """Root cause del 500 en deploy: la imagen no incluía migrations/"""
        dockerfile = (REPO_ROOT / "Dockerfile").read_text()
        assert "COPY migrations/ migrations/" in dockerfile

    def test_entrypoint_applies_migrations(self):
        """El entrypoint debe correr las migraciones sobre el WebGUI DB al arrancar"""
        entrypoint = (REPO_ROOT / "docker-entrypoint.sh").read_text()
        assert "apply_schema_migrations" in entrypoint
        assert 'sqlite3 "$WEBGUI_DB_PATH" < "$migration"' in entrypoint


class TestApiDevicesEndpoint:
    def test_api_devices_200_with_schema_columns(self, webgui_env):
        _initialize_db(webgui_env)
        _seed_device(webgui_env, name="Reloj Puerta", address="192.168.1.50")
        _seed_device(webgui_env, name="Reloj Off", address="192.168.1.51", is_enabled=0)

        from src.webgui.server import create_app

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/attendance/api/devices")
        assert resp.status_code == 200, f"esperado 200, got {resp.status_code}"
        devices = resp.get_json()["devices"]
        assert len(devices) == 1, "solo dispositivos habilitados (is_enabled=1)"
        assert devices[0]["name"] == "Reloj Puerta"
        assert devices[0]["address"] == "192.168.1.50"
        assert devices[0]["is_enabled"] == 1

    def test_devices_page_renders_200(self, webgui_env):
        _initialize_db(webgui_env)
        _seed_device(webgui_env, name="Reloj Puerta", address="192.168.1.50")

        from src.webgui.server import create_app

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/devices/")
        assert resp.status_code == 200, f"esperado 200, got {resp.status_code}"
        assert b"Reloj Puerta" in resp.data


class TestForgotPassword:
    def test_forgot_password_renders_200(self, webgui_env):
        """MYK-250: /auth/forgot-password daba 500 por template faltante"""
        _initialize_db(webgui_env)

        from src.webgui.server import create_app

        app = create_app()
        app.config["TESTING"] = True
        client = app.test_client()

        resp = client.get("/auth/forgot-password")
        assert resp.status_code == 200, f"esperado 200, got {resp.status_code}"
        assert b"Recuperar" in resp.data
