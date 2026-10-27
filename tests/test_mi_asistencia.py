"""Tests e2e del portal del trabajador /mi-asistencia (MYK-425).

AC del issue:
- El empleado ve SOLO sus registros (via employee_device_links).
- Intentar consultar `employee_id` ajeno -> 403 (HTML y JSON).
- Login por PIN por empleado con rate limit y mensaje generico unico.
- Aviso de privacidad enlazado (datos biometricos = sensibles LFPDPPP).
"""

import re
from datetime import datetime, timedelta

import pytest

from src.webgui.routes.mi_asistencia import reset_pin_rate_limit_store

TODAY = datetime.now().date()
MARK_DAY = (TODAY - timedelta(days=1)).isoformat()
PERIOD = {"start_date": (TODAY - timedelta(days=6)).isoformat(), "end_date": TODAY.isoformat()}


@pytest.fixture(autouse=True)
def _reset_pin_rate_limit():
    reset_pin_rate_limit_store()


@pytest.fixture
def portal_env(webgui_app):
    """Dos empleados con PIN activo, dispositivos y marcas propias/ajenas en el buffer."""
    db = webgui_app.db
    device_a = db.insert(
        "devices",
        {
            "name": "Reloj Portal A",
            "address": "10.10.10.10",
            "port": 4370,
            "password": 0,
            "timeout": 5,
            "protocol": "tcp",
            "serial_number": "SNPORTA",
            "is_enabled": 1,
        },
    )
    emp_a = db.create_employee(
        {
            "employee_code": "PORTA-001",
            "first_name": "Ana",
            "last_name": "Rivera",
            "status": "active",
            "pin_hash": webgui_app.auth.hash_password("123456"),
        }
    )
    emp_b = db.create_employee(
        {
            "employee_code": "PORTB-002",
            "first_name": "Beto",
            "last_name": "Luna",
            "status": "active",
            "pin_hash": webgui_app.auth.hash_password("654321"),
        }
    )
    db.link_employee_to_device(emp_a, "SNPORTA", "7001")
    db.link_employee_to_device(emp_b, "SNPORTA", "7002")

    with webgui_app.buffer_repo.get_connection() as conn:
        marks = [
            # Ana: entrada 09:00, salida 19:00 -> 10 h trabajadas, 2 h extra
            ("7001", f"{MARK_DAY}T09:00:00", 0, "10.10.10.10", "check-in"),
            ("7001", f"{MARK_DAY}T19:00:00", 1, "10.10.10.10", "check-out"),
            # Beto: mismas marcas en el MISMO reloj e IP -> NO deben aparecer a Ana
            ("7002", f"{MARK_DAY}T09:30:00", 0, "10.10.10.10", "check-in"),
            ("7002", f"{MARK_DAY}T19:30:00", 1, "10.10.10.10", "check-out"),
        ]
        conn.executemany(
            "INSERT INTO attendance_records (user_id, timestamp, status, device_ip, punch_type) "
            "VALUES (?, ?, ?, ?, ?)",
            marks,
        )
    return webgui_app, emp_a, emp_b, device_a


def _login(client, code="PORTA-001", pin="123456"):
    return client.post("/mi-asistencia/login", data={"employee_code": code, "pin": pin})


def _login_ok(client, code="PORTA-001", pin="123456"):
    resp = _login(client, code, pin)
    assert resp.status_code == 302
    assert resp.headers["Location"].rstrip("/").endswith("/mi-asistencia")
    return client


# --- Login y sesion -----------------------------------------------------------


def test_login_page_renders_with_privacy_link(webgui_app):
    resp = webgui_app.test_client().get("/mi-asistencia/login")
    assert resp.status_code == 200
    assert b"/mi-asistencia/aviso-privacidad" in resp.data


def test_index_requires_portal_session(webgui_app):
    resp = webgui_app.test_client().get("/mi-asistencia")
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/mi-asistencia/login")


