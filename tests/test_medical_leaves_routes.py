"""Tests para las rutas CRUD /api/medical-leaves (MYK-239)."""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.medical_leaves import medical_leaves_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_CHAIN = ("001_initial_schema.sql", "002_employees.sql", "003_medical_leaves.sql")

# JWT real firmado con el mismo secreto de la app (MYK-443: el middleware valida)
AUTH_HEADER = {
    "Authorization": "Bearer "
    + Auth("test-secret-key").generate_tokens(1, "admin", "admin")["access_token"]
}


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth(app.config["SECRET_KEY"])
    app.register_blueprint(medical_leaves_bp, url_prefix="/api/medical-leaves")
    return app


@pytest.fixture
def client(tmp_path: Path):
    app = _build_app(tmp_path)
    return app.test_client()


@pytest.fixture
def employee_id(client):
    return client.application.db.insert(
        "employees",
        {"employee_code": "E001", "first_name": "Ana", "last_name": "Lopez"},
    )


def _payload(employee_id, **extra):
    return {
        "employee_id": employee_id,
        "leave_type": "enfermedad",
        "start_date": "2026-01-01",
        "end_date": "2026-01-05",
        **extra,
    }


def _create(client, employee_id, **extra):
    return client.post(
        "/api/medical-leaves/",
        json=_payload(employee_id, **extra),
        headers=AUTH_HEADER,
    )


class TestAuth:
    def test_requires_authorization_header(self, client):
        resp = client.get("/api/medical-leaves/")
        assert resp.status_code == 401

    def test_accepts_bearer_token(self, client, employee_id):
        resp = client.get("/api/medical-leaves/", headers=AUTH_HEADER)
        assert resp.status_code == 200


class TestListMedicalLeaves:
    def test_empty_list(self, client):
        resp = client.get("/api/medical-leaves/", headers=AUTH_HEADER)
        assert resp.status_code == 200
        data = resp.get_json()
        assert data["leaves"] == []
        assert data["pagination"]["total"] == 0

    def test_pagination_and_filter(self, client, employee_id):
        db = client.application.db
        other_employee = db.insert("employees", {"employee_code": "E002"})
        first = _create(client, employee_id, start_date="2026-01-01", end_date="2026-01-02")
        second = _create(client, employee_id, start_date="2026-02-01", end_date="2026-02-02")
        assert first.status_code == 201
        assert second.status_code == 201
        assert _create(client, other_employee).status_code == 201

        resp = client.get(
            "/api/medical-leaves/?per_page=1&page=1",
            headers=AUTH_HEADER,
        )
        data = resp.get_json()
        assert len(data["leaves"]) == 1
        assert data["pagination"]["total"] == 3
        assert data["pagination"]["total_pages"] == 3

        resp = client.get(
            f"/api/medical-leaves/?employee_id={employee_id}",
            headers=AUTH_HEADER,
        )
        data = resp.get_json()
        assert data["pagination"]["total"] == 2
        assert all(row["employee_id"] == employee_id for row in data["leaves"])


class TestCreateMedicalLeave:
    def test_create_ok(self, client, employee_id):
        resp = _create(client, employee_id, doctor_name="Dra. House")
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["leave"]["days"] == 5
        assert data["leave"]["status"] == "active"
        assert data["warnings"] == []

    def test_days_from_client_are_ignored(self, client, employee_id):
        resp = _create(client, employee_id, days=99)
        assert resp.status_code == 201
        assert resp.get_json()["leave"]["days"] == 5

    def test_invalid_dates(self, client, employee_id):
        payload = _payload(employee_id, start_date="2026-01-10", end_date="2026-01-01")
        resp = client.post(
            "/api/medical-leaves/",
            json=payload,
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 400

    def test_invalid_leave_type(self, client, employee_id):
        resp = _create(client, employee_id, leave_type="vacaciones")
        assert resp.status_code == 400

    def test_unknown_employee(self, client):
        resp = _create(client, 99999)
        assert resp.status_code == 400

    def test_document_ref_dict_is_serialized(self, client, employee_id):
        resp = _create(client, employee_id, document_ref={"bucket": "s3://incidencias/1.pdf"})
        assert resp.status_code == 201
        assert resp.get_json()["leave"]["document_ref"] == '{"bucket": "s3://incidencias/1.pdf"}'


class TestGetUpdateDelete:
    def test_get_404(self, client):
        resp = client.get("/api/medical-leaves/999", headers=AUTH_HEADER)
        assert resp.status_code == 404

    def test_get_ok(self, client, employee_id):
        leave_id = _create(client, employee_id).get_json()["leave"]["id"]
        resp = client.get(f"/api/medical-leaves/{leave_id}", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()["leave"]["id"] == leave_id

    def test_update_recomputes_days(self, client, employee_id):
        leave_id = _create(client, employee_id).get_json()["leave"]["id"]
        resp = client.put(
            f"/api/medical-leaves/{leave_id}",
            json={"end_date": "2026-01-08", "days": 1},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 200
        assert resp.get_json()["leave"]["days"] == 8

    def test_update_404(self, client):
        resp = client.put(
            "/api/medical-leaves/999",
            json={"end_date": "2026-01-08"},
            headers=AUTH_HEADER,
        )
        assert resp.status_code == 404

    def test_delete_soft_cancel(self, client, employee_id):
        leave_id = _create(client, employee_id).get_json()["leave"]["id"]
        resp = client.delete(f"/api/medical-leaves/{leave_id}", headers=AUTH_HEADER)
        assert resp.status_code == 200
        assert resp.get_json()["leave"]["status"] == "cancelled"

    def test_delete_404(self, client):
        resp = client.delete("/api/medical-leaves/999", headers=AUTH_HEADER)
        assert resp.status_code == 404


class TestVacationOverlapWarning:
    def test_create_returns_warning_when_overlap(self, client, employee_id):
        db = client.application.db
        with db.get_connection() as conn:
            conn.execute(
                """
                CREATE TABLE vacation_requests (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    employee_id INTEGER NOT NULL,
                    start_date DATE NOT NULL,
                    end_date DATE NOT NULL,
                    status TEXT NOT NULL
                )
                """
            )
            conn.execute(
                """
                INSERT INTO vacation_requests (employee_id, start_date, end_date, status)
                VALUES (?, '2026-01-01', '2026-01-05', 'approved')
                """,
                (employee_id,),
            )

        resp = _create(client, employee_id)
        assert resp.status_code == 201
        assert len(resp.get_json()["warnings"]) == 1

    def test_create_without_vacation_table_returns_no_warnings(self, client, employee_id):
        resp = _create(client, employee_id)
        assert resp.status_code == 201
        assert resp.get_json()["warnings"] == []
