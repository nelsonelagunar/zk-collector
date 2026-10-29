"""Test RBAC matriz permiso->ruta aplicada a todos los blueprints (MYK-414).

Para cada rol (admin, rrhh, supervisor, auditor) un request representativo por
blueprint con el status esperado de la matriz ADR-001 §5 (200/403/401).

Self-contained: sin BD ni templates; ejerce los decoradores reales
``require()`` / ``api_require()`` / ``login_required`` que usan los blueprints.
"""

import pytest
from flask import Blueprint, Flask, jsonify

from src.webgui.middleware.auth import api_require, login_required, require


def _build_app():
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.auth = None  # api_require por JWT falla cerrado; se testa via sesion WebGUI

    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/login")
    def login():
        return "login"

    app.register_blueprint(auth_bp)

    # --- devices (UI: devices:read; escrituras/sync: devices:write / devices:sync) ---
    @app.route("/ui/devices")
    @require("devices:read")
    def ui_devices():
        return jsonify({"ok": True})

    @app.route("/api/devices")
    @api_require("devices:read")
    def api_devices_read():
        return jsonify({"ok": True})

    @app.route("/api/devices", methods=["POST"])
    @api_require("devices:write")
    def api_devices_write():
        return jsonify({"ok": True})

    @app.route("/api/devices/sync", methods=["POST"])
    @api_require("devices:sync")
    def api_devices_sync():
        return jsonify({"ok": True})

    # --- colaboradores / employees (lectura: employees:read; POST/PUT/DELETE: employees:write) ---
    @app.route("/ui/colaboradores")
    @require("employees:read")
    def ui_colaboradores():
        return jsonify({"ok": True})

    @app.route("/api/employees")
    @api_require("employees:read")
    def api_employees_read():
        return jsonify({"ok": True})

    @app.route("/api/employees", methods=["POST"])
    @api_require("employees:write")
    def api_employees_write():
        return jsonify({"ok": True})

    # --- medical-leaves (lectura: medical_leaves:read; escritura: medical_leaves:write) ---
    @app.route("/api/medical-leaves")
    @api_require("medical_leaves:read")
    def api_medical_leaves_read():
        return jsonify({"ok": True})

    @app.route("/api/medical-leaves", methods=["POST"])
    @api_require("medical_leaves:write")
    def api_medical_leaves_write():
        return jsonify({"ok": True})

    # --- attendance / reportes (lectura: reports:read; export: reports:export) ---
    @app.route("/ui/attendance")
    @require("reports:read")
    def ui_attendance():
        return jsonify({"ok": True})

    @app.route("/api/attendance/stats")
    @api_require("reports:read")
    def api_attendance_stats_read():
        return jsonify({"ok": True})

    @app.route("/api/attendance/stats/export")
    @api_require("reports:export")
    def api_attendance_stats_export():
        return jsonify({"ok": True})

    @app.route("/ui/reportes")
    @require("reports:read")
    def ui_reportes():
        return jsonify({"ok": True})

    # --- dashboard / apidocs: login_required (cualquier rol autenticado) ---
    @app.route("/ui/dashboard")
    @login_required
    def ui_dashboard():
        return jsonify({"ok": True})

    @app.route("/api/apidocs")
    @login_required
    def api_apidocs():
        return jsonify({"ok": True})

    # --- publicos ---
    @app.route("/health")
    def health():
        return jsonify({"ok": True})

    return app


@pytest.fixture
def client():
    return _build_app().test_client()


def _session(client, role):
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "user1"
        sess["role"] = role


