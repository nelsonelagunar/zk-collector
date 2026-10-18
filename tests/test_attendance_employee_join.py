"""Tests para el join de nombre de colaborador en asistencia (MYK-221 req 3)."""

import sqlite3
from pathlib import Path

from src.webgui.database import Database
from src.webgui.routes.attendance import resolve_employee_names

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def _apply_migrations(conn: sqlite3.Connection, *names: str) -> None:
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_db(tmp_path: Path) -> Database:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn, "001_initial_schema.sql", "002_employees.sql")
    conn.close()
    return Database(db_path)


def test_resolve_employee_name_via_link(tmp_path):
    db = _build_db(tmp_path)

    # seed device with known serial + employee + link
    db.execute(
        "INSERT INTO devices (name, address, serial_number) VALUES (?, ?, ?)",
        ("Reloj 1", "192.168.1.10", "SN1"),
    )
    emp_id = db.create_employee(
        {"employee_code": "E001", "first_name": "Ana", "last_name": "Lopez"}
    )
    db.link_employee_to_device(emp_id, "SN1", "u1")

    rows = [
        {"device_ip": "192.168.1.10", "user_id": "u1"},
        {"device_ip": "192.168.1.10", "user_id": "u9"},  # no link
        {"device_ip": "192.168.1.99", "user_id": "u1"},  # no device
    ]

    resolved = resolve_employee_names(db, rows)

    assert resolved[("192.168.1.10", "u1")] == "Ana Lopez"
    assert ("192.168.1.10", "u9") not in resolved
    assert ("192.168.1.99", "u1") not in resolved


def test_resolve_no_links_no_crash(tmp_path):
    db = _build_db(tmp_path)
    rows = [{"device_ip": "192.168.1.10", "user_id": "u1"}]
    assert resolve_employee_names(db, rows) == {}
