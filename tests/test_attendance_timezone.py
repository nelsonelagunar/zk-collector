"""Tests de timestamps con zona horaria en asistencia (MYK-420).

Criterios de aceptacion del issue:
- Un registro con offset +06:00 serializa/deserializa identico en el buffer.
- Export en el huso Pacifico (America/Tijuana) muestra la hora local del
  centro de trabajo configurado en system_config.timezone.
- El firmware entrega datetimes naive: se localizan con el huso del
  dispositivo/config (default America/Mexico_City) antes de persistir.
"""

import csv
import io
import sqlite3
from datetime import datetime, timedelta, timezone
from pathlib import Path
from types import SimpleNamespace
from zoneinfo import ZoneInfo

import pytest
from flask import Flask

from src.buffer.models import AttendanceRecordDB
from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.utils.timezones import (
    DEFAULT_TIMEZONE,
    coerce_timezone,
    get_system_timezone,
    parse_timestamp,
    to_local_iso,
)
from src.webgui.database import Database
from src.webgui.routes.attendance import attendance_bp
from src.zk_client.attendance import AttendanceRecord

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
MIGRATION_CHAIN = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "003_medical_leaves.sql",
    "004_password_reset_tokens.sql",
    "005_alerts.sql",
    "006_alert_default_rules.sql",
    "008_timezone_config.sql",
)

PLUS_SIX = timezone(timedelta(hours=6))


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path, system_timezone: str | None = None) -> Flask:
    db_path = tmp_path / "data" / "webgui.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _apply_migrations(conn)
    if system_timezone is not None:
        conn.execute(
            "INSERT OR REPLACE INTO system_config (key, value, description) "
            "VALUES ('timezone', ?, 'IANA timezone of the work center')",
            (system_timezone,),
        )
    conn.commit()
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth(app.config["SECRET_KEY"])
    app.buffer_repo = BufferRepository(
        tmp_path / "data" / "buffer.db",
        default_timezone=get_system_timezone(app.db),
    )
    app.register_blueprint(attendance_bp, url_prefix="/attendance")
    return app


def _record(user_id: str, ts: datetime) -> AttendanceRecordDB:
    return AttendanceRecordDB(
        user_id=user_id,
        timestamp=ts,
        status=0,
        device_ip="10.0.0.5",
        punch_type="entrada",
    )


def _insert_raw(client, rows) -> None:
    """rows: iterable de (user_id, timestamp) insertados tal cual al buffer."""
    buffer_repo = client.application.buffer_repo
    with buffer_repo.get_connection() as conn:
        conn.executemany(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
            "VALUES (?, ?, 0, '10.0.0.5')",
            list(rows),
        )


class TestBufferRoundTripOffset:
    """AC: registro con offset +06:00 serializa/deserializa identico."""

    def test_plus_six_offset_round_trip(self, tmp_path):
        buffer = BufferRepository(tmp_path / "buffer.db")
        original = datetime(2026, 10, 23, 9, 30, 15, tzinfo=PLUS_SIX)
        inserted = buffer.add_records([_record("1", original)])
        assert inserted == 1

        rows = buffer.get_unsynced_records()
        assert len(rows) == 1
        # Serializacion identica: el offset +06:00 se conserva tal cual
        assert rows[0]["timestamp"] == "2026-10-23T09:30:15+06:00"
        # Deserializacion identica: fromisoformat devuelve el mismo instante
        assert datetime.fromisoformat(rows[0]["timestamp"]) == original

    def test_naive_firmware_localized_with_default_tz(self, tmp_path):
        buffer = BufferRepository(
            tmp_path / "buffer.db", default_timezone="America/Mexico_City"
        )
        naive = datetime(2026, 10, 23, 8, 0, 0)
        buffer.add_records([_record("2", naive)])
        rows = buffer.get_unsynced_records()
        # Huso oficial MX: sin horario de verano, offset fijo -06:00
        assert rows[0]["timestamp"] == "2026-10-23T08:00:00-06:00"

    def test_buffer_default_timezone_is_mexico_city(self, tmp_path):
        buffer = BufferRepository(tmp_path / "buffer.db")
        buffer.add_records([_record("3", datetime(2026, 10, 23, 8, 0, 0))])
        rows = buffer.get_unsynced_records()
        assert rows[0]["timestamp"].endswith("-06:00")

    def test_invalid_tz_falls_back_to_default(self):
        assert str(coerce_timezone("Not/A_Zone")) == DEFAULT_TIMEZONE
        assert coerce_timezone(ZoneInfo("America/Tijuana")) == ZoneInfo("America/Tijuana")


