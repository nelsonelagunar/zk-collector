"""Tests for the medical_leaves migration (003) (MYK-238)."""

import sqlite3
from pathlib import Path

import pytest

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"

MIGRATION_CHAIN = ("001_initial_schema.sql", "002_employees.sql", "003_medical_leaves.sql")


def _apply_migrations(conn: sqlite3.Connection, *names: str) -> None:
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _connect(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.row_factory = sqlite3.Row
    return conn


@pytest.fixture
def conn(tmp_path: Path) -> sqlite3.Connection:
    connection = _connect(tmp_path / "webgui.db")
    _apply_migrations(connection, *MIGRATION_CHAIN)
    return connection


def _seed_employee(conn: sqlite3.Connection) -> int:
    cur = conn.execute(
        "INSERT INTO employees (employee_code, first_name, last_name) VALUES (?, ?, ?)",
        ("E1", "Ana", "Lopez"),
    )
    return cur.lastrowid


class TestMedicalLeavesMigration:
    def test_table_and_index_exist(self, conn: sqlite3.Connection) -> None:
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert "medical_leaves" in tables

        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert "idx_medical_leaves_employee_start" in indexes

    def test_idempotent_apply(self, conn: sqlite3.Connection) -> None:
        _apply_migrations(conn, "003_medical_leaves.sql")  # must not raise

    def test_leave_type_check_constraint(self, conn: sqlite3.Connection) -> None:
        emp_id = _seed_employee(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO medical_leaves (employee_id, leave_type, start_date, end_date, days) "
                "VALUES (?, ?, ?, ?, ?)",
                (emp_id, "vacaciones", "2026-01-01", "2026-01-05", 5),
            )

    def test_status_check_constraint(self, conn: sqlite3.Connection) -> None:
        emp_id = _seed_employee(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO medical_leaves "
                "(employee_id, leave_type, start_date, end_date, days, status) "
                "VALUES (?, ?, ?, ?, ?, ?)",
                (emp_id, "enfermedad", "2026-01-01", "2026-01-05", 5, "bogus"),
            )

    def test_end_date_must_be_after_start_date(self, conn: sqlite3.Connection) -> None:
        emp_id = _seed_employee(conn)
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO medical_leaves (employee_id, leave_type, start_date, end_date, days) "
                "VALUES (?, ?, ?, ?, ?)",
                (emp_id, "enfermedad", "2026-01-10", "2026-01-05", 5),
            )

    def test_fk_cascade_on_employee_delete(self, conn: sqlite3.Connection) -> None:
        emp_id = _seed_employee(conn)
        conn.execute(
            "INSERT INTO medical_leaves (employee_id, leave_type, start_date, end_date, days) "
            "VALUES (?, ?, ?, ?, ?)",
            (emp_id, "enfermedad", "2026-01-01", "2026-01-05", 5),
        )
        conn.commit()

        conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()

        leaves = conn.execute("SELECT COUNT(*) FROM medical_leaves").fetchone()[0]
        assert leaves == 0

    def test_fk_rejects_unknown_employee(self, conn: sqlite3.Connection) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO medical_leaves (employee_id, leave_type, start_date, end_date, days) "
                "VALUES (?, ?, ?, ?, ?)",
                (99999, "enfermedad", "2026-01-01", "2026-01-05", 5),
            )

    def test_valid_insert_with_defaults(self, conn: sqlite3.Connection) -> None:
        emp_id = _seed_employee(conn)
        conn.execute(
            "INSERT INTO medical_leaves (employee_id, leave_type, start_date, end_date, days) "
            "VALUES (?, ?, ?, ?, ?)",
            (emp_id, "maternidad", "2026-02-01", "2026-05-01", 90),
        )
        conn.commit()

        row = conn.execute("SELECT * FROM medical_leaves").fetchone()
        assert row["status"] == "active"
        assert row["days"] == 90
        assert row["created_at"] is not None
        assert row["updated_at"] is not None
