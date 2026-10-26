"""Tests RBAC middleware: require() / api_require() / api_auth_required (MYK-413).

Criterio de aceptacion del issue:
- api_require rechaza token firmado con OTRO secret y token expirado (tests explicitos).
- token ausente/invalido/expirado -> 401; rol sin permiso -> 403; rol con permiso -> 200.
- session UI sin permiso -> redirect; semantica multi-permiso = AND. Parametrizado por rol.
"""

import pytest
from flask import Blueprint, Flask, g, jsonify

from src.webgui.auth import Auth
from src.webgui.middleware.auth import api_auth_required, api_require, require
from src.webgui.permissions import ALLOWED_ROLES, ROLE_PERMISSIONS

SECRET = "test-secret-key-0123456789-abcdef-0123"
WRONG_SECRET = "wrong-secret-key-0123456789-abcdef-01"


def _access_token(secret: str = SECRET, role: str = "admin", expired: bool = False) -> str:
    auth = Auth(secret)
    if expired:
        auth.token_expiry_minutes = -1
    return auth.generate_tokens(1, "user1", role)["access_token"]


def _bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def _login_session(client, role: str | None) -> None:
    with client.session_transaction() as sess:
        sess["user_id"] = 1
        sess["username"] = "user1"
        if role is not None:
            sess["role"] = role


def _build_app(with_auth: bool = True) -> Flask:
    app = Flask(__name__)
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = SECRET
    if with_auth:
        app.auth = Auth(SECRET)

    auth_bp = Blueprint("auth", __name__)

    @auth_bp.route("/login")
    def login():
        return "login"

    app.register_blueprint(auth_bp)

    @app.route("/")
    def index():
        return "home"

    @app.route("/ui/users")
    @require("users:manage")
    def ui_users():
        return "ui-users-ok"

    @app.route("/ui/multi")
    @require("employees:read", "users:manage")
    def ui_multi():
        return "ui-multi-ok"

    @app.route("/api/users")
    @api_require("users:manage")
    def api_users():
        return jsonify({"ok": True})

    @app.route("/api/identity")
    @api_require()
    def api_identity():
        # solo rutas JWT-decoradas pueden confiar en g.api_user (path sesion no lo setea)
        return jsonify({"role": g.api_user.get("role")})

    @app.route("/api/multi")
    @api_require("employees:read", "users:manage")
    def api_multi():
        return jsonify({"ok": True})

    @app.route("/api/any")
    @api_auth_required
    def api_any():
        return jsonify({"ok": True})

    return app


@pytest.fixture()
def client():
    return _build_app().test_client()


