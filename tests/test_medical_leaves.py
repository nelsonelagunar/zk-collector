"""Tests for the medical_leaves migration (003) and its CRUD helpers (MYK-238)."""

import sqlite3
from pathlib import Path

import pytest

from src.webgui.database import Database

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def _apply_migrations(conn: sqlite3.Connection, *names: str) -> None:
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def db(tmp_path: Path) -> Database:
    db_path = tmp_path / "webgui.db"
    conn = _connect(db_path)
    _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql", "005_medical_leaves.sql")
    conn.close()
    return Database(db_path)


class TestMedicalLeavesMigration:
    def test_tables_and_indexes_exist(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql", "005_medical_leaves.sql")

        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"medical_leaves"} <= tables

        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {"idx_medical_leaves_employee_start"} <= indexes
        conn.close()

    def test_idempotent_apply(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql", "005_medical_leaves.sql")
        _apply_migrations(conn, "005_medical_leaves.sql")  # must not raise
        conn.close()

    def test_leave_type_check_constraint(self, db: Database) -> None:
        # First create an employee as foreign key
        emp_id = db.create_employee({"employee_code": "E001", "first_name": "Ana", "last_name": "Lopez"})
        
        # Valid leave types should work
        for leave_type in ('enfermedad', 'maternidad', 'accidente', 'otro'):
            db.create_medical_leave({
                "employee_id": emp_id,
                "leave_type": leave_type,
                "start_date": "2026-10-01",
                "end_date": "2026-10-05",
                "days": 5
            })
        
        # Invalid leave type should fail
        with pytest.raises(sqlite3.IntegrityError):
            db.create_medical_leave({
                "employee_id": emp_id,
                "leave_type": "vacaciones",  # Invalid
                "start_date": "2026-10-01",
                "end_date": "2026-10-05",
                "days": 5
            })

    def status_check_constraint(self, db: Database) -> None:
        emp_id = db.create_employee({"employee_code": "E002", "first_name": "Juan", "last_name": "Perez"})
        
        # Valid status values should work
        for status in ('active', 'cancelled'):
            db.create_medical_leave({
                "employee_id": emp_id,
                "leave_type": "enfermedad",
                "start_date": "2026-10-01",
                "end_date": "2026-10-05",
                "days": 5,
                "status": status
            })
        
        # Invalid status should fail
        with pytest.raises(sqlite3.IntegrityError):
            db.create_medical_leave({
                "employee_id": emp_id,
                "leave_type": "enfermedad",
                "start_date": "2026-10-01",
                "end_date": "2026-10-05",
                "days": 5,
                "status": "pending"  # Invalid
            })

    def test_end_date_gte_start_date_constraint(self, db: Database) -> None:
        emp_id = db.create_employee({"employee_code": "E003", "first_name": "Maria", "last_name": "Garcia"})
        
        # Valid date ranges should work
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-01",  # Same day
            "days": 1
        })
        
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",  # End after start
            "days": 5
        })
        
        # Invalid date range (end before start) should fail
        with pytest.raises(sqlite3.IntegrityError):
            db.create_medical_leave({
                "employee_id": emp_id,
                "leave_type": "enfermedad",
                "start_date": "2026-10-05",
                "end_date": "2026-10-01",  # End before start
                "days": 5
            })

    def test_employee_fk_cascade_on_delete(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql", "005_medical_leaves.sql")
        cur = conn.execute(
            "INSERT INTO employees (employee_code, first_name, last_name) VALUES (?, ?, ?)",
            ("E1", "Ana", "Lopez"),
        )
        emp_id = cur.lastrowid
        conn.execute(
            "INSERT INTO medical_leaves "
            "(employee_id, leave_type, start_date, end_date, days) VALUES (?, ?, ?, ?, ?)",
            (emp_id, "enfermedad", "2026-10-01", "2026-10-05", 5),
        )
        leave_id = cur.lastrowid
        conn.commit()

        # Delete employee should cascade delete medical leave
        conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()

        leaves = conn.execute("SELECT COUNT(*) FROM medical_leaves WHERE employee_id = ?", (emp_id,)).fetchone()[0]
        assert leaves == 0
        conn.close()


class TestMedicalLeavesCrud:
    def test_create_and_get(self, db: Database) -> None:
        # First create an employee
        emp_id = db.create_employee(
            {"employee_code": "E100", "first_name": "Ana", "last_name": "Lopez", "department": "RH"}
        )
        
        leave_id = db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "days": 5,
            "doctor_name": "Dr. Smith",
            "document_ref": "/path/to/document.pdf"
        })
        assert leave_id > 0

        leave = db.get_medical_leave_by_id(leave_id)
        assert leave is not None
        assert leave["employee_id"] == emp_id
        assert leave["leave_type"] == "enfermedad"
        assert leave["start_date"] == "2026-10-01"
        assert leave["end_date"] == "2026-10-05"
        assert leave["days"] == 5
        assert leave["doctor_name"] == "Dr. Smith"
        assert leave["document_ref"] == "/path/to/document.pdf"
        assert leave["status"] == "active"

    def test_timestamps_defaulted_on_create(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E101", "first_name": "Ana", "last_name": "Lopez"}
        )
        
        leave_id = db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "days": 5
        })
        
        leave = db.get_medical_leave_by_id(leave_id)
        assert leave is not None
        assert leave["created_at"] is not None
        assert leave["updated_at"] is not None

    def test_get_medical_leaves_by_employee_filters(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E200", "first_name": "Ana", "last_name": "Lopez", "department": "RH"}
        )
        
        # Create active leave
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "days": 5
        })
        
        # Create cancelled leave
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "maternidad",
            "start_date": "2026-09-01",
            "end_date": "2026-09-10",
            "days": 10,
            "status": "cancelled"
        })
        
        # Get all leaves
        all_leaves = db.get_medical_leaves_by_employee(emp_id)
        assert len(all_leaves) == 2
        
        # Get only active leaves
        active_leaves = db.get_medical_leaves_by_employee(emp_id, status="active")
        assert len(active_leaves) == 1
        assert active_leaves[0]["leave_type"] == "enfermedad"
        
        # Get only cancelled leaves
        cancelled_leaves = db.get_medical_leaves_by_employee(emp_id, status="cancelled")
        assert len(cancelled_leaves) == 1
        assert cancelled_leaves[0]["leave_type"] == "maternidad"

    def test_update_medical_leave_refreshes_updated_at(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E300", "first_name": "Ana", "last_name": "Lopez"}
        )
        
        leave_id = db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "days": 5
        })
        
        db.update_medical_leave(leave_id, {"days": 7, "doctor_name": "Dr. Johnson"})
        after = db.get_medical_leave_by_id(leave_id)
        
        assert after["days"] == 7
        assert after["doctor_name"] == "Dr. Johnson"
        assert after["updated_at"] is not None

    def test_delete_medical_leave_is_soft(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E400", "first_name": "Ana", "last_name": "Lopez"}
        )
        
        leave_id = db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-01",
            "end_date": "2026-10-05",
            "days": 5
        })
        
        db.delete_medical_leave(leave_id)
        
        leave = db.get_medical_leave_by_id(leave_id)
        assert leave is not None
        assert leave["status"] == "cancelled"

    def test_ordering_by_start_date_desc(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E500", "first_name": "Ana", "last_name": "Lopez"}
        )
        
        # Create leaves in non-chronological order
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "enfermedad",
            "start_date": "2026-10-10",
            "end_date": "2026-10-15",
            "days": 6
        })
        
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "maternidad",
            "start_date": "2026-09-01",
            "end_date": "2026-09-30",
            "days": 30
        })
        
        db.create_medical_leave({
            "employee_id": emp_id,
            "leave_type": "accidente",
            "start_date": "2026-11-01",
            "end_date": "2026-11-05",
            "days": 5
        })
        
        leaves = db.get_medical_leaves_by_employee(emp_id)
        assert len(leaves) == 3
        
        # Should be ordered by start_date DESC (most recent first)
        assert leaves[0]["start_date"] == "2026-11-01"  # accidente
        assert leaves[1]["start_date"] == "2026-10-10"  # enfermedad
        assert leaves[2]["start_date"] == "2026-09-01"  # maternidad