# (rol_o_None, metodo, path, status_esperado). rol None = sin sesion / sin credencial.
MATRIX = [
    # devices:read solo admin
    ("admin", "GET", "/ui/devices", 200),
    ("rrhh", "GET", "/ui/devices", 302),
    ("supervisor", "GET", "/ui/devices", 302),
    ("auditor", "GET", "/ui/devices", 302),
    (None, "GET", "/ui/devices", 302),
    # devices:read / devices:write / devices:sync (API)
    ("admin", "GET", "/api/devices", 200),
    ("rrhh", "GET", "/api/devices", 403),
    ("supervisor", "GET", "/api/devices", 403),
    ("auditor", "GET", "/api/devices", 403),
    (None, "GET", "/api/devices", 401),
    ("admin", "POST", "/api/devices", 200),
    ("rrhh", "POST", "/api/devices", 403),
    ("admin", "POST", "/api/devices/sync", 200),
    ("rrhh", "POST", "/api/devices/sync", 403),
    (None, "POST", "/api/devices/sync", 401),
    # employees:read -> todos los roles; employees:write -> admin y rrhh
    ("admin", "GET", "/ui/colaboradores", 200),
    ("rrhh", "GET", "/ui/colaboradores", 200),
    ("supervisor", "GET", "/ui/colaboradores", 200),
    ("auditor", "GET", "/ui/colaboradores", 200),
    (None, "GET", "/ui/colaboradores", 302),
    ("admin", "GET", "/api/employees", 200),
    ("rrhh", "GET", "/api/employees", 200),
    ("supervisor", "GET", "/api/employees", 200),
    ("auditor", "GET", "/api/employees", 200),
    (None, "GET", "/api/employees", 401),
    ("admin", "POST", "/api/employees", 200),
    ("rrhh", "POST", "/api/employees", 200),
    ("supervisor", "POST", "/api/employees", 403),
    ("auditor", "POST", "/api/employees", 403),
    (None, "POST", "/api/employees", 401),
    # medical_leaves:read -> todos; medical_leaves:write -> admin y rrhh
    ("admin", "GET", "/api/medical-leaves", 200),
    ("rrhh", "GET", "/api/medical-leaves", 200),
    ("supervisor", "GET", "/api/medical-leaves", 200),
    ("auditor", "GET", "/api/medical-leaves", 200),
    (None, "GET", "/api/medical-leaves", 401),
    ("admin", "POST", "/api/medical-leaves", 200),
    ("rrhh", "POST", "/api/medical-leaves", 200),
    ("supervisor", "POST", "/api/medical-leaves", 403),
    ("auditor", "POST", "/api/medical-leaves", 403),
    (None, "POST", "/api/medical-leaves", 401),
    # reports:read / reports:export -> todos los roles autenticados
    ("admin", "GET", "/ui/attendance", 200),
    ("rrhh", "GET", "/ui/attendance", 200),
    ("supervisor", "GET", "/ui/attendance", 200),
    ("auditor", "GET", "/ui/attendance", 200),
    (None, "GET", "/ui/attendance", 302),
    ("admin", "GET", "/api/attendance/stats", 200),
    ("rrhh", "GET", "/api/attendance/stats", 200),
    ("supervisor", "GET", "/api/attendance/stats", 200),
    ("auditor", "GET", "/api/attendance/stats", 200),
    (None, "GET", "/api/attendance/stats", 401),
    ("admin", "GET", "/api/attendance/stats/export", 200),
    ("rrhh", "GET", "/api/attendance/stats/export", 200),
    ("supervisor", "GET", "/api/attendance/stats/export", 200),
    ("auditor", "GET", "/api/attendance/stats/export", 200),
    (None, "GET", "/api/attendance/stats/export", 401),
    ("admin", "GET", "/ui/reportes", 200),
    ("rrhh", "GET", "/ui/reportes", 200),
    ("supervisor", "GET", "/ui/reportes", 200),
    ("auditor", "GET", "/ui/reportes", 200),
    (None, "GET", "/ui/reportes", 302),
    # login_required: cualquier rol autenticado -> 200; sin sesion -> 302 UI / 401 API
    ("admin", "GET", "/ui/dashboard", 200),
    ("auditor", "GET", "/ui/dashboard", 200),
    (None, "GET", "/ui/dashboard", 302),
    ("admin", "GET", "/api/apidocs", 200),
    ("auditor", "GET", "/api/apidocs", 200),
    (None, "GET", "/api/apidocs", 302),
    # publicos
    (None, "GET", "/health", 200),
    ("auditor", "GET", "/health", 200),
]


@pytest.mark.parametrize("role,method,path,expected", MATRIX)
def test_rbac_matrix(client, role, method, path, expected):
    if role is not None:
        _session(client, role)
    func = getattr(client, method.lower())
    resp = func(path)
    assert resp.status_code == expected, (
        f"role={role} {method} {path} esperaban {expected}, obtuvieron {resp.status_code}"
    )


def test_desconocido_deniega_todo(client):
    _session(client, "desconocido")
    assert client.get("/api/devices").status_code == 403
    assert client.get("/api/employees").status_code == 403
    assert client.get("/api/medical-leaves").status_code == 403
    assert client.get("/api/attendance/stats").status_code == 403
    # login_required solo exige sesion (cualquier rol autenticado pasa).
    assert client.get("/ui/dashboard").status_code == 200
