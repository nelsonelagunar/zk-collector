"""Tests API CRUD usuarios /api/users (MYK-415, ADR-001).

Criterio de aceptacion del issue:
- CRUD happy path con rol admin (JWT Bearer);
- 403 con roles rrhh/supervisor/auditor en todos los verbos;
- proteccion del ultimo admin activo en PATCH y DELETE (test explicito);
- 401 sin credencial; rol invalido y password debil -> 400;
- DELETE es soft: is_active=0 y el row persiste.
"""

import pytest

STRONG = "Sup3rSecret!Pass"


def _bearer(webgui_app, role: str, user_id: int = 99999) -> dict:
    """JWT con el rol pedido. user_id por defecto inexistente: el middleware
    solo lee los claims, y asi los tests de ultimo admin no chocan con el
    guard de auto-desactivacion (caller != objetivo)."""
    token = webgui_app.auth.generate_tokens(user_id, "caller", role)["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.fixture
def admin_headers(webgui_app):
    return _bearer(webgui_app, "admin")


def _user_id(app, username: str) -> int:
    row = app.db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
    assert row is not None, f"usuario demo {username} no encontrado (seed MYK-377)"
    return row["id"]


def _new_user(app, username: str, **overrides) -> int:
    data = {
        "username": username,
        "email": f"{username}@example.com",
        "full_name": username.title(),
        "role": "supervisor",
        "password": STRONG,
    }
    data.update(overrides)
    return app.db.insert(
        "users",
        {
            "username": data["username"],
            "email": data["email"],
            "password_hash": app.auth.hash_password(data["password"]),
            "full_name": data["full_name"],
            "role": data["role"],
            "is_active": 1,
        },
    )


# --- happy path (rol admin, JWT) ---


def test_list_users_returns_seed_and_no_password_hash(webgui_app, admin_headers):
    resp = webgui_app.test_client().get("/api/users", headers=admin_headers)
    assert resp.status_code == 200
    users = resp.get_json()["users"]
    assert any(u["username"] == "demo.admin" for u in users)
    assert all("password_hash" not in u for u in users)


def test_create_user_persists_and_hashes_password(webgui_app, admin_headers):
    payload = {
        "username": "api.nuevo",
        "email": "api.nuevo@example.com",
        "full_name": "Api Nuevo",
        "role": "rrhh",
        "password": STRONG,
    }
    resp = webgui_app.test_client().post("/api/users", json=payload, headers=admin_headers)
    assert resp.status_code == 201
    user = resp.get_json()["user"]
    assert user["role"] == "rrhh" and user["is_active"] == 1
    row = webgui_app.db.fetch_one("SELECT * FROM users WHERE username = 'api.nuevo'")
    assert webgui_app.auth.verify_password(STRONG, row["password_hash"])


def test_update_user_partial(webgui_app, admin_headers):
    target = _new_user(webgui_app, "api.editable")
    resp = webgui_app.test_client().patch(
        f"/api/users/{target}", json={"full_name": "Editado", "role": "auditor"},
        headers=admin_headers,
    )
    assert resp.status_code == 200
    user = resp.get_json()["user"]
    assert user["full_name"] == "Editado" and user["role"] == "auditor"
    row = webgui_app.db.fetch_one("SELECT role, full_name FROM users WHERE id = ?", (target,))
    assert row["role"] == "auditor" and row["full_name"] == "Editado"


def test_delete_user_is_soft(webgui_app, admin_headers):
    target = _new_user(webgui_app, "api.borrable")
    resp = webgui_app.test_client().delete(f"/api/users/{target}", headers=admin_headers)
    assert resp.status_code == 200
    row = webgui_app.db.fetch_one("SELECT is_active FROM users WHERE id = ?", (target,))
    assert row is not None and row["is_active"] == 0


# --- 401 / 403 ---


def test_api_users_requires_credential(webgui_app):
    resp = webgui_app.test_client().get("/api/users")
    assert resp.status_code == 401
    assert resp.get_json()["error"]


@pytest.mark.parametrize("role", ["rrhh", "supervisor", "auditor"])
def test_non_admin_roles_get_403_on_all_verbs(webgui_app, role):
    client = webgui_app.test_client()
    headers = _bearer(webgui_app, role)
    target = _new_user(webgui_app, f"api.target.{role}")

    assert client.get("/api/users", headers=headers).status_code == 403
    assert client.post(
        "/api/users", json={"username": "x", "password": STRONG}, headers=headers
    ).status_code == 403
    assert client.patch(
        f"/api/users/{target}", json={"role": "auditor"}, headers=headers
    ).status_code == 403
    assert client.delete(f"/api/users/{target}", headers=headers).status_code == 403


def test_session_without_permission_gets_403(webgui_app):
    """Paridad con el fetch same-origin del WebGUI: sesion sin users:manage -> 403."""
    webgui_app.db.insert(
        "users",
        {
            "username": "sesion.rrhh",
            "email": "sesion@example.com",
            "password_hash": webgui_app.auth.hash_password(STRONG),
            "full_name": "Sesion Rrhh",
            "role": "rrhh",
        },
    )
    client = webgui_app.test_client()
    client.post(
        "/auth/login", data={"username": "sesion.rrhh", "password": STRONG}
    )
    resp = client.get("/api/users")
    assert resp.status_code == 403


# --- validacion de entrada ---


def test_create_user_rejects_weak_password(webgui_app, admin_headers):
    resp = webgui_app.test_client().post(
        "/api/users",
        json={"username": "api.debil", "role": "auditor", "password": "corta123"},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    assert "password" in resp.get_json()["error"]


@pytest.mark.parametrize("bad_role", ["user", "superadmin", ""])
def test_create_user_rejects_role_outside_catalog(webgui_app, admin_headers, bad_role):
    resp = webgui_app.test_client().post(
        "/api/users",
        json={"username": "api.rol", "role": bad_role, "password": STRONG},
        headers=admin_headers,
    )
    assert resp.status_code == 400
    row = webgui_app.db.fetch_one("SELECT id FROM users WHERE username = 'api.rol'")
    assert row is None


def test_create_user_rejects_duplicate_username(webgui_app, admin_headers):
    resp = webgui_app.test_client().post(
        "/api/users",
        json={"username": "demo.admin", "role": "auditor", "password": STRONG},
        headers=admin_headers,
    )
    assert resp.status_code == 409


def test_update_user_rejects_invalid_payload(webgui_app, admin_headers):
    target = _new_user(webgui_app, "api.malpayload")
    resp = webgui_app.test_client().patch(
        f"/api/users/{target}", json={"role": "superadmin"}, headers=admin_headers
    )
    assert resp.status_code == 400
    resp = webgui_app.test_client().patch(
        f"/api/users/{target}", json={"is_active": "si"}, headers=admin_headers
    )
    assert resp.status_code == 400
    resp = webgui_app.test_client().patch(
        f"/api/users/{target}", json={}, headers=admin_headers
    )
    assert resp.status_code == 400


def test_update_missing_user_404(webgui_app, admin_headers):
    resp = webgui_app.test_client().patch(
        "/api/users/99999", json={"role": "auditor"}, headers=admin_headers
    )
    assert resp.status_code == 404


# --- proteccion del ultimo admin activo (regla ADR-001, explicita) ---


def test_cannot_demote_last_active_admin(webgui_app, admin_headers):
    """demo.admin es el unico admin activo del seed: degradar -> 409."""
    only_admin = _user_id(webgui_app, "demo.admin")
    resp = webgui_app.test_client().patch(
        f"/api/users/{only_admin}", json={"role": "rrhh"}, headers=admin_headers
    )
    assert resp.status_code == 409
    assert webgui_app.db.fetch_one(
        "SELECT role FROM users WHERE id = ?", (only_admin,)
    )["role"] == "admin"


def test_cannot_deactivate_last_active_admin_via_patch(webgui_app, admin_headers):
    only_admin = _user_id(webgui_app, "demo.admin")
    resp = webgui_app.test_client().patch(
        f"/api/users/{only_admin}", json={"is_active": 0}, headers=admin_headers
    )
    assert resp.status_code == 409


def test_cannot_delete_last_active_admin(webgui_app, admin_headers):
    only_admin = _user_id(webgui_app, "demo.admin")
    resp = webgui_app.test_client().delete(
        f"/api/users/{only_admin}", headers=admin_headers
    )
    assert resp.status_code == 409
    assert webgui_app.db.fetch_one(
        "SELECT is_active FROM users WHERE id = ?", (only_admin,)
    )["is_active"] == 1


def test_demote_allowed_when_another_active_admin_exists(webgui_app, admin_headers):
    """Con un segundo admin activo, degradar al primero ya no es 409."""
    _new_user(webgui_app, "api.admin2", role="admin")
    demo_admin = _user_id(webgui_app, "demo.admin")
    resp = webgui_app.test_client().patch(
        f"/api/users/{demo_admin}", json={"role": "auditor"}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["role"] == "auditor"


# --- auto-proteccion del caller (paridad UI MYK-416) ---


def test_caller_cannot_deactivate_own_account(webgui_app):
    """Admin cuyo JWT user_id apunta a su propia cuenta: PATCH/DELETE -> 409.

    Segundo admin activo en la BD: aislamiento del guard de auto-desactivacion
    respecto a la regla de ultimo admin.
    """
    me = _new_user(webgui_app, "api.autoden", role="admin")
    headers = _bearer(webgui_app, "admin", user_id=me)
    resp = webgui_app.test_client().patch(
        f"/api/users/{me}", json={"is_active": 0}, headers=headers
    )
    assert resp.status_code == 409
    resp = webgui_app.test_client().delete(f"/api/users/{me}", headers=headers)
    assert resp.status_code == 409


def test_reactivation_via_patch(webgui_app, admin_headers):
    target = _new_user(webgui_app, "api.revive")
    webgui_app.test_client().delete(f"/api/users/{target}", headers=admin_headers)
    resp = webgui_app.test_client().patch(
        f"/api/users/{target}", json={"is_active": 1}, headers=admin_headers
    )
    assert resp.status_code == 200
    assert resp.get_json()["user"]["is_active"] == 1
