"""Tests para la landing page publica "Attendance Controller" (MYK-409).

La landing es publica (fuera del login): debe renderizar con y sin sesion,
y el formulario de contacto debe guardar el lead en `landing_leads` con
flash de confirmacion (sin SMTP).
"""

import sqlite3
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.landing import landing_bp

REPO_ROOT = Path(__file__).resolve().parents[1]
MIGRATIONS_DIR = REPO_ROOT / "migrations"
WEBGUI_DIR = REPO_ROOT / "src" / "webgui"
MIGRATION_CHAIN = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "003_medical_leaves.sql",
    "004_password_reset_tokens.sql",
    "005_landing_leads.sql",
)


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())
    conn.close()

    app = Flask(
        __name__,
        template_folder=str(WEBGUI_DIR / "templates"),
        static_folder=str(WEBGUI_DIR / "static"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth(app.config["SECRET_KEY"])
    app.register_blueprint(landing_bp)
    return app


@pytest.fixture
def client(tmp_path: Path):
    return _build_app(tmp_path).test_client()


def _lead_count(app: Flask) -> int:
    rows = app.db.fetch_all("SELECT id FROM landing_leads")
    return len(rows)


def test_landing_renders_without_session(client):
    resp = client.get("/landing")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Attendance Controller" in body
    assert "ZKTeco" in body
    assert 'action="/landing/contact"' in body
    assert 'id="contacto"' in body


def test_landing_renders_with_session(client):
    with client.session_transaction() as session:
        session["user_id"] = 1
        session["username"] = "admin"
    resp = client.get("/landing")
    assert resp.status_code == 200
    body = resp.data.decode()
    assert "Attendance Controller" in body
    # Con sesion activa el navbar del WebGUI tambien renderiza (misma identidad)
    assert "Cerrar Sesión" in body


def test_contact_saves_lead_and_flashes_confirmation(client):
    resp = client.post(
        "/landing/contact",
        data={
            "name": "María Gómez",
            "email": "maria@empresa.com",
            "company": "Empresa ACME",
            "phone": "+52 55 1234 5678",
            "message": "Tenemos 3 relojes K40 y 40 colaboradores.",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "¡Gracias! Hemos recibido tu solicitud" in resp.data.decode()

    lead = client.application.db.fetch_one(
        "SELECT * FROM landing_leads WHERE email = ?", ("maria@empresa.com",)
    )
    assert lead is not None
    assert lead["name"] == "María Gómez"
    assert lead["company"] == "Empresa ACME"
    assert lead["phone"] == "+52 55 1234 5678"
    assert lead["message"] == "Tenemos 3 relojes K40 y 40 colaboradores."
    assert lead["created_at"]


def test_contact_prg_redirect_targets_landing_anchor(client):
    resp = client.post(
        "/landing/contact",
        data={"name": "Juan", "email": "juan@test.com"},
    )
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/landing#contacto")


def test_contact_missing_required_fields_not_saved(client):
    for payload in (
        {"email": "solo-email@test.com"},  # sin nombre
        {"name": "Solo Nombre"},  # sin email
    ):
        resp = client.post("/landing/contact", data=payload)
        assert resp.status_code == 200
        assert "Por favor completa tu nombre y un correo válido" in resp.data.decode()
        assert _lead_count(client.application) == 0


def test_contact_invalid_email_not_saved(client):
    resp = client.post(
        "/landing/contact",
        data={"name": "Robot", "email": "no-es-un-correo"},
    )
    assert resp.status_code == 200
    assert "Por favor completa tu nombre y un correo válido" in resp.data.decode()
    assert _lead_count(client.application) == 0


def test_contact_honeypot_fakes_success_without_saving(client):
    resp = client.post(
        "/landing/contact",
        data={"name": "Bot", "email": "bot@spam.com", "website": "http://spam.example"},
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert "¡Gracias!" in resp.data.decode()
    assert _lead_count(client.application) == 0


def test_contact_trims_and_cuts_oversized_values(client):
    resp = client.post(
        "/landing/contact",
        data={
            "name": "  Nombre Con Espacios  ",
            "email": "correo@test.com",
            "message": "x" * 5000,
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    lead = client.application.db.fetch_one(
        "SELECT * FROM landing_leads WHERE email = ?", ("correo@test.com",)
    )
    assert lead is not None
    assert lead["name"] == "Nombre Con Espacios"
    assert len(lead["message"]) == 2000
