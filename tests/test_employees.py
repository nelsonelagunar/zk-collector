"""
Tests para la migracion 002 (employees) y el EmployeeRepository (MYK-220).
"""

import shutil
import sqlite3
from pathlib import Path

import pytest

from src.webgui.database import Database
from src.webgui.employees import EmployeeRepository

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_SRC = REPO_ROOT / "migrations"


@pytest.fixture
def db(tmp_path):
    """Database con la estructura de migraciones real (001 + 002) aplicadas."""
    shutil.copytree(MIGRATIONS_SRC, tmp_path / "migrations")
    database = Database(tmp_path / "data" / "webgui.db")
    database.initialize()
    return database


@pytest.fixture
def repo(db):
    return EmployeeRepository(db)


def test_migration_creates_tables(db):
    tables = db.fetch_all("SELECT name FROM sqlite_master WHERE type = 'table' ORDER BY name")
    names = {row["name"] for row in tables}
    assert {"employees", "employee_device_links"}.issubset(names)


def test_migration_idempotent(db):
    db.initialize()
    applied = db.fetch_all("SELECT name FROM _migrations ORDER BY name")
    assert [row["name"] for row in applied].count("002_employees.sql") == 1


def test_migration_indexes(db):
    indexes = db.fetch_all(
        "SELECT name FROM sqlite_master WHERE type = 'index' AND tbl_name IN "
        "('employees', 'employee_device_links')"
    )
    names = {row["name"] for row in indexes}
    assert "idx_employees_status" in names
    assert "idx_employee_device_links_employee_id" in names


def test_employee_code_unique_enforced(db):
    conn = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (employee_code) VALUES ('E-001')")
        conn.execute("INSERT INTO employees (employee_code) VALUES ('E-001')")
    conn.close()


def test_status_check_constraint(db):
    conn = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (employee_code, status) VALUES ('E-002', 'fired')")
    conn.close()


def test_fk_cascade_on_delete(db):
    conn = sqlite3.connect(str(db.db_path))
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("INSERT INTO employees (employee_code) VALUES ('E-003')")
    employee_id = conn.execute("SELECT id FROM employees WHERE employee_code = 'E-003'").fetchone()[
        0
    ]
    conn.execute(
        "INSERT INTO employee_device_links (employee_id, device_serial, device_user_id) "
        "VALUES (?, 'SERIAL1', '100')",
        (employee_id,),
    )
    conn.commit()
    conn.execute("DELETE FROM employees WHERE id = ?", (employee_id,))
    conn.commit()
    links = conn.execute(
        "SELECT COUNT(*) FROM employee_device_links WHERE employee_id = ?", (employee_id,)
    ).fetchone()[0]
    conn.close()
    assert links == 0


def test_crud_create_and_get(repo):
    employee_id = repo.create(
        {
            "employee_code": "E-100",
            "first_name": "Ada",
            "last_name": "Lovelace",
            "email": "ada@example.com",
        }
    )
    assert employee_id > 0

    row = repo.get(employee_id)
    assert row["employee_code"] == "E-100"
    assert row["status"] == "active"


def test_create_requires_employee_code(repo):
    with pytest.raises(ValueError):
        repo.create({"first_name": "Sin codigo"})


def test_create_rejects_invalid_status(repo):
    with pytest.raises(ValueError):
        repo.create({"employee_code": "E-101", "status": "fired"})


def test_get_by_code(repo):
    repo.create({"employee_code": "E-102", "first_name": "Grace"})
    row = repo.get_by_code("E-102")
    assert row["first_name"] == "Grace"


def test_list_filter_by_status(repo):
    repo.create({"employee_code": "E-103", "status": "active"})
    repo.create({"employee_code": "E-104", "status": "inactive"})
    active = repo.list_employees(status="active")
    assert [r["employee_code"] for r in active] == ["E-103"]


def test_list_search(repo):
    repo.create({"employee_code": "E-108", "first_name": "Alan", "last_name": "Turing"})
    repo.create({"employee_code": "E-109", "first_name": "Grace", "last_name": "Hopper"})
    rows = repo.list_employees(search="turing")
    assert [r["employee_code"] for r in rows] == ["E-108"]


def test_link_device_requires_ids(repo):
    employee_id = repo.create({"employee_code": "E-110"})
    with pytest.raises(ValueError):
        repo.link_device(employee_id, "", "100")


