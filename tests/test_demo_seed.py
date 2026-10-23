"""Tests del seed de datos demo (migracion 007, MYK-377).

El seed debe dejar >=100 colaboradores, empresa (system_config),
dispositivos, usuarios WebGUI y vinculos; y ser idempotente (re-ejecutar
el SQL no duplica filas).
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.webgui.auth import Auth
from src.webgui.database import Database

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"


@pytest.fixture
def db(tmp_path, monkeypatch):
    shutil.copytree(MIGRATIONS_DIR, tmp_path / "migrations")
    (tmp_path / "data").mkdir()
    monkeypatch.setenv("ZK_DEMO_SEED", "1")
    database = Database(tmp_path / "data" / "webgui.db")
    database.initialize()
    return database


def _count(database, table):
    return database.fetch_one(f"SELECT COUNT(*) AS c FROM {table}")["c"]


def test_seed_provides_at_least_100_employees(db):
    assert _count(db, "employees") >= 100


def test_seed_exact_demo_counts(db):
    assert _count(db, "devices") == 3
    assert _count(db, "users") == 5
    assert _count(db, "device_users") == 40
    assert _count(db, "employee_device_links") == 40


def test_seed_empresa_config(db):
    row = db.fetch_one("SELECT value FROM system_config WHERE key = 'company_name'")
    assert row is not None
    assert row["value"] == "Empresa Demo S.A. de C.V."
    assert db.fetch_one(
        "SELECT value FROM system_config WHERE key = 'demo_seed_version'"
    )["value"] == "1"


def test_seed_demo_users_verify_with_demo_password(db):
    auth = Auth()
    users = db.fetch_all("SELECT username, password_hash FROM users ORDER BY username")
    assert len(users) == 5
    for user in users:
        assert auth.verify_password("demo1234", user["password_hash"]), user["username"]


def test_seed_links_reference_real_employees_and_devices(db):
    orphans = db.fetch_all(
        """
        SELECT l.employee_id FROM employee_device_links l
        WHERE l.employee_id NOT IN (SELECT id FROM employees)
           OR l.device_serial NOT IN
              (SELECT serial_number FROM devices)
        """
    )
    assert orphans == []
    serials = {row["serial_number"] for row in db.fetch_all("SELECT serial_number FROM devices")}
    assert serials == {"DEMO-SN-0001", "DEMO-SN-0002", "DEMO-SN-0003"}


def test_seed_sql_is_idempotent(db):
    """Ejecutar 007 dos veces mas no duplica filas (guards por llave natural)."""
    seed_sql = (MIGRATIONS_DIR / "007_demo_seed.sql").read_text()
    with sqlite3.connect(db.db_path) as conn:
        conn.executescript(seed_sql)
        conn.executescript(seed_sql)
    assert _count(db, "employees") == 120
    assert _count(db, "devices") == 3
    assert _count(db, "users") == 5
    assert _count(db, "device_users") == 40
    assert _count(db, "employee_device_links") == 40


def test_seed_has_active_and_inactive_employees(db):
    active = db.fetch_one("SELECT COUNT(*) AS c FROM employees WHERE status = 'active'")["c"]
    inactive = db.fetch_one("SELECT COUNT(*) AS c FROM employees WHERE status = 'inactive'")["c"]
    assert active >= 100
    assert inactive >= 5


def test_seed_departments_covered(db):
    depts = {
        row["department"]
        for row in db.fetch_all(
            "SELECT DISTINCT department FROM employees WHERE department IS NOT NULL"
        )
    }
    assert len(depts) >= 8
