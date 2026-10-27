"""Tests de seguridad para api_auth_required (MYK-443).

Antes del fix, cualquier header ``Authorization: Bearer <cualquier cosa>``
obtenia acceso completo CRUD a las rutas /api/*.

Estos tests FALLAN con el middleware sin validar (garbage token -> 200)
y PASAN con JWT real validado via Auth.verify_access_token.
Cubre al menos una ruta de cada blueprint API: employees,
attendance_stats, medical_leaves y alerts.
"""

import sqlite3
import tempfile
from pathlib import Path

import pytest
from flask import Flask

from src.buffer.repository import BufferRepository
from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.alerts import alerts_bp
from src.webgui.routes.attendance_stats import attendance_stats_bp
from src.webgui.routes.employees import employees_bp
from src.webgui.routes.medical_leaves import medical_leaves_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
SECRET = "test-secret-key"

BLUEPRINTS = {
    "employees": (
        employees_bp,
        "/api/employees",
        "/api/employees/",
        ("001_initial_schema.sql", "002_employees.sql", "011_employee_labor_data.sql"),
    ),
    "attendance_stats": (
        attendance_stats_bp,
        "/api/attendance",
        "/api/attendance/stats",
        ("001_initial_schema.sql", "002_employees.sql", "003_medical_leaves.sql"),
    ),
    "medical_leaves": (
        medical_leaves_bp,
        "/api/medical-leaves",
        "/api/medical-leaves/",
        ("001_initial_schema.sql", "002_employees.sql", "003_medical_leaves.sql"),
    ),
    "alerts": (
        alerts_bp,
        "/api/alerts",
        "/api/alerts/",
        ("001_initial_schema.sql", "002_employees.sql", "005_alerts.sql"),
    ),
}


def _build_app(name: str, with_auth: bool = True) -> Flask:
    bp, prefix, _path, migrations = BLUEPRINTS[name]
    tmp = Path(tempfile.mkdtemp())
    conn = sqlite3.connect(tmp / "webgui.db")
    conn.execute("PRAGMA foreign_keys = ON")
    for migration in migrations:
        conn.executescript((MIGRATIONS_DIR / migration).read_text())
    conn.close()

    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = SECRET
    app.db = Database(tmp / "webgui.db")
    app.buffer_repo = BufferRepository(tmp / "buffer.db")
    app.register_blueprint(bp, url_prefix=prefix)
    if with_auth:
        app.auth = Auth(SECRET)
    return app


def _bearer_header(expired: bool = False) -> dict:
    auth = Auth(SECRET)
    if expired:
        auth.token_expiry_minutes = -1
    token = auth.generate_tokens(1, "admin", "admin")["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture(params=sorted(BLUEPRINTS), ids=sorted(BLUEPRINTS))
def route(request):
    """(app, client, GET-path) para una ruta API de cada blueprint."""
    app = _build_app(request.param)
    return app.test_client(), BLUEPRINTS[request.param][2]


class TestApiAuthRequired:
    def test_missing_header_401(self, route):
        client, path = route
        resp = client.get(path)
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authorization header required"}

    def test_garbage_token_401(self, route):
        client, path = route
        resp = client.get(path, headers={"Authorization": "Bearer garbage"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_wrong_scheme_401(self, route):
        client, path = route
        resp = client.get(path, headers={"Authorization": "Basic x"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Bearer scheme required"}

    def test_malformed_header_401(self, route):
        client, path = route
        resp = client.get(path, headers={"Authorization": "NoSpacesHere"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid authorization format"}

    def test_expired_token_401(self, route):
        client, path = route
        resp = client.get(path, headers=_bearer_header(expired=True))
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_refresh_token_is_not_access_401(self, route):
        client, path = route
        auth = Auth(SECRET)
        refresh = auth.generate_tokens(1, "admin", "admin")["refresh_token"]
        resp = client.get(path, headers={"Authorization": f"Bearer {refresh}"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_valid_token_200(self, route):
        client, path = route
        resp = client.get(path, headers=_bearer_header())
        assert resp.status_code == 200, resp.get_data(as_text=True)

    def test_webgui_session_200(self, route):
        client, path = route
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        resp = client.get(path)
        assert resp.status_code == 200, resp.get_data(as_text=True)

    def test_app_without_auth_fails_closed(self, request):
        name = request.node.callspec.id if hasattr(request.node, "callspec") else "employees"
        app = _build_app(name, with_auth=False)
        client = app.test_client()
        path = BLUEPRINTS[name][2]
        resp = client.get(path, headers=_bearer_header())
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authentication is not configured"}


class TestExportRouteRequiresAuth:
    """GET /api/employees/export expone CURP/RFC/NSS (MYK-423): debe exigir
    @api_auth_required igual que el resto del blueprint (MYK-467).

    Regression: antes del fix, sin sesion ni token devolvia 200 con el CSV
    completo de colaboradores.
    """

    def _client(self):
        app = _build_app("employees")
        return app.test_client()

    def test_export_missing_header_401(self):
        resp = self._client().get("/api/employees/export")
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authorization header required"}

    def test_export_garbage_token_401(self):
        resp = self._client().get(
            "/api/employees/export", headers={"Authorization": "Bearer garbage"}
        )
        assert resp.status_code == 401

    def test_export_valid_token_200(self):
        resp = self._client().get("/api/employees/export", headers=_bearer_header())
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/csv")

    def test_export_webgui_session_200(self):
        client = self._client()
        with client.session_transaction() as sess:
            sess["user_id"] = 1
            sess["username"] = "admin"
            sess["role"] = "admin"
        resp = client.get("/api/employees/export")
        assert resp.status_code == 200
        assert resp.headers["Content-Type"].startswith("text/csv")
