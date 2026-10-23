"""Tests de la seccion Usuarios y Perfil (MYK-377)."""

from src.webgui.auth import Auth


def _count_users(app, username):
    row = app.db.fetch_one("SELECT COUNT(*) AS c FROM users WHERE username = ?", (username,))
    return row["c"] if row else 0


def _demo_user_id(app, username):
    row = app.db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
    assert row is not None, f"usuario demo {username} no encontrado (seed MYK-377)"
    return row["id"]


DEMO_USERS = (b"demo.admin", b"demo.rrhh", b"demo.finanzas", b"demo.soporte", b"demo.ventas")


def test_users_list_renders_with_layout_and_demo_seed(logged_client):
    app, client = logged_client
    resp = client.get("/users")
    assert resp.status_code == 200
    assert b"<nav" in resp.data
    for demo_user in DEMO_USERS:
        assert demo_user in resp.data, f"seed demo {demo_user} no aparece en /users"


def test_users_requires_session(webgui_app):
    resp = webgui_app.test_client().get("/users")
    assert resp.status_code == 302
    assert "/auth/login" in resp.headers["Location"]


def test_create_user_persists_and_hashes_password(logged_client):
    app, client = logged_client
    resp = client.post(
        "/users/new",
        data={
            "username": "nueva.cuenta",
            "email": "nueva@example.com",
            "full_name": "Nueva Cuenta",
            "role": "user",
            "password": "PasswordSegura99",
        },
        follow_redirects=True,
    )
    assert resp.status_code == 200
    assert _count_users(app, "nueva.cuenta") == 1
    row = app.db.fetch_one("SELECT password_hash FROM users WHERE username = 'nueva.cuenta'")
    auth = Auth()
    assert auth.verify_password("PasswordSegura99", row["password_hash"])


def test_create_user_rejects_short_password(logged_client):
    app, client = logged_client
    resp = client.post(
        "/users/new",
        data={"username": "corta.cuenta", "role": "user", "password": "123"},
    )
    assert resp.status_code == 200
    assert b"al menos 8" in resp.data
    assert _count_users(app, "corta.cuenta") == 0


def test_create_user_rejects_duplicate_username(logged_client):
    app, client = logged_client
    resp = client.post(
        "/users/new",
        data={"username": "demo.admin", "role": "user", "password": "PasswordSegura99"},
    )
    assert resp.status_code == 200
    assert b"ya existe" in resp.data
    assert _count_users(app, "demo.admin") == 1


def test_create_user_requires_admin(user_role_client):
    app, client = user_role_client
    resp = client.post(
        "/users/new",
        data={"username": "sin.permiso", "role": "user", "password": "PasswordSegura99"},
    )
    assert resp.status_code == 302
    assert _count_users(app, "sin.permiso") == 0


def test_toggle_user_activates_and_deactivates(logged_client):
    app, client = logged_client
    target_id = _demo_user_id(app, "demo.rrhh")

    resp = client.post(f"/users/{target_id}/toggle", follow_redirects=True)
    assert resp.status_code == 200
    is_active = app.db.fetch_one(
        "SELECT is_active FROM users WHERE id = ?", (target_id,)
    )["is_active"]
    assert is_active == 0

    client.post(f"/users/{target_id}/toggle")
    is_active = app.db.fetch_one(
        "SELECT is_active FROM users WHERE id = ?", (target_id,)
    )["is_active"]
    assert is_active == 1


def test_toggle_own_account_rejected(logged_client):
    app, client = logged_client
    own = app.db.fetch_one("SELECT id FROM users WHERE username = 'admin'")
    resp = client.post(f"/users/{own['id']}/toggle", follow_redirects=True)
    assert resp.status_code == 200
    assert b"propia cuenta" in resp.data
    is_active = app.db.fetch_one(
        "SELECT is_active FROM users WHERE id = ?", (own["id"],)
    )["is_active"]
    assert is_active == 1


def test_profile_shows_session_user(logged_client):
    _app, client = logged_client
    resp = client.get("/profile")
    assert resp.status_code == 200
    assert b"<nav" in resp.data
    assert b"admin@example.com" in resp.data
    assert b"Admin Test" in resp.data
