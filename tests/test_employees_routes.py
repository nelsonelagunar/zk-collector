"""Tests para las rutas CRUD /api/employees (MYK-221)."""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.employees import employees_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"


def _apply_migrations(conn: sqlite3.Connection, *names: str) -> None:
    for name in names:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(
        conn,
        "001_initial_schema.sql",
        "002_employees.sql",
        "011_employee_labor_data.sql",
    )
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth(app.config["SECRET_KEY"])
    app.register_blueprint(employees_bp, url_prefix="/api/employees")
    return app


@pytest.fixture
def client(tmp_path: Path):
    app = _build_app(tmp_path)
    client = app.test_client()
    # MYK-443: /api/employees requiere auth — sesión WebGUI válida
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "admin"
        sess["role"] = "admin"
    return client


def _create(client, code="E001", first="Ana", last="Lopez", **extra):
    payload = {"employee_code": code, "first_name": first, "last_name": last, **extra}
    return client.post("/api/employees/", json=payload)


class TestListEmployees:
    def test_empty_list(self, client):
        resp = client.get("/api/employees/")
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["employees"] == []
        assert data["pagination"]["total"] == 0

    def test_list_pagination_and_filters(self, client):
        for code, first, last, dept in [
            ("E001", "Ana", "Lopez", "RH"),
            ("E002", "Beto", "Perez", "IT"),
            ("E003", "Carla", "Ruiz", "RH"),
        ]:
            assert _create(client, code, first, last, department=dept).status_code == 201

        resp = client.get("/api/employees/?per_page=2&page=1")
        data = resp.get_json()
        assert len(data["employees"]) == 2
        assert data["pagination"]["total"] == 3
        assert data["pagination"]["total_pages"] == 2

        resp = client.get("/api/employees/?department=RH")
        assert [e["employee_code"] for e in resp.get_json()["employees"]] == ["E001", "E003"]

        resp = client.get("/api/employees/?search=beto")
        assert [e["employee_code"] for e in resp.get_json()["employees"]] == ["E002"]

        resp = client.get("/api/employees/?status=inactive")
        assert resp.get_json()["pagination"]["total"] == 0


class TestCreateEmployee:
    def test_create_ok(self, client):
        resp = _create(client, "E100", "Ana", "Lopez", department="RH")
        assert resp.status_code == 201
        emp = resp.get_json()["employee"]
        assert emp["employee_code"] == "E100"
        assert emp["status"] == "active"

    def test_create_missing_required(self, client):
        resp = client.post("/api/employees/", json={"first_name": "Ana"})
        assert resp.status_code == 400
        assert "employee_code" in resp.get_json()["error"]
        assert "last_name" in resp.get_json()["error"]

    def test_create_duplicate_code(self, client):
        assert _create(client, "E200").status_code == 201
        resp = _create(client, "E200", "Otro", "Perez")
        assert resp.status_code == 409


class TestGetUpdateDelete:
    def test_get_404(self, client):
        assert client.get("/api/employees/999").status_code == 404

    def test_update_ok(self, client):
        emp_id = _create(client, "E300").get_json()["employee"]["id"]
        resp = client.put(f"/api/employees/{emp_id}", json={"first_name": "Anabel"})
        assert resp.status_code == 200
        assert resp.get_json()["employee"]["first_name"] == "Anabel"

    def test_update_404(self, client):
        resp = client.put("/api/employees/999", json={"first_name": "X"})
        assert resp.status_code == 404

    def test_delete_soft(self, client):
        emp_id = _create(client, "E400").get_json()["employee"]["id"]
        resp = client.delete(f"/api/employees/{emp_id}")
        assert resp.status_code == 200

        after = client.get(f"/api/employees/{emp_id}").get_json()["employee"]
        assert after["status"] == "inactive"

    def test_delete_404(self, client):
        assert client.delete("/api/employees/999").status_code == 404


class TestDeviceLinks:
    def test_link_list_unlink(self, client):
        emp_id = _create(client, "E500").get_json()["employee"]["id"]

        resp = client.post(
            f"/api/employees/{emp_id}/device-links",
            json={"device_serial": "SN1", "device_user_id": "u1"},
        )
        assert resp.status_code == 201

        resp = client.get(f"/api/employees/{emp_id}/device-links")
        assert len(resp.get_json()["device_links"]) == 1

        resp = client.delete(
            f"/api/employees/{emp_id}/device-links",
            json={"device_serial": "SN1", "device_user_id": "u1"},
        )
        assert resp.status_code == 200

        resp = client.get(f"/api/employees/{emp_id}/device-links")
        assert resp.get_json()["device_links"] == []

    def test_link_missing_fields(self, client):
        emp_id = _create(client, "E501").get_json()["employee"]["id"]
        resp = client.post(f"/api/employees/{emp_id}/device-links", json={"device_serial": "SN1"})
        assert resp.status_code == 400

    def test_link_duplicate(self, client):
        emp_id = _create(client, "E502").get_json()["employee"]["id"]
        payload = {"device_serial": "SN1", "device_user_id": "u1"}
        assert client.post(f"/api/employees/{emp_id}/device-links", json=payload).status_code == 201
        assert client.post(f"/api/employees/{emp_id}/device-links", json=payload).status_code == 409


