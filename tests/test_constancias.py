"""Tests para el endpoint de constancia de asistencia en PDF (MYK-593).

Valida generacion del PDF, descarga adjunta, autenticacion, permiso
`reports:export`, empleado no encontrado/inactivo y validacion de rangos de fecha.
"""

import io
import shutil
import sqlite3
from datetime import date
from pathlib import Path

import pytest
from flask import Flask
from pypdf import PdfReader

from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.webgui.constancia import build_constancia_pdf
from src.webgui.database import Database
from src.webgui.routes.constancias import constancias_bp

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
MIGRATION_CHAIN = ("001_initial_schema.sql", "002_employees.sql", "003_medical_leaves.sql")

AUTH_HEADER_ADMIN = {
    "Authorization": "Bearer "
    + Auth("test-secret-key").generate_tokens(1, "admin", "admin")["access_token"]
}
# Rol legacy no presente en el catalogo RBAC: deny por defecto, sin reports:export.
AUTH_HEADER_NO_PERM = {
    "Authorization": "Bearer "
    + Auth("test-secret-key").generate_tokens(2, "usuario", "user")["access_token"]
}
START, END = "2026-10-05", "2026-10-09"


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path) -> Flask:
    shutil.copytree(MIGRATIONS_DIR, tmp_path / "migrations")
    db_path = tmp_path / "data" / "webgui.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    _apply_migrations(conn)
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth(app.config["SECRET_KEY"])
    app.buffer_repo = BufferRepository(tmp_path / "data" / "buffer.db")
    app.config["COMPANY_NAME"] = "ACME"
    app.register_blueprint(constancias_bp, url_prefix="/reportes")
    return app


@pytest.fixture
def client(tmp_path):
    app = _build_app(tmp_path)
    return app.test_client()


@pytest.fixture
def seeded(client):
    db = client.application.db
    buffer_repo = client.application.buffer_repo
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
        "employees",
        {
            "employee_code": "E002",
            "first_name": "Bob",
            "last_name": "Suarez",
            "department": "Ventas",
            "status": "inactive",
        },
    )
    db.insert(
        "employee_device_links",
        {"employee_id": ana_id, "device_serial": "SN1", "device_user_id": "1"},
    )
    with buffer_repo.get_connection() as conn:
        conn.execute(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip) "
            "VALUES ('1', '2026-10-05 08:55:00', 0, '10.0.0.5')"
        )
    return {"ana_id": ana_id}


def _url(employee_id: int, query: str = "") -> str:
    return f"/reportes/constancia/{employee_id}/pdf" + (f"?{query}" if query else "")


def _pdf_text(resp) -> str:
    reader = PdfReader(io.BytesIO(resp.data))
    return " ".join(page.extract_text() or "" for page in reader.pages)


class TestPdfService:
    def test_build_constancia_pdf_is_valid_pdf(self):
        pdf = build_constancia_pdf(
            employee_name="Ana Lopez",
            employee_code="E001",
            department="IT",
            hire_date="2020-01-01",
            period={"start_date": "2026-10-05", "end_date": "2026-10-09"},
            stats={
                "days_expected": 5,
                "days_present": 1,
                "days_absent": 4,
                "days_incapacity": 0,
                "days_vacation": 0,
                "late_arrivals": 0,
                "punctuality_pct": 100.0,
                "absenteeism_pct": 80.0,
            },
            company_name="ACME",
            issued_at=date(2026, 10, 10),
        )
        assert pdf.startswith(b"%PDF-")
        text = " ".join(page.extract_text() or "" for page in PdfReader(io.BytesIO(pdf)).pages)
        for token in (
            "Ana Lopez",
            "E001",
            "IT",
            "ACME",
            "2026-10-05",
            "2026-10-09",
            "CONSTANCIA DE ASISTENCIA",
        ):
            assert token in text, f"falta {token!r} en el PDF"


class TestAuth:
    def test_requires_authentication(self, client, seeded):
        resp = client.get(_url(seeded["ana_id"], f"start_date={START}&end_date={END}"))
        assert resp.status_code == 401

    def test_rejects_role_without_reports_export(self, client, seeded):
        resp = client.get(
            _url(seeded["ana_id"], f"start_date={START}&end_date={END}"),
            headers=AUTH_HEADER_NO_PERM,
        )
        assert resp.status_code == 403


class TestConstanciaPdf:
    def test_admin_downloads_constancia_pdf(self, client, seeded):
        resp = client.get(
            _url(seeded["ana_id"], f"start_date={START}&end_date={END}"),
            headers=AUTH_HEADER_ADMIN,
        )
        assert resp.status_code == 200
        assert resp.content_type == "application/pdf"
        assert "attachment" in (resp.headers.get("Content-Disposition") or "")
        assert f"constancia_E001_{START}_{END}.pdf" in (
            resp.headers.get("Content-Disposition") or ""
        )
        assert resp.data.startswith(b"%PDF-")
        text = _pdf_text(resp)
        for token in ("Ana Lopez", "E001", "IT", "ACME", "2026-10-05", "2026-10-09"):
            assert token in text

    def test_employee_not_found_returns_404(self, client):
        resp = client.get(
            _url(99999, f"start_date={START}&end_date={END}"), headers=AUTH_HEADER_ADMIN
        )
        assert resp.status_code == 404

    def test_inactive_employee_returns_404(self, client, seeded):
        bob_id = client.application.db.fetch_one(
            "SELECT id FROM employees WHERE employee_code = 'E002'"
        )["id"]
        resp = client.get(
            _url(bob_id, f"start_date={START}&end_date={END}"), headers=AUTH_HEADER_ADMIN
        )
        assert resp.status_code == 404

    def test_invalid_date_returns_400(self, client, seeded):
        resp = client.get(
            _url(seeded["ana_id"], "start_date=nope"),
            headers=AUTH_HEADER_ADMIN,
        )
        assert resp.status_code == 400

    def test_start_after_end_returns_400(self, client, seeded):
        resp = client.get(
            _url(seeded["ana_id"], f"start_date={END}&end_date={START}"),
            headers=AUTH_HEADER_ADMIN,
        )
        assert resp.status_code == 400

    def test_constancia_for_employee_without_attendance_still_generates(self, client, seeded):
        resp = client.get(
            _url(seeded["ana_id"], "start_date=2026-01-05&end_date=2026-01-09"),
            headers=AUTH_HEADER_ADMIN,
        )
        assert resp.status_code == 200
        assert resp.data.startswith(b"%PDF-")
