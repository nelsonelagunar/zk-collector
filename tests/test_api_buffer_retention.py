"""Tests para el endpoint GET /api/buffer/retention (MYK-505)."""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.middleware.auth import reset_rate_limit_store as reset_api_rate_limit
from src.webgui.routes.api_buffer import api_buffer_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_CHAIN = ("001_initial_schema.sql", "009_api_tokens.sql")


def _build_app(tmp_path: Path) -> Flask:
    # Create webgui.db with users table for auth
    webgui_db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(webgui_db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())
    conn.close()

    buffer_db_path = tmp_path / "buffer.db"
    buffer_repo = BufferRepository(
        buffer_db_path,
        retention_days=730,
        config_source="archivo",
        config_path="/etc/attendance/collector.yaml",
    )

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(webgui_db_path)
    app.auth = Auth("test-secret-key")
    app.buffer_repo = buffer_repo
    app.register_blueprint(api_buffer_bp, url_prefix="/api/buffer")

    # Create admin user
    admin_id = app.db.insert(
        "users",
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": app.auth.hash_password("Sup3rSecret!Pass"),
            "role": "admin",
        },
    )
    app.config["ADMIN_ID"] = admin_id

    return app


@pytest.fixture
def app(tmp_path):
    reset_api_rate_limit()
    return _build_app(tmp_path)


@pytest.fixture
def client(app):
    return app.test_client()


def _get_pat_token(app):
    """Helper to create a PAT token for testing."""
    from src.webgui.api_tokens import ApiTokenService
    service = ApiTokenService(app.db)
    result = service.issue_token(app.config["ADMIN_ID"], "test-token", ["read"])
    return result["token"]


def test_retention_returns_effective_retention(app):
    """El endpoint retorna retention_days y config_source correctos."""
    # Agregar un registro para tener total_records > 0
    app.buffer_repo.log_sync(records_synced=10, records_failed=0, status="success")

    token = _get_pat_token(app)
    client = app.test_client()
    resp = client.get(
        "/api/buffer/retention",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert resp.status_code == 200

    data = resp.get_json()
    assert data["retention_days"] == 730
    assert data["config_source"] == "archivo"
    assert data["config_path"] == "/etc/attendance/collector.yaml"
    assert data["total_records"] == 0  # no attendance_records, solo sync_log
    assert isinstance(data["retention_audit"], list)
    assert len(data["retention_audit"]) == 1
    assert data["retention_audit"][0]["records_synced"] == 10


def test_retention_default_config_source():
    """Cuando no hay YAML, config_source es 'default'."""
    import tempfile
    import os

    db_path = Path(tempfile.mkdtemp()) / "buffer_default.db"
    repo = BufferRepository(db_path)  # defaults: retention_days=30, config_source='default'
    stats = repo.get_stats()
    assert stats["retention_days"] == 30
    assert stats["config_source"] == "default"
    assert stats["config_path"] is None