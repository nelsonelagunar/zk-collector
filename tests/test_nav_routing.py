"""Tests de navegacion del layout (MYK-377).

Regresion del issue: las secciones colaboradores, dispositivos, usuarios y
configuracion deben renderizar DENTRO del layout con menus (no pagina suelta
ni 404 "no existe"). En master sin fix: /users, /settings y /profile -> 404
y el navbar enlazaba pagulas inexistentes.
"""

NAV_PATHS = (
    "/",
    "/attendance",
    "/reportes",
    "/colaboradores",
    "/devices",
    "/users",
    "/configuracion/razon-social",
    "/settings",
    "/profile",
)

# Rutas de seccion: deben responder 200 tanto con como sin slash final
SECTION_PATHS = (
    "/colaboradores",
    "/colaboradores/",
    "/devices",
    "/devices/",
    "/attendance",
    "/attendance/",
    "/reportes",
    "/reportes/",
    "/users",
    "/users/",
    "/configuracion/razon-social",
    "/configuracion/razon-social/",
    "/settings",
    "/settings/",
    "/profile",
    "/profile/",
)


def test_nav_sections_render_inside_layout(logged_client):
    """Cada seccion del navbar responde 200 y renderiza el navbar (layout)."""
    _app, client = logged_client
    for path in NAV_PATHS:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} devolvio {resp.status_code}"
        assert b"<nav" in resp.data, f"{path} no renderiza dentro del layout"
        for href in (b'href="/users"', b'href="/settings"', b'href="/colaboradores"'):
            assert href in resp.data, f"{path} no incluye el menu ({href})"


def test_section_routes_accept_both_slash_variants(logged_client):
    """El navbar enlaza sin slash; el 308 previo se elimina con strict_slashes."""
    _app, client = logged_client
    for path in SECTION_PATHS:
        resp = client.get(path)
        assert resp.status_code == 200, f"{path} devolvio {resp.status_code}"


def test_protected_sections_redirect_anonymous_to_login(webgui_app):
    """Sin sesion, usuarios/configuracion/perfil redirigen al login (no 404)."""
    client = webgui_app.test_client()
    for path in ("/users", "/settings", "/profile"):
        resp = client.get(path)
        assert resp.status_code == 302, f"{path} devolvio {resp.status_code} sin sesion"
        assert "/auth/login" in resp.headers["Location"]
