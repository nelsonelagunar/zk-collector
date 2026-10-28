"""Tests de regresión del dashboard autenticado (MYK-365).

Reproduce el layout Docker: webgui.db creada SOLO desde migrations/ y el
buffer de asistencia en buffer.db (BufferRepository). Regresión de MYK-363:
antes del fix, GET / tras un login válido daba 500
`sqlite3.OperationalError: no such table: attendance_buffer` porque index()
consultaba attendance_buffer en webgui.db (server.py), tabla que NINGUNA
migración (001-004) crea.
"""

import os

os.environ.setdefault("WEBGUI_SKIP_APP_CREATE", "1")

import re
import shutil
from datetime import datetime, timedelta
from pathlib import Path

import pytest

from src.buffer.models import AttendanceRecordDB
from src.webgui.server import create_app  # noqa: E402


def _dt(days_ago: int = 0, hours: int = 8, minutes: int = 0) -> datetime:
    """Relative datetime for tests — avoids time-bombs (MYK-466)."""
    base = datetime.now().replace(hour=hours, minute=minutes, second=0, microsecond=0)
    return base - timedelta(days=days_ago)

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
STRONG_PASSWORD = "Sup3rSecret!Pass"


@pytest.fixture
def webgui_app(tmp_path, monkeypatch):
    """App de producción (create_app) con layout Docker:

    - migrations/ en tmp_path/migrations (Database busca en db_path.parent.parent)
    - webgui.db creada SOLO por las migraciones 001-004
    - buffer.db manejada por BufferRepository (attendance_records/sync_log)
    """
    shutil.copytree(MIGRATIONS_DIR, tmp_path / "migrations")
    data_dir = tmp_path / "data"
    monkeypatch.setenv("DB_PATH", str(data_dir / "webgui.db"))
    monkeypatch.setenv("BUFFER_DB_PATH", str(data_dir / "buffer.db"))
    monkeypatch.setenv("WEBGUI_SECRET_KEY", "test-secret-key")
    app = create_app()
    app.config["TESTING"] = True
    return app


@pytest.fixture
def user_id(webgui_app):
    return webgui_app.db.insert(
        "users",
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": webgui_app.auth.hash_password(STRONG_PASSWORD),
            "role": "admin",
        },
    )


def _login(client):
    return client.post(
        "/auth/login",
        data={"username": "admin", "password": STRONG_PASSWORD},
        follow_redirects=True,
    )


def test_valid_login_then_dashboard_returns_200(webgui_app, user_id):
    """MYK-365 AC1: login válido -> GET / responde 200 con DB solo-migraciones.

    En master sin fix este test muere con
    sqlite3.OperationalError: no such table: attendance_buffer.
    """
    client = webgui_app.test_client()
    response = _login(client)
    assert response.request.path == "/"
    assert response.status_code == 200


def test_dashboard_pending_records_come_from_buffer_db(webgui_app, user_id):
    """AC: pending_records del dashboard se sirve desde buffer.db
    (BufferRepository.attendance_records), no desde webgui.db."""
    webgui_app.buffer_repo.add_records(
        [
            AttendanceRecordDB(
                user_id="1",
                timestamp=_dt(days_ago=365),
                status=0,
                device_ip="192.168.1.101",
                punch_type="check_in",
            ),
            AttendanceRecordDB(
                user_id="2",
                timestamp=_dt(days_ago=365, minutes=5),
                status=0,
                device_ip="192.168.1.101",
                punch_type="check_in",
            ),
        ]
    )
    client = webgui_app.test_client()
    response = _login(client)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    match = re.search(r"Registros Pendientes\s*</dt>\s*<dd[^>]*>\s*(\d+)", html, re.S)
    assert match is not None, "el dashboard no renderiza 'Registros Pendientes'"
    assert int(match.group(1)) == 2


def test_dashboard_without_session_redirects_to_login(webgui_app):
    """index() sin sesión redirige al login (cobertura de la otra rama)."""
    client = webgui_app.test_client()
    response = client.get("/")
    assert response.status_code == 302
    assert "/auth/login" in response.headers["Location"]
