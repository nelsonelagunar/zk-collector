"""Tests para el servicio de estadisticas de asistencia (MYK-241).

Fixture (periodo 2026-10-05 Lunes -> 2026-10-09 Viernes, 5 habiles):
- Ana (E001, IT, hire 2020): punchs Lun 08:55 entrada (temprano) + 10:00
  entrada duplicada + 18:00 salida, Mar 09:20 entrada (TARDE, formato ISO 'T'),
  Jue 08:30 entrada; ademas un punch sabado (fuera de KPIs).
- Bob (E002, Ventas, hire 2026-10-07): sin punchs.
- Incapacidad activa de Ana Jue-Vie; una cancelada Lun-Mar (no cuenta).
- 2 registros huerfanos (user sin link + device desconocido).

Esperado Ana: expected=5 present=3 incap=1 (solo Vie; Jue trabajo) absent=1
retardos=1 (Mar) puntualidad=66.7 ausentismo=20.0.
Esperado Bob: expected=3 (hire tope) present=0 absent=3 puntualidad=null.
"""

import shutil
from pathlib import Path

import pytest

from src.buffer.repository import BufferRepository
from src.webgui.attendance_stats import (
    StatsValidationError,
    compute_attendance_stats,
)
from src.webgui.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_SRC = REPO_ROOT / "migrations"

START, END = "2026-10-05", "2026-10-09"


@pytest.fixture
def db(tmp_path):
    shutil.copytree(MIGRATIONS_SRC, tmp_path / "migrations")
    database = Database(tmp_path / "data" / "webgui.db")
    database.initialize()
    return database


@pytest.fixture
def buffer_repo(tmp_path):
    return BufferRepository(tmp_path / "data" / "buffer.db")


@pytest.fixture
def seeded(db, buffer_repo):
    """Pobla employees, devices, links, attendance_records y medical_leaves."""
    db.insert("devices", {"name": "Reloj 1", "address": "10.0.0.5", "serial_number": "SN1"})
    ana_id = db.insert(
        "employees",
        {
            "employee_code": "E001",
            "first_name": "Ana",
            "last_name": "Lopez",
            "department": "IT",
            "hire_date": "2020-01-01",
        },
    )
    bob_id = db.insert(
        "employees",
        {
            "employee_code": "E002",
            "first_name": "Bob",
            "last_name": "Suarez",
            "department": "Ventas",
            "hire_date": "2026-10-07",
        },
    )
    db.insert(
        "employee_device_links",
        {
            "employee_id": ana_id,
            "device_serial": "SN1",
            "device_user_id": "1",
        },
    )
    db.insert(
        "employee_device_links",
        {
            "employee_id": bob_id,
            "device_serial": "SN1",
            "device_user_id": "2",
        },
    )
    db.insert(
        "medical_leaves",
        {
            "employee_id": ana_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-08",
            "end_date": "2026-10-09",
            "days": 2,
        },
    )
    db.insert(
        "medical_leaves",
        {
            "employee_id": ana_id,
            "leave_type": "accidente",
            "start_date": "2026-10-05",
            "end_date": "2026-10-07",
            "days": 3,
            "status": "cancelled",
        },
    )

    records = [
        # Ana: (user_id, timestamp, status)
        ("1", "2026-10-05 08:55:00", 0),  # Lun entrada temprano (la primera)
        ("1", "2026-10-05 10:00:00", 0),  # entrada posterior: no es la primera
        ("1", "2026-10-05 18:00:00", 1),  # salida
        ("1", "2026-10-06T09:20:00", 0),  # Mar entrada TARDE (formato ISO con T)
        ("1", "2026-10-08 08:30:00", 0),  # Jue entrada pese a incapacidad
        ("1", "2026-10-10 08:00:00", 0),  # Sabado: fuera de dias habiles
        ("99", "2026-10-05 08:00:00", 0),  # user sin link -> unlinked
    ]
    with buffer_repo.get_connection() as conn:
        for user_id, ts, status in records:
            conn.execute(
                "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
                "VALUES (?, ?, ?, '10.0.0.5')",
                (user_id, ts, status),
            )
        # device desconocido -> unlinked
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
            "VALUES ('1', '2026-10-05 09:00:00', 0, '10.0.0.99')",
        )
    return {"ana_id": ana_id, "bob_id": bob_id}


