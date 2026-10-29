"""Tests del endpoint GET /api/buffer/retention (MYK-505)."""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask

from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.api_buffer import api_buffer_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_CHAIN = ("001_initial_schema.sql", "002_employees.sql")


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth("test-secret-key")
    app.buffer_repo = BufferRepository(
        tmp_path / "buffer.db", retention_days=730, archive_dir=tmp_path / "archive"
    )
    app.register_blueprint(api_buffer_bp, url_prefix="/api/buffer")
    return app


@pytest.fixture
def app(tmp_path):
    return _build_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


def _login(client, role="auditor"):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "qa.test"
        sess["role"] = role


def _record(user_id="1", days_ago=0):
    return AttendanceRecordDB(
        user_id=user_id,
        timestamp=datetime.now() - timedelta(days=days_ago),
        status=0,
        device_ip="10.0.0.5",
        punch_type="entrada",
    )


def test_retention_requires_auth(client):
    resp = client.get("/api/buffer/retention")
    assert resp.status_code == 401


def test_retention_returns_effective_config(client, app):
    _login(client)
    resp = client.get("/api/buffer/retention")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["retention_days"] == 730
    assert body["archive_enabled"] is True
    assert body["total_records"] == 0
    assert body["retention_audit"] == []
    assert body["archive_log"] == []


def test_retention_reflects_purge_and_archive(client, app):
    repo = app.buffer_repo
    repo.add_records([_record("1", days_ago=900), _record("2", days_ago=1)])
    ids = [r["id"] for r in repo.get_unsynced_records()]
    repo.mark_as_synced(ids)
    repo.archive_synced_older_than(
        days=790,
        export_path=Path(repo.archive_dir) / "manual.csv",
        reason="retencion anual",
        operator="qa",
    )
    repo.purge_synced_older_than(days=790, reason="retencion anual", operator="qa")

    _login(client)
    body = client.get("/api/buffer/retention").get_json()
    assert body["total_records"] == 1
    assert body["pending_sync"] == 0
    assert body["archive_log"][0]["action"] == "archive_synced"
    assert body["archive_log"][0]["records_archived"] == 1
    assert body["retention_audit"][0]["action"] == "purge_synced"
    assert body["retention_audit"][0]["records_deleted"] == 1


def test_retention_forbidden_without_reports_permission(client):
    _login(client, role="desconocido")
    resp = client.get("/api/buffer/retention")
    assert resp.status_code == 403