# --- MYK-423: datos laborales (validacion CURP/RFC/NSS/tipo jornada + export) ---

VALID_CURP = "GARC850101HDFRRL09"
VALID_RFC_FISICA = "GARC850101H45"
VALID_NSS = "12345678901"


class TestLaborDataValidation:
    def test_create_with_labor_data(self, client):
        resp = _create(
            client,
            "L100",
            "Ana",
            "Lopez",
            curp=VALID_CURP,
            rfc=VALID_RFC_FISICA,
            nss=VALID_NSS,
            tipo_jornada="diurna",
            turno="matutino",
        )
        assert resp.status_code == 201
        emp = resp.get_json()["employee"]
        assert emp["curp"] == VALID_CURP
        assert emp["rfc"] == VALID_RFC_FISICA
        assert emp["nss"] == VALID_NSS
        assert emp["tipo_jornada"] == "diurna"
        assert emp["turno"] == "matutino"

    def test_create_normalizes_lowercase_curp(self, client):
        resp = _create(client, "L101", curp=VALID_CURP.lower())
        assert resp.status_code == 201
        assert resp.get_json()["employee"]["curp"] == VALID_CURP

    def test_create_rejects_malformed_curp(self, client):
        resp = _create(client, "L102", curp="GARC850101HDF")
        assert resp.status_code == 400
        assert "curp" in resp.get_json()["error"]

    def test_create_rejects_curp_with_unknown_entity(self, client):
        resp = _create(client, "L103", curp="GARC850101HXXRRL09")
        assert resp.status_code == 400
        assert "curp" in resp.get_json()["error"]

    def test_create_rejects_malformed_rfc(self, client):
        resp = _create(client, "L104", rfc="GARC")
        assert resp.status_code == 400
        assert "rfc" in resp.get_json()["error"]

    def test_create_rejects_bad_nss(self, client):
        resp = _create(client, "L105", nss="1234567890")
        assert resp.status_code == 400
        assert "nss" in resp.get_json()["error"]

    def test_create_rejects_bad_tipo_jornada(self, client):
        resp = _create(client, "L106", tipo_jornada="vespertina")
        assert resp.status_code == 400
        assert "tipo_jornada" in resp.get_json()["error"]

    def test_create_accepts_moral_rfc_12(self, client):
        resp = _create(client, "L107", rfc="ABC850101XYZ")
        assert resp.status_code == 201
        assert resp.get_json()["employee"]["rfc"] == "ABC850101XYZ"

    def test_update_rejects_malformed_curp(self, client):
        emp_id = _create(client, "L108").get_json()["employee"]["id"]
        resp = client.put(f"/api/employees/{emp_id}", json={"curp": "no-es-una-curp"})
        assert resp.status_code == 400
        assert "curp" in resp.get_json()["error"]

    def test_update_accepts_valid_curp(self, client):
        emp_id = _create(client, "L109").get_json()["employee"]["id"]
        resp = client.put(f"/api/employees/{emp_id}", json={"curp": VALID_CURP})
        assert resp.status_code == 200
        assert resp.get_json()["employee"]["curp"] == VALID_CURP

    def test_empty_labor_fields_are_ignored(self, client):
        resp = _create(client, "L110", curp="", rfc="", nss="", tipo_jornada="", turno="")
        assert resp.status_code == 201
        emp = resp.get_json()["employee"]
        assert emp["curp"] is None
        assert emp["rfc"] is None
        assert emp["nss"] is None
        assert emp["tipo_jornada"] is None
        assert emp["turno"] is None


class TestEmployeesExport:
    def test_export_includes_curp_and_rfc(self, client):
        assert _create(client, "L200", curp=VALID_CURP, rfc=VALID_RFC_FISICA).status_code == 201
        resp = client.get("/api/employees/export")
        assert resp.status_code == 200
        text = resp.get_data(as_text=True)
        assert "curp" in text
        assert "rfc" in text
        assert VALID_CURP in text
        assert VALID_RFC_FISICA in text

    def test_export_respects_status_filter(self, client):
        assert _create(client, "L201", curp=VALID_CURP).status_code == 201
        resp = client.get("/api/employees/export?status=inactive")
        assert resp.status_code == 200
        assert VALID_CURP not in resp.get_data(as_text=True)