def _stats(db, buffer_repo, **kwargs):
    params = {"start_date": START, "end_date": END}
    params.update(kwargs)
    return compute_attendance_stats(db, buffer_repo, **params)


class TestEmployeeGroup:
    def test_ana_full_kpis(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["ana_id"])
        ana = report["rows"][0]
        assert ana["employee_name"] == "Ana Lopez"
        assert ana["department"] == "IT"
        assert ana["days_expected"] == 5
        assert ana["days_present"] == 3
        assert ana["days_incapacity"] == 1
        assert ana["days_absent"] == 1
        assert ana["days_vacation"] == 0
        assert ana["late_arrivals"] == 1
        assert ana["punctuality_pct"] == 66.7
        assert ana["absenteeism_pct"] == 20.0

    def test_bob_hire_date_caps_expected(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["bob_id"])
        bob = report["rows"][0]
        assert bob["days_expected"] == 3
        assert bob["days_present"] == 0
        assert bob["days_absent"] == 3
        assert bob["punctuality_pct"] is None
        assert bob["absenteeism_pct"] == 100.0

    def test_present_day_wins_over_incapacity(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["ana_id"])
        ana = report["rows"][0]
        # Jue trabajo (present) y Vie cubierto por incapacidad activa
        assert ana["days_incapacity"] == 1
        assert ana["days_absent"] == 1  # solo Mie

    def test_weekend_records_do_not_count(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["ana_id"])
        assert report["rows"][0]["days_present"] == 3  # Sab ignorado

    def test_totals_and_meta(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo)
        assert report["meta"]["employees_total"] == 2
        assert report["meta"]["unlinked_records"] == 2
        assert report["totals"]["days_expected"] == 8
        assert report["totals"]["days_present"] == 3
        assert report["totals"]["days_incapacity"] == 1
        assert report["totals"]["days_absent"] == 4
        assert report["totals"]["late_arrivals"] == 1
        assert report["totals"]["punctuality_pct"] == 66.7
        assert report["totals"]["absenteeism_pct"] == 50.0

    def test_period_and_filters_echo(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, department="IT")
        assert report["period"] == {"start_date": START, "end_date": END}
        assert report["filters"]["department"] == "IT"
        assert report["group_by"] == "employee"
        assert report["work_start"] == "09:00:00"


class TestFilters:
    def test_department_filter(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, department="IT")
        assert report["meta"]["employees_total"] == 1
        assert report["rows"][0]["employee_code"] == "E001"

    def test_employee_id_filter(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["bob_id"])
        assert [r["employee_code"] for r in report["rows"]] == ["E002"]

    def test_empty_result_when_no_match(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, department="Logistica")
        assert report["rows"] == []
        assert report["totals"]["days_expected"] == 0
        assert report["totals"]["punctuality_pct"] is None


class TestGrouping:
    def test_group_by_department(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, group_by="department")
        by_dept = {row["department"]: row for row in report["rows"]}
        assert set(by_dept) == {"IT", "Ventas"}
        assert by_dept["IT"]["days_present"] == 3
        assert by_dept["IT"]["days_incapacity"] == 1
        assert by_dept["Ventas"]["days_absent"] == 3
        assert by_dept["Ventas"]["punctuality_pct"] is None

    def test_group_by_company_single_row(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, group_by="company", company_name="ACME")
        assert len(report["rows"]) == 1
        row = report["rows"][0]
        assert row["company"] == "ACME"
        assert row["days_expected"] == 8
        assert row["days_absent"] == 4

    def test_department_null_falls_back_label(self, db, buffer_repo, seeded):
        db.insert(
            "employees",
            {"employee_code": "E003", "first_name": "Sin", "last_name": "Depto"},
        )
        report = _stats(db, buffer_repo, group_by="department")
        assert "Sin departamento" in {row["department"] for row in report["rows"]}