def test_login_ok_and_portal_session_is_not_admin(portal_env):
    app, emp_a, _, _ = portal_env
    client = _login_ok(app.test_client())
    with client.session_transaction() as sess:
        assert sess["portal_employee_id"] == emp_a
        assert "user_id" not in sess  # sesion de portal distinta a la de admin
    # La sesion de portal NO da acceso a paginas admin
    resp = client.get("/profile")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_login_wrong_pin_and_unknown_code_share_generic_message(portal_env):
    app, _, _, _ = portal_env
    client = app.test_client()
    wrong = client.post(
        "/mi-asistencia/login",
        data={"employee_code": "PORTA-001", "pin": "999999"},
        follow_redirects=True,
    )
    unknown = client.post(
        "/mi-asistencia/login",
        data={"employee_code": "NOEXISTE", "pin": "123456"},
        follow_redirects=True,
    )
    assert wrong.status_code == 401 and unknown.status_code == 401
    assert b"Numero de empleado o PIN incorrecto." in wrong.data
    assert b"Numero de empleado o PIN incorrecto." in unknown.data


def test_login_rate_limited_after_5_failures(portal_env):
    app, _, _, _ = portal_env
    client = app.test_client()
    for _ in range(5):
        assert _login(client, pin="000000").status_code == 401
    assert _login(client, pin="000000").status_code == 429


def test_login_rejected_for_inactive_employee(portal_env):
    app, emp_a, _, _ = portal_env
    app.db.update_employee(emp_a, {"status": "inactive"})
    assert _login(app.test_client()).status_code == 401


def test_logout_clears_portal_session(portal_env):
    app, _, _, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia/logout")
    assert resp.status_code == 302
    with client.session_transaction() as sess:
        assert "portal_employee_id" not in sess


# --- AC: el empleado ve SOLO sus registros ------------------------------------


def test_index_shows_only_own_records(portal_env):
    app, emp_a, _, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia", query_string=PERIOD)
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "Ana" in body and "PORTA-001" in body
    assert "09:00:00" in body and "19:00:00" in body  # marcas propias
    assert "09:30:00" not in body and "19:30:00" not in body  # marcas ajenas NO
    assert "+2.00 h" in body  # 10 h - 8 h de jornada (LFT 61/66)


def test_api_records_returns_only_own_data(portal_env):
    app, emp_a, emp_b, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia/api/records", query_string=PERIOD)
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["employee"]["employee_id"] == emp_a
    assert data["employee"]["employee_code"] == "PORTA-001"
    assert data["summary"]["days_with_marks"] == 1
    assert data["summary"]["worked_hours"] == 10.0
    assert data["summary"]["extra_hours"] == 2.0
    assert len(data["days"]) == 1
    assert len(data["days"][0]["marks"]) == 2  # solo las 2 marcas propias


# --- AC: intentar ver otro empleado -> 403 ------------------------------------


def test_foreign_employee_id_on_index_is_403(portal_env):
    app, _, emp_b, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia", query_string={**PERIOD, "employee_id": emp_b})
    assert resp.status_code == 403


def test_foreign_employee_id_on_api_is_403(portal_env):
    app, _, emp_b, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia/api/records", query_string={**PERIOD, "employee_id": emp_b})
    assert resp.status_code == 403
    assert b"7002" not in resp.data  # jamas expone los registros ajenos


def test_own_employee_id_is_allowed(portal_env):
    app, emp_a, _, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia/api/records", query_string={**PERIOD, "employee_id": emp_a})
    assert resp.status_code == 200
    assert resp.get_json()["employee"]["employee_id"] == emp_a


def test_employee_id_of_deleted_employee_is_403(portal_env):
    app, _, _, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia", query_string={"employee_id": 999999})
    assert resp.status_code == 403


# --- Validacion de periodo -----------------------------------------------------