class TestFirmwareLocalize:
    """from_zk_attendance localiza naive del firmware con el huso indicado."""

    def test_naive_localized_with_device_timezone(self):
        punch = SimpleNamespace(user_id=7, timestamp=datetime(2026, 10, 23, 8, 0), status=0)
        record = AttendanceRecord.from_zk_attendance(punch, "10.0.0.9", "America/Tijuana")
        assert record.timestamp.tzinfo is not None
        assert record.timestamp.isoformat() == "2026-10-23T08:00:00-07:00"
        assert record.to_dict()["timestamp"] == "2026-10-23T08:00:00-07:00"

    def test_aware_timestamp_untouched(self):
        aware = datetime(2026, 10, 23, 8, 0, tzinfo=PLUS_SIX)
        punch = SimpleNamespace(user_id=7, timestamp=aware, status=0)
        record = AttendanceRecord.from_zk_attendance(punch, "10.0.0.9", "America/Tijuana")
        assert record.timestamp == aware

    def test_no_timezone_keeps_naive(self):
        punch = SimpleNamespace(user_id=7, timestamp=datetime(2026, 10, 23, 8, 0), status=0)
        record = AttendanceRecord.from_zk_attendance(punch, "10.0.0.9")
        assert record.timestamp.tzinfo is None


class TestSystemTimezoneConfig:
    """system_config.timezone (migration 008) default America/Mexico_City."""

    def test_migration_default(self, tmp_path):
        app = _build_app(tmp_path)
        assert get_system_timezone(app.db) == "America/Mexico_City"

    def test_configured_value_wins(self, tmp_path):
        app = _build_app(tmp_path, system_timezone="America/Tijuana")
        assert get_system_timezone(app.db) == "America/Tijuana"

    def test_invalid_db_value_falls_back(self, tmp_path):
        app = _build_app(tmp_path, system_timezone="Bad/Zone")
        assert coerce_timezone(get_system_timezone(app.db)) == ZoneInfo(DEFAULT_TIMEZONE)


class TestPacificExport:
    """AC: export en huso Pacifico (America/Tijuana) muestra hora local."""

    def test_api_attendance_localized_to_pacific(self, tmp_path):
        app = _build_app(tmp_path, system_timezone="America/Tijuana")
        client = app.test_client()
        # Registro persistido en huso Centro (-06:00): 08:00 CDMX = 07:00 Tijuana
        _insert_raw(client, [("1", "2026-10-23T08:00:00-06:00")])
        resp = client.get("/attendance/api/attendance")
        assert resp.status_code == 200
        records = resp.get_json()["records"]
        assert records[0]["timestamp"] == "2026-10-23T07:00:00-07:00"

    def test_export_csv_pacific_offset(self, tmp_path):
        app = _build_app(tmp_path, system_timezone="America/Tijuana")
        client = app.test_client()
        _insert_raw(
            client,
            [
                ("1", "2026-10-23T08:00:00-06:00"),
                ("2", "2026-10-23T18:30:00-06:00"),
            ],
        )
        resp = client.get("/attendance/export?format=csv")
        assert resp.status_code == 200
        rows = list(csv.reader(io.StringIO(resp.get_data(as_text=True))))
        header_idx = rows[0].index("timestamp")
        # Export ordena por timestamp DESC
        assert [r[header_idx] for r in rows[1:]] == [
            "2026-10-23T17:30:00-07:00",
            "2026-10-23T07:00:00-07:00",
        ]

    def test_export_default_center_timezone(self, tmp_path):
        app = _build_app(tmp_path)
        client = app.test_client()
        # Sin config, hora local del centro = America/Mexico_City
        _insert_raw(client, [("1", "2026-10-23T08:00:00-06:00")])
        resp = client.get("/attendance/api/attendance")
        records = resp.get_json()["records"]
        assert records[0]["timestamp"] == "2026-10-23T08:00:00-06:00"

    def test_export_xlsx_pacific_offset(self, tmp_path):
        openpyxl = pytest.importorskip("openpyxl")
        app = _build_app(tmp_path, system_timezone="America/Tijuana")
        client = app.test_client()
        _insert_raw(client, [("1", "2026-10-23T08:00:00-06:00")])
        resp = client.get("/attendance/export?format=xlsx")
        assert resp.status_code == 200
        workbook = openpyxl.load_workbook(io.BytesIO(resp.data))
        sheet = workbook.active
        header = [c.value for c in sheet[1]]
        ts_idx = header.index("Fecha/Hora")
        assert sheet[2][ts_idx].value == "2026-10-23T07:00:00-07:00"


class TestTimestampHelpers:
    def test_parse_timestamp_supports_offsets_and_legacy(self):
        assert parse_timestamp("2026-10-23T08:00:00+06:00") == datetime(
            2026, 10, 23, 8, 0, tzinfo=PLUS_SIX
        )
        assert parse_timestamp("2026-10-23 08:00:00") == datetime(2026, 10, 23, 8, 0)
        assert parse_timestamp("garbage") is None
        assert parse_timestamp(None) is None

    def test_to_local_iso_assumes_naive_in_tz(self):
        tz = ZoneInfo("America/Tijuana")
        assert to_local_iso("2026-10-23T08:00:00-06:00", tz) == "2026-10-23T07:00:00-07:00"
        assert to_local_iso("2026-10-23 08:00:00", tz) == "2026-10-23T08:00:00-07:00"
        assert to_local_iso("no-parsea", tz) == "no-parsea"