class TestWorkStart:
    def test_earlier_work_start_flags_more_lates(self, db, buffer_repo, seeded):
        report = _stats(db, buffer_repo, employee_id=seeded["ana_id"], work_start="08:00")
        ana = report["rows"][0]
        assert ana["late_arrivals"] == 3  # Lun 08:55, Mar 09:20 y Jue 08:30
        assert ana["punctuality_pct"] == 0.0
        assert report["work_start"] == "08:00:00"


class TestOldBufferSchema:
    """Regression tests for MYK-478: old buffer.db without annulled column."""

    @pytest.fixture
    def old_buffer_repo(self, tmp_path):
        """BufferRepository with old schema: no annulled column."""
        repo = BufferRepository(tmp_path / "data" / "buffer_old.db")
        # Drop annulled column if it somehow exists (simulate old schema)
        with repo.get_connection() as conn:
            conn.execute("DROP TABLE IF EXISTS attendance_records")
            conn.execute("""
                CREATE TABLE attendance_records (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    user_id TEXT NOT NULL,
                    timestamp DATETIME NOT NULL,
                    status INTEGER NOT NULL,
                    device_ip TEXT NOT NULL,
                    punch_type TEXT,
                    synced BOOLEAN DEFAULT 0,
                    sync_attempts INTEGER DEFAULT 0,
                    last_sync_attempt DATETIME,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
        return repo

    def test_stats_without_annulled_column(self, db, old_buffer_repo):
        """Stats endpoint must not crash when buffer.db lacks annulled column (MYK-478)."""
        db.insert("devices", {"name": "Reloj 1", "address": "10.0.0.5", "serial_number": "SN1"})
        ana_id = db.insert(
            "employees",
            {
                "employee_code": "E001",
                "first_name": "Ana",
                "last_name": "Lopez",
                "department": "IT",
                "hire_date": "2020-01-01",
            },
        )
        db.insert(
            "employee_device_links",
            {
                "employee_id": ana_id,
                "device_serial": "SN1",
                "device_user_id": "1",
            },
        )
        # Insert records into old-schema buffer (no annulled column)
        with old_buffer_repo.get_connection() as conn:
            conn.execute(
                "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
                "VALUES ('1', '2026-10-05 08:55:00', 0, '10.0.0.5')",
            )
        report = _stats(db, old_buffer_repo, employee_id=ana_id)
        assert report["rows"][0]["employee_name"] == "Ana Lopez"
        assert report["rows"][0]["days_present"] == 1

    def test_stats_with_annulled_column_still_works(self, db, buffer_repo, seeded):
        """Stats must still work with new buffer.db that has annulled column."""
        # buffer_repo fixture creates table without annulled, so add it manually
        with buffer_repo.get_connection() as conn:
            conn.execute("ALTER TABLE attendance_records ADD COLUMN annulled BOOLEAN NOT NULL DEFAULT 0")
        report = _stats(db, buffer_repo, employee_id=seeded["ana_id"])
        ana = report["rows"][0]
        assert ana["employee_name"] == "Ana Lopez"
        assert ana["days_present"] == 3


class TestValidation:
    def test_invalid_start_date(self, db, buffer_repo):
        with pytest.raises(StatsValidationError):
            _stats(db, buffer_repo, start_date="2026-13-01")

    def test_start_after_end(self, db, buffer_repo):
        with pytest.raises(StatsValidationError):
            _stats(db, buffer_repo, start_date="2026-10-09", end_date="2026-10-05")

    def test_invalid_group_by(self, db, buffer_repo):
        with pytest.raises(StatsValidationError):
            _stats(db, buffer_repo, group_by="team")

    def test_invalid_work_start(self, db, buffer_repo):
        with pytest.raises(StatsValidationError):
            _stats(db, buffer_repo, work_start="9am")
