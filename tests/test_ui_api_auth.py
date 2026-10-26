"""Tests de auth de los endpoints JSON/paginas de UI (MYK-451).

Antes del fix, los fetch que alimentan la UI respondian 200 a cualquier
request anonimo: /devices/api/*, /attendance/api/*, /colaboradores/api/*
y /reportes/api/* filtraban datos de empleados/asistencia sin sesion ni
JWT, y las paginas de esas secciones eran publicas.

Estos tests FALLAN sin el fix (anon obtiene 200/302->200) y PASAN con
``api_auth_required`` en las rutas JSON y ``login_required`` en las paginas.
Usa la app real (``create_app``) con login real (``logged_client``), asi
tambien prueba que la UI sigue funcionando con sesion activa (MYK-451 AC 3).
"""

import pytest

DEVICE_IP = "192.0.2.51"

JSON_ROUTES_200_LOGGED = (
    "/attendance/api/attendance",
    "/attendance/api/devices",
    "/attendance/attendance/stats",
    "/colaboradores/api/devices",
    "/reportes/api/stats",
)

JSON_ROUTES_401_ANON = JSON_ROUTES_200_LOGGED + (
    "/devices/api/device-users",
    "/devices/api/device-users/stats",
    "/attendance/export",
    "/reportes/export",
)

PAGE_ROUTES = (
    "/devices/",
    "/devices/new",
    "/devices/1/detail",
    "/attendance/",
    "/colaboradores/",
    "/colaboradores/expediente/1",
    "/reportes/",
)


def _seed_device(app):
    return app.db.insert(
        "devices",
        {
            "name": "Reloj MYK-451",
            "location": "LAN",
            "zone": "",
            "address": DEVICE_IP,
            "port": 4370,
            "password": 0,
            "timeout": 5,
            "protocol": "tcp",
        },
    )


def test_anonymous_json_routes_get_401(webgui_app):
    """Sin sesion ni JWT, cada ruta JSON de UI responde 401 (AC 2)."""
    client = webgui_app.test_client()
    for path in JSON_ROUTES_401_ANON:
        resp = client.get(path)
        assert resp.status_code == 401, f"{path} anon devolvio {resp.status_code}"
        assert "error" in (resp.get_json() or {}), f"{path} no usa el shape de error 401"


def test_anonymous_post_json_routes_get_401(webgui_app):
    """POSTs de UI (sync-users, test de conexion) bloqueados sin auth."""
    client = webgui_app.test_client()
    resp = client.post("/devices/api/devices/test", json={"ip": DEVICE_IP})
    assert resp.status_code == 401
    resp = client.post("/devices/999999/sync-users")
    assert resp.status_code == 401


def test_anonymous_pages_redirect_to_login(webgui_app):
    """Las paginas de las 4 secciones redirigen anonimos al login."""
    client = webgui_app.test_client()
    for path in PAGE_ROUTES:
        resp = client.get(path)
        assert resp.status_code == 302, f"{path} anon devolvio {resp.status_code}"
        assert "/auth/login" in resp.headers["Location"], f"{path} no redirige al login"


def test_logged_session_ui_json_routes_200(logged_client):
    """Con sesion activa (login real) los endpoints JSON de UI funcionan."""
    app, client = logged_client
    _seed_device(app)

    for path in JSON_ROUTES_200_LOGGED:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} con sesion devolvio {resp.status_code}"

    resp = client.get(f"/devices/api/device-users?device_ip={DEVICE_IP}")
    assert resp.status_code == 200
    assert resp.get_json() == {"users": []}

    resp = client.get("/colaboradores/api/devices")
    assert resp.status_code == 200
    assert "devices" in resp.get_json()


def test_logged_session_exports_and_stats_work(logged_client):
    """Los exports CSV y las stats de UI siguen funcionando con sesion."""
    _app, client = logged_client

    resp = client.get("/attendance/export?format=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"

    resp = client.get("/reportes/export?format=csv")
    assert resp.status_code == 200
    assert resp.mimetype == "text/csv"

    resp = client.get("/attendance/attendance/stats")
    assert resp.status_code == 200
    assert "by_punch_type" in resp.get_json()


@pytest.mark.parametrize(
    "path",
    [
        "/devices/",
        "/attendance/",
        "/colaboradores/",
        "/reportes/",
    ],
)
def test_logged_pages_render(logged_client, path):
    """Las paginas de las secciones renderizan 200 con sesion activa."""
    _app, client = logged_client
    resp = client.get(path)
    assert resp.status_code == 200, f"{path} con sesion devolvio {resp.status_code}"