@pytest.mark.parametrize(
    "params",
    [
        {"start_date": "2026-13-40", "end_date": "2026-01-31"},
        {"start_date": TODAY.isoformat(), "end_date": (TODAY - timedelta(days=1)).isoformat()},
        {"start_date": (TODAY - timedelta(days=200)).isoformat(), "end_date": TODAY.isoformat()},
        {"start_date": TODAY.isoformat(), "end_date": (TODAY + timedelta(days=1)).isoformat()},
    ],
)
def test_api_rejects_invalid_periods(portal_env, params):
    app, _, _, _ = portal_env
    client = _login_ok(app.test_client())
    resp = client.get("/mi-asistencia/api/records", query_string=params)
    assert resp.status_code == 400
    assert "error" in resp.get_json()


def test_api_requires_auth(portal_env):
    app, _, _, _ = portal_env
    resp = app.test_client().get("/mi-asistencia/api/records")
    assert resp.status_code == 401


# --- Aviso de privacidad (LFPDPPP, datos biometricos) -------------------------


def test_privacy_notice_renders(portal_env):
    resp = portal_env[0].test_client().get("/mi-asistencia/aviso-privacidad")
    assert resp.status_code == 200
    body = resp.get_data(as_text=True)
    assert "biom" in body.lower()
    assert "LFPDPPP" in body


# --- Gestion de PIN por RRHH/admin ---------------------------------------------


def _admin_client(app):
    app.db.insert(
        "users",
        {
            "username": "hr_admin",
            "email": "hr@example.com",
            "password_hash": app.auth.hash_password("Sup3rSecret!Pass"),
            "full_name": "HR Admin",
            "role": "admin",
        },
    )
    client = app.test_client()
    client.post(
        "/auth/login",
        data={"username": "hr_admin", "password": "Sup3rSecret!Pass"},
        follow_redirects=True,
    )
    return client


def test_admin_generates_pin_then_employee_logs_in(portal_env):
    app, emp_a, _, _ = portal_env
    client = _admin_client(app)
    resp = client.post(f"/colaboradores/expediente/{emp_a}/pin/generar", follow_redirects=True)
    assert resp.status_code == 200
    match = re.search(rb"PIN generado para Ana Rivera: (\d{6})", resp.data)
    assert match, "el PIN debe mostrarse UNA sola vez via flash"
    pin = match.group(1).decode()

    employee = app.db.get_employee_by_id(emp_a)
    assert employee["pin_hash"]
    assert app.auth.verify_password(pin, employee["pin_hash"])

    portal = app.test_client()
    resp = _login(portal, pin=pin)
    assert resp.status_code == 302  # el PIN nuevo funciona en el portal


def test_admin_clears_pin_and_portal_login_fails(portal_env):
    app, emp_a, _, _ = portal_env
    client = _admin_client(app)
    assert client.post(f"/colaboradores/expediente/{emp_a}/pin/limpiar").status_code == 302
    assert app.db.get_employee_by_id(emp_a)["pin_hash"] is None
    assert _login(app.test_client()).status_code == 401


def test_pin_generation_requires_admin(portal_env):
    app, emp_a, _, _ = portal_env
    # rol 'user' autenticado -> sin permisos
    app.db.insert(
        "users",
        {
            "username": "plain_user",
            "email": "plain@example.com",
            "password_hash": app.auth.hash_password("Sup3rSecret!Pass"),
            "full_name": "Plain User",
            "role": "user",
        },
    )
    client = app.test_client()
    client.post(
        "/auth/login",
        data={"username": "plain_user", "password": "Sup3rSecret!Pass"},
        follow_redirects=True,
    )
    resp = client.post(f"/colaboradores/expediente/{emp_a}/pin/generar")
    assert resp.status_code == 302  # redirect de admin_required, sin efecto
    assert app.db.get_employee_by_id(emp_a)["pin_hash"] is not None  # PIN intacto


def test_pin_generation_rejects_inactive_employee(portal_env):
    app, emp_a, _, _ = portal_env
    app.db.update_employee(emp_a, {"status": "inactive"})
    client = _admin_client(app)
    resp = client.post(f"/colaboradores/expediente/{emp_a}/pin/generar", follow_redirects=True)
    assert resp.status_code == 200
    assert b"empleados activos" in resp.data
