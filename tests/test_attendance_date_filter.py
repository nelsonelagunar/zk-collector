"""Tests del filtro de fechas de /attendance (MYK-383).

El buffer almacena timestamps ISO con separador 'T'; el filtro de fechas debe
comparar por fecha normalizada (substr(timestamp,1,10)) para que end_date sea
inclusivo en ambos formatos, igual que /reportes.
"""

import csv
import io
import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.buffer.repository import BufferRepository
from src.webgui.api_tokens import ApiTokenService
from src.webgui.database import Database
from src.webgui.routes.attendance import attendance_bp

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
MIGRATION_CHAIN = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "003_medical_leaves.sql",
    "009_api_tokens.sql",
)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "data" / "webgui.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _apply_migrations(conn)
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.buffer_repo = BufferRepository(tmp_path / "data" / "buffer.db")
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    return app


@pytest.fixture
def client(tmp_path):
    app = _build_app(tmp_path)
    test_client = app.test_client()

    # PAT real: /attendance/api/* requiere Bearer desde MYK-407
    user_id = app.db.insert(
        "users",
        {"username": "tester", "password_hash": "x", "role": "admin"},
    )
    token = ApiTokenService(app.db).issue_token(
        user_id, "test", ["read", "write"]
    )["token"]
    test_client.environ_base["HTTP_AUTHORIZATION"] = f"Bearer {token}"
    return test_client


def _insert_records(client, rows) -> None:
    """rows: iterable de (user_id, timestamp) insertados tal cual al buffer."""
    buffer_repo = client.application.buffer_repo
    with buffer_repo.get_connection() as conn:
        conn.executemany(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
            "VALUES (?, ?, 0, '10.0.0.5')",
            list(rows),
        )


def _get_total(client, query: str) -> int:
    resp = client.get(f"/attendance/api/attendance?{query}")
    assert resp.status_code == 200
    return resp.get_json()["pagination"]["total"]


class TestAttendanceDateFilter:
    def test_single_day_iso_timestamps_included(self, client):
        _insert_records(
            client,
            [
                ("1", "2026-10-23T08:00:00"),
                ("1", "2026-10-23T18:30:00"),
                ("2", "2026-10-23T23:59:59"),
                ("3", "2026-10-22T23:30:00"),
                ("4", "2026-10-24T00:01:00"),
            ],
        )
        total = _get_total(client, "start_date=2026-10-23&end_date=2026-10-23")
        assert total == 3

    def test_single_day_240_iso_records(self, client):
        # Criterio de aceptacion 1 del issue: mismo dia devuelve todos los
        # registros del dia (240 en el entorno demo).
        _insert_records(
            client,
            [(str(i % 30), f"2026-10-23T{8 + (i // 30):02d}:{i % 60:02d}:00") for i in range(240)],
        )
        total = _get_total(client, "start_date=2026-10-23&end_date=2026-10-23")
        assert total == 240

    def test_end_date_inclusive_upper_bound(self, client):
        _insert_records(
            client,
            [
                ("1", "2026-10-22T23:59:59"),
                ("2", "2026-10-23T00:00:01"),
                ("3", "2026-10-24T08:15:00"),
                ("4", "2026-10-24T23:59:59"),
            ],
        )
        total = _get_total(client, "start_date=2026-10-22&end_date=2026-10-24")
        assert total == 4

    def test_space_format_still_supported(self, client):
        _insert_records(
            client,
            [
                ("1", "2026-10-23 08:00:00"),
                ("2", "2026-10-23 23:59:59"),
                ("3", "2026-10-24 08:00:00"),
            ],
        )
        total = _get_total(client, "start_date=2026-10-23&end_date=2026-10-23")
        assert total == 2

    def test_export_includes_end_day_iso_records(self, client):
        _insert_records(
            client,
            [
                ("1", "2026-10-23T08:00:00"),
                ("2", "2026-10-24T23:59:59"),
                ("3", "2026-10-25T00:01:00"),
            ],
        )
        resp = client.get("/attendance/export?start_date=2026-10-23&end_date=2026-10-24")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        assert len(rows) == 3  # header + 2 registros del rango

    def test_build_attendance_query_normalizes_date_bounds(self):
        from src.webgui.routes.attendance import _build_attendance_query

        params = {
            "start_date": "2026-10-23",
            "end_date": "2026-10-24",
            "user_id": "",
            "device_ip": "",
            "status": "",
            "punch_type": "",
            "synced": "",
        }
        where_clause, query_params = _build_attendance_query(params)
        assert "substr(timestamp, 1, 10) >= ?" in where_clause
        assert "substr(timestamp, 1, 10) <= ?" in where_clause
        assert query_params == ["2026-10-23", "2026-10-24"]