def test_update_and_set_status(repo):
    employee_id = repo.create({"employee_code": "E-105", "first_name": "Old"})
    repo.update(employee_id, {"first_name": "New", "department": "IT"})
    row = repo.get(employee_id)
    assert row["first_name"] == "New"
    assert row["department"] == "IT"

    repo.set_status(employee_id, "inactive")
    assert repo.get(employee_id)["status"] == "inactive"


def test_link_unlink_and_list_links(repo):
    employee_id = repo.create({"employee_code": "E-106"})

    assert repo.link_device(employee_id, "SERIAL-A", "100") == 1
    # Duplicado: ignorado por UNIQUE (idempotente)
    assert repo.link_device(employee_id, "SERIAL-A", "100") == 0

    links = repo.list_links(employee_id)
    assert len(links) == 1
    assert links[0]["device_serial"] == "SERIAL-A"

    assert repo.unlink_device(employee_id, "SERIAL-A", "100") == 1
    assert repo.list_links(employee_id) == []


def test_delete_removes_links(repo):
    employee_id = repo.create({"employee_code": "E-107"})
    repo.link_device(employee_id, "SERIAL-B", "200")

    assert repo.delete(employee_id) == 1
    assert repo.get(employee_id) is None
    assert repo.list_links(employee_id) == []


# --- MYK-423: datos laborales (migracion 011 + validacion de formato) ---

VALID_CURP = "GARC850101HDFRRL09"
VALID_RFC_FISICA = "GARC850101H45"
VALID_NSS = "12345678901"


def test_migration_011_adds_labor_columns(db):
    columns = {row["name"] for row in db.fetch_all("PRAGMA table_info(employees)")}
    assert {"curp", "rfc", "nss", "imss_numero_seguro", "tipo_jornada", "turno"}.issubset(columns)


def test_migration_011_length_and_enum_checks(db):
    conn = sqlite3.connect(str(db.db_path))
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (employee_code, curp) VALUES ('L-001', 'GARC')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute("INSERT INTO employees (employee_code, nss) VALUES ('L-002', '123')")
    with pytest.raises(sqlite3.IntegrityError):
        conn.execute(
            "INSERT INTO employees (employee_code, tipo_jornada) VALUES ('L-003', 'vespertina')"
        )
    conn.close()


def test_migration_011_accepts_valid_values(db):
    conn = sqlite3.connect(str(db.db_path))
    conn.execute(
        "INSERT INTO employees (employee_code, curp, rfc, nss, tipo_jornada, turno) "
        "VALUES ('L-004', ?, ?, ?, 'nocturna', 'nocturno A')",
        (VALID_CURP, VALID_RFC_FISICA, VALID_NSS),
    )
    conn.commit()
    row = conn.execute(
        "SELECT curp, tipo_jornada FROM employees WHERE employee_code = 'L-004'"
    ).fetchone()
    conn.close()
    assert tuple(row) == (VALID_CURP, "nocturna")


def test_repository_rejects_malformed_curp(repo):
    with pytest.raises(ValueError, match="curp"):
        repo.create({"employee_code": "L-005", "curp": "GARC850101HDF"})


def test_repository_normalizes_lowercase_curp(repo):
    employee_id = repo.create({"employee_code": "L-006", "curp": VALID_CURP.lower()})
    assert repo.get(employee_id)["curp"] == VALID_CURP


def test_repository_rejects_malformed_rfc(repo):
    with pytest.raises(ValueError, match="rfc"):
        repo.create({"employee_code": "L-007", "rfc": "GARC"})


def test_repository_rejects_bad_nss(repo):
    with pytest.raises(ValueError, match="nss"):
        repo.create({"employee_code": "L-008", "nss": "1234567890"})


def test_repository_rejects_bad_tipo_jornada(repo):
    with pytest.raises(ValueError, match="tipo_jornada"):
        repo.create({"employee_code": "L-009", "tipo_jornada": "vespertina"})


def test_repository_update_does_not_clear_absent_fields(repo):
    employee_id = repo.create({"employee_code": "L-010", "curp": VALID_CURP})
    repo.update(employee_id, {"first_name": "Ana"})
    assert repo.get(employee_id)["curp"] == VALID_CURP


def test_repository_update_rejects_malformed_curp(repo):
    employee_id = repo.create({"employee_code": "L-011"})
    with pytest.raises(ValueError, match="curp"):
        repo.update(employee_id, {"curp": "XYZ"})