class TestApiRequireJwt:
    """API JWT: 401 credencial invalida, 403 sin permiso, 200 con permiso, por rol."""

    @pytest.mark.parametrize("role", ALLOWED_ROLES)
    def test_role_matrix_users_manage(self, role, client):
        resp = client.get("/api/users", headers=_bearer(_access_token(role=role)))
        if "users:manage" in ROLE_PERMISSIONS[role]:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403
            assert resp.get_json() == {"error": "Insufficient permissions"}

    def test_role_read_from_jwt_payload(self, client):
        # el rol autorizado es el del payload del JWT, no de la sesion
        resp = client.get("/api/identity", headers=_bearer(_access_token(role="rrhh")))
        assert resp.status_code == 200
        assert resp.get_json() == {"role": "rrhh"}

    def test_missing_header_401(self, client):
        resp = client.get("/api/users")
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authorization header required"}

    def test_garbage_token_401(self, client):
        resp = client.get("/api/users", headers=_bearer("garbage"))
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_expired_token_401(self, client):
        """Explicito del criterio de aceptacion: token expirado se rechaza."""
        resp = client.get("/api/users", headers=_bearer(_access_token(expired=True)))
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_wrong_secret_token_401(self, client):
        """Explicito del criterio de aceptacion: token firmado con otro secret se rechaza."""
        resp = client.get("/api/users", headers=_bearer(_access_token(secret=WRONG_SECRET)))
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid or expired token"}

    def test_wrong_scheme_401(self, client):
        resp = client.get("/api/users", headers={"Authorization": "Basic abc"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Bearer scheme required"}

    def test_malformed_header_401(self, client):
        resp = client.get("/api/users", headers={"Authorization": "NoSpacesHere"})
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Invalid authorization format"}

    def test_refresh_token_as_access_401(self, client):
        refresh = Auth(SECRET).generate_tokens(1, "user1", "admin")["refresh_token"]
        resp = client.get("/api/users", headers=_bearer(refresh))
        assert resp.status_code == 401

    def test_fail_closed_without_app_auth_401(self):
        # header presente pero app sin auth configurado -> 401, nunca pasa
        resp = _build_app(with_auth=False).test_client().get("/api/users", headers=_bearer("x"))
        assert resp.status_code == 401
        assert resp.get_json() == {"error": "Authentication is not configured"}

    def test_unknown_role_in_token_403(self, client):
        resp = client.get("/api/users", headers=_bearer(_access_token(role="hacker")))
        assert resp.status_code == 403
        assert resp.get_json() == {"error": "Insufficient permissions"}

    def test_multi_permission_is_and(self, client):
        # rrhh tiene employees:read pero NO users:manage -> 403
        resp = client.get("/api/multi", headers=_bearer(_access_token(role="rrhh")))
        assert resp.status_code == 403
        # admin tiene ambos -> 200
        resp = client.get("/api/multi", headers=_bearer(_access_token(role="admin")))
        assert resp.status_code == 200


class TestApiRequireSession:
    """api_require mantiene la sesion WebGUI como credencial (MYK-443)."""

    @pytest.mark.parametrize("role", ALLOWED_ROLES)
    def test_session_role_matrix(self, role, client):
        _login_session(client, role)
        resp = client.get("/api/users")
        if "users:manage" in ROLE_PERMISSIONS[role]:
            assert resp.status_code == 200
        else:
            assert resp.status_code == 403
            assert resp.get_json() == {"error": "Insufficient permissions"}

    def test_session_without_role_claims_no_perm_403(self, client):
        _login_session(client, role=None)
        resp = client.get("/api/users")
        assert resp.status_code == 403

    def test_session_admin_ignores_bad_bearer_header(self, client):
        # la sesion manda primero: header basura no rompe al browser del WebGUI
        _login_session(client, "admin")
        resp = client.get("/api/users", headers=_bearer("garbage"))
        assert resp.status_code == 200


class TestApiAuthRequiredAlias:
    """api_auth_required deprecated = api_require() sin permisos: sin regresion."""

    def test_valid_token_200(self, client):
        resp = client.get("/api/any", headers=_bearer(_access_token()))
        assert resp.status_code == 200

    def test_unknown_role_token_without_perms_200(self, client):
        # sin permisos pedidos solo autentica; el rol desconocido deniega permisos, no acceso
        resp = client.get("/api/any", headers=_bearer(_access_token(role="hacker")))
        assert resp.status_code == 200

    def test_garbage_token_401(self, client):
        resp = client.get("/api/any", headers=_bearer("garbage"))
        assert resp.status_code == 401

    def test_session_200(self, client):
        _login_session(client, "auditor")
        resp = client.get("/api/any")
        assert resp.status_code == 200


class TestRequireUiSession:
    """UI sesion: sin sesion -> login; sin permiso -> flash + redirect a '/'."""

    def test_no_session_redirects_to_login(self, client):
        resp = client.get("/ui/users")
        assert resp.status_code == 302
        assert "/login" in resp.headers["Location"]

    @pytest.mark.parametrize("role", ALLOWED_ROLES)
    def test_session_role_matrix(self, role, client):
        _login_session(client, role)
        resp = client.get("/ui/users")
        if "users:manage" in ROLE_PERMISSIONS[role]:
            assert resp.status_code == 200
            assert resp.data == b"ui-users-ok"
        else:
            assert resp.status_code == 302
            assert resp.headers["Location"] == "/"

    def test_denied_role_flashes_message(self, client):
        _login_session(client, "auditor")
        client.get("/ui/users")
        with client.session_transaction() as sess:
            flashes = [msg for _, msg in sess.get("_flashes", [])]
        assert any("No tienes permisos" in msg for msg in flashes)

    def test_unknown_role_in_session_redirects(self, client):
        _login_session(client, "hacker")
        resp = client.get("/ui/users")
        assert resp.status_code == 302
        assert resp.headers["Location"] == "/"

    def test_multi_permission_is_and(self, client):
        _login_session(client, "rrhh")
        assert client.get("/ui/multi").status_code == 302
        _login_session(client, "admin")
        assert client.get("/ui/multi").status_code == 200
