"""
Tests unit del collector — MYK-250 criterio 3

El collector debe leer los devices desde la WebGUI DB (fuente unica de
verdad, MYK-172/210) con cache TTL de 60s. Regresión: el commit 57cd695
(lint pass) eliminó _load_devices_from_webgui_db; estos tests la detectan.
"""

import sqlite3
import sys
from pathlib import Path
from unittest.mock import Mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT))

from src.core.collector import AttendanceCollector  # noqa: E402


def _create_webgui_db(db_path):
    """Crea la DB del WebGUI con el esquema REAL de migrations/001"""
    sql = (REPO_ROOT / "migrations" / "001_initial_schema.sql").read_text()
    with sqlite3.connect(db_path) as conn:
        conn.executescript(sql)


def _insert_device(db_path, name, address, is_enabled):
    with sqlite3.connect(db_path) as conn:
        conn.execute(
            "INSERT INTO devices (name, address, port, password, timeout, "
            "protocol, status, is_enabled) VALUES (?, ?, 4370, 0, 5, 'tcp', 'unknown', ?)",
            (name, address, is_enabled),
        )


@pytest.fixture
def webgui_db(tmp_path, monkeypatch):
    db_path = tmp_path / "webgui.db"
    _create_webgui_db(db_path)
    monkeypatch.setenv("WEBGUI_DB_PATH", str(db_path))
    return db_path


@pytest.fixture
def collector(tmp_path, monkeypatch):
    from src.buffer.repository import BufferRepository

    buffer_path = tmp_path / "buffer.db"
    config = Mock()
    config.get = lambda key, default=None: {
        "buffer.db_path": str(buffer_path),
        "platform.url": "https://test.example.com",
        "platform.api_key": "test-api-key",
        "platform.tenant_id": "test-tenant",
    }.get(key, default)
    monkeypatch.setattr(
        "src.core.collector.BufferRepository",
        lambda **kwargs: BufferRepository(buffer_path, max_records=100),
    )
    return AttendanceCollector(config)


class TestCollectorLoadsDevicesFromWebguiDb:
    def test_loads_enabled_devices(self, collector, webgui_db):
        _insert_device(webgui_db, "Reloj Puerta", "192.168.1.50", 1)
        _insert_device(webgui_db, "Reloj Off", "192.168.1.51", 0)

        devices = collector._load_devices_from_webgui_db()

        assert len(devices) == 1
        assert devices[0]["name"] == "Reloj Puerta"
        assert devices[0]["ip"] == "192.168.1.50"
        assert devices[0]["port"] == 4370

    def test_missing_db_returns_empty_list(self, collector, tmp_path, monkeypatch):
        monkeypatch.setenv("WEBGUI_DB_PATH", str(tmp_path / "nope.db"))
        assert collector._load_devices_from_webgui_db() == []

    def test_ttl_cache_avoids_rereading_db(self, collector, webgui_db):
        _insert_device(webgui_db, "Reloj Puerta", "192.168.1.50", 1)

        first = collector._load_devices_from_webgui_db()
        assert len(first) == 1

        # Nuevo device visible en DB pero el cache TTL (60s) aún sirve el viejo
        _insert_device(webgui_db, "Reloj Nuevo", "192.168.1.99", 1)
        cached = collector._load_devices_from_webgui_db()
        assert len(cached) == 1

        # Cache expirado -> ve el nuevo device
        collector._devices_cache_ts = 0
        refreshed = collector._load_devices_from_webgui_db()
        assert len(refreshed) == 2

    def test_initialize_devices_prefers_webgui_db(self, collector, webgui_db):
        _insert_device(webgui_db, "Reloj Puerta", "192.168.1.50", 1)

        collector._initialize_devices()

        assert "192.168.1.50" in collector.zk_clients
