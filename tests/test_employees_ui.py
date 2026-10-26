"""Tests para la UI de colaboradores (MYK-230)."""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.database import Database
from src.webgui.routes.employees_ui import employees_ui_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    for name in (
        "001_initial_schema.sql",
        "002_employees.sql",
        "011_employee_labor_data.sql",
    ):
        conn.executescript((MIGRATIONS_DIR / name).read_text())
    conn.close()

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parents[1] / "src/webgui/templates"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.register_blueprint(employees_ui_bp, url_prefix="/colaboradores")
    return app


@pytest.fixture
def client(tmp_path: Path):
    app = _build_app(tmp_path)
    test_client = app.test_client()
    # MYK-451: las rutas de este blueprint requieren sesion/JWT.
    with test_client.session_transaction() as session:
        session["user_id"] = 1
    return test_client


def _seed_device(db, name="Reloj Entrada", address="192.168.1.10", serial="SN123456"):
    return db.insert(
        "devices",
        {
            "name": name,
            "address": address,
            "port": 4370,
            "password": 0,
            "timeout": 5,
            "protocol": "tcp",
            "serial_number": serial,
            "is_enabled": 1,
        },
    )


def test_colaboradores_page_renders(client):
    resp = client.get("/colaboradores/")
    assert resp.status_code == 200
    assert b"Colaboradores" in resp.data


def test_devices_endpoint_returns_serial(client):
    app_db = client.application.db
    device_id = _seed_device(app_db)
    resp = client.get("/colaboradores/api/devices")
    assert resp.status_code == 200
    devices = resp.get_json()["devices"]
    assert len(devices) == 1
    assert devices[0]["id"] == device_id
    assert devices[0]["serial_number"] == "SN123456"


def test_device_users_endpoint(client):
    app_db = client.application.db
    device_id = _seed_device(app_db)
    app_db.insert(
        "device_users",
        {"device_id": device_id, "user_id": "1001", "name": "Ana Lopez"},
    )
    resp = client.get(f"/colaboradores/api/devices/{device_id}/users")
    assert resp.status_code == 200
    users = resp.get_json()["users"]
    assert users == [{"user_id": "1001", "name": "Ana Lopez"}]


def test_device_users_unknown_device_404(client):
    assert client.get("/colaboradores/api/devices/999/users").status_code == 404


def _seed_employee(db, **extra):
    return db.insert(
        "employees",
        {"employee_code": "E001", "first_name": "Ana", "last_name": "Lopez", **extra},
    )


def test_expediente_page_renders(client):
    employee_id = _seed_employee(client.application.db)
    resp = client.get(f"/colaboradores/expediente/{employee_id}")
    assert resp.status_code == 200
    assert b"Expediente" in resp.data
    assert b"Incapacidades" in resp.data
    assert b"/api/medical-leaves/" in resp.data


def test_expediente_page_lists_employee_data(client):
    employee_id = _seed_employee(client.application.db, department="Operaciones")
    resp = client.get(f"/colaboradores/expediente/{employee_id}")
    assert b"Ana Lopez" in resp.data
    assert b"Operaciones" in resp.data


def test_expediente_unknown_employee_404(client):
    assert client.get("/colaboradores/expediente/999").status_code == 404


def test_colaboradores_list_links_expediente(client):
    _seed_employee(client.application.db)
    resp = client.get("/colaboradores/")
    assert resp.status_code == 200
    assert b"/colaboradores/expediente/" in resp.data


# --- MYK-423: datos laborales en la UI ---

VALID_CURP = "GARC850101HDFRRL09"


def test_colaboradores_form_has_labor_fields(client):
    resp = client.get("/colaboradores/")
    assert resp.status_code == 200
    assert b"CURP" in resp.data
    assert b"RFC" in resp.data
    assert b"NSS" in resp.data
    assert b"tipo_jornada" in resp.data


def test_expediente_lists_labor_data(client):
    employee_id = _seed_employee(
        client.application.db,
        curp=VALID_CURP,
        tipo_jornada="diurna",
        turno="matutino",
    )
    resp = client.get(f"/colaboradores/expediente/{employee_id}")
    assert resp.status_code == 200
    assert b"Datos laborales" in resp.data
    assert VALID_CURP.encode() in resp.data
    assert b"diurna" in resp.data
    assert b"matutino" in resp.data
