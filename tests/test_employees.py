"""Tests for the employees migration (002) and its CRUD helpers (MYK-220)."""

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
    _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql")
    conn.close()
    return Database(db_path)


class TestEmployeesMigration:
    def test_tables_and_indexes_exist(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql")

        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        assert {"employees", "employee_device_links"} <= tables

        indexes = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='index'")}
        assert {
            "idx_employees_code",
            "idx_employees_status",
            "idx_employee_device_links_serial",
            "idx_employee_device_links_user",
        } <= indexes
        conn.close()

    def test_idempotent_apply(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql")
        _apply_migrations(conn, "002_employees.sql")  # must not raise
        conn.close()

    def test_employee_code_unique(self, db: Database) -> None:
        db.create_employee(
            {"employee_code": "E001", "first_name": "Ana", "last_name": "Lopez"}
        )
        with pytest.raises(sqlite3.IntegrityError):
            db.create_employee(
                {"employee_code": "E001", "first_name": "Otro", "last_name": "Perez"}
            )

    def test_status_check_constraint(self, db: Database) -> None:
        with pytest.raises(sqlite3.IntegrityError):
            db.create_employee(
                {
                    "employee_code": "E002",
                    "first_name": "Ana",
                    "last_name": "Lopez",
                    "status": "bogus",
                }
            )

    def test_fk_cascade_on_employee_delete(self, tmp_path: Path) -> None:
        conn = _connect(tmp_path / "webgui.db")
        _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql")
        cur = conn.execute(
            "INSERT INTO employees (employee_code, first_name, last_name) VALUES (?, ?, ?)",
            ("E1", "Ana", "Lopez"),
        )
        emp_id = cur.lastrowid
        conn.execute(
            "INSERT INTO employee_device_links "
            "(employee_id, device_serial, device_user_id) VALUES (?, ?, ?)",
            (emp_id, "SN1", "u1"),
        )
        conn.commit()

        conn.execute("DELETE FROM employees WHERE id = ?", (emp_id,))
        conn.commit()

        links = conn.execute("SELECT COUNT(*) FROM employee_device_links").fetchone()[0]
        assert links == 0
        conn.close()


class TestEmployeesCrud:
    def test_create_and_get(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E100", "first_name": "Ana", "last_name": "Lopez", "department": "RH"}
        )
        assert emp_id > 0

        by_code = db.get_employee_by_code("E100")
        assert by_code is not None
        assert by_code["first_name"] == "Ana"
        assert by_code["status"] == "active"

        by_id = db.get_employee_by_id(emp_id)
        assert by_id is not None
        assert by_id["employee_code"] == "E100"

    def test_timestamps_defaulted_on_create(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E101", "first_name": "Ana", "last_name": "Lopez"}
        )
        row = db.get_employee_by_id(emp_id)
        assert row is not None
        assert row["created_at"] is not None
        assert row["updated_at"] is not None

    def test_get_employees_filters(self, db: Database) -> None:
        db.create_employee(
            {"employee_code": "E200", "first_name": "Ana", "last_name": "Lopez", "department": "RH"}
        )
        db.create_employee(
            {
                "employee_code": "E201",
                "first_name": "Beto",
                "last_name": "Perez",
                "department": "IT",
            }
        )

        assert len(db.get_employees()) == 2
        assert len(db.get_employees(department="RH")) == 1
        assert db.get_employees(department="RH")[0]["employee_code"] == "E200"
        assert db.get_employees(status="inactive") == []

    def test_update_employee_refreshes_updated_at(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E300", "first_name": "Ana", "last_name": "Lopez"}
        )

        db.update_employee(emp_id, {"first_name": "Anabel"})
        after = db.get_employee_by_id(emp_id)

        assert after["first_name"] == "Anabel"
        assert after["updated_at"] is not None

    def test_delete_employee_is_soft(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E400", "first_name": "Ana", "last_name": "Lopez"}
        )
        db.delete_employee(emp_id)

        row = db.get_employee_by_id(emp_id)
        assert row is not None
        assert row["status"] == "inactive"

    def test_link_unlink_and_lookups(self, db: Database) -> None:
        emp_id = db.create_employee(
            {"employee_code": "E500", "first_name": "Ana", "last_name": "Lopez"}
        )

        # seed a device so the reverse JOIN in get_devices_for_employee resolves
        db.execute(
            "INSERT INTO devices (name, address, serial_number) VALUES (?, ?, ?)",
            ("Reloj 1", "192.168.1.10", "SN500"),
        )

        db.link_employee_to_device(emp_id, "SN500", "u500")
        assert len(db.get_devices_for_employee(emp_id)) == 1
        assert len(db.get_employees_for_device("SN500", "u500")) == 1

        db.unlink_employee_from_device(emp_id, "SN500", "u500")
        assert db.get_devices_for_employee(emp_id) == []
