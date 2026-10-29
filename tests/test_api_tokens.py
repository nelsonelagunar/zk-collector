"""Tests para Personal Access Tokens y endpoints con Bearer auth (MYK-407).

Cubre: emision/verificacion/revocacion de PATs, scopes, expiracion,
endpoints de gestion (/auth/api/tokens) y auth de /api/employees con PAT.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.api_tokens import ApiTokenService
from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.middleware.auth import reset_rate_limit_store as reset_api_rate_limit
from src.webgui.routes.api_tokens import api_tokens_bp
from src.webgui.routes.employees import employees_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_CHAIN = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "012_api_tokens.sql",
)


def _apply_migrations(conn: sqlite3.Connection) -> None:
    for name in MIGRATION_CHAIN:
        conn.executescript((MIGRATIONS_DIR / name).read_text())


def _build_app(tmp_path: Path) -> Flask:
    db_path = tmp_path / "webgui.db"
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    _apply_migrations(conn)
    conn.close()

    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parents[1] / "src" / "webgui" / "templates"),
    )
    app.config["TESTING"] = True
    app.config["SECRET_KEY"] = "test-secret-key"
    app.db = Database(db_path)
    app.auth = Auth("test-secret-key")
    app.register_blueprint(api_tokens_bp, url_prefix="/auth/api/tokens")
    app.register_blueprint(employees_bp, url_prefix="/api/employees")

    # auth_bp solo para que url_for("auth.login") resuelva en redirect de admin_required
    from src.webgui.routes.auth import auth_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    return app


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    application = _build_app(tmp_path)
    reset_api_rate_limit()
    yield application
    reset_api_rate_limit()


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.fixture
def admin_id(app: Flask) -> int:
    return app.db.insert(
        "users",
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": app.auth.hash_password("Sup3rSecret!Pass"),
            "role": "admin",
        },
    )


@pytest.fixture
def admin_session(client, admin_id):
    with client.session_transaction() as sess:
        sess["user_id"] = admin_id
        sess["username"] = "admin"
        sess["role"] = "admin"


class TestApiTokenService:
    def test_issue_and_verify(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "CI token", ["read"])
        assert result["token"]
        record = service.verify_token(result["token"])
        assert record is not None
        assert record["name"] == "CI token"
        assert record["scopes"] == "read"

    def test_verify_updates_last_used(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["read"])
        assert result["record"]["last_used_at"] is None
        service.verify_token(result["token"])
        record = service.verify_token(result["token"])
        assert record["last_used_at"] is not None

    def test_verify_unknown_token(self, app):
        assert ApiTokenService(app.db).verify_token("no-existe") is None

    def test_verify_revoked(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["read"])
        assert service.revoke_token(result["record"]["id"])
        assert service.verify_token(result["token"]) is None

    def test_verify_expired(self, app, admin_id):
        service = ApiTokenService(app.db)
        token = service._token_secret()
        expired = (datetime.now() - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")
        app.db.insert(
            "api_tokens",
            {
                "user_id": admin_id,
                "name": "expired",
                "token_hash": service.hash_token(token),
                "scopes": "read",
                "expires_at": expired,
            },
        )
        assert service.verify_token(token) is None

    def test_verify_without_expiry_never_expires(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["read"], expires_in_days=None)
        assert result["record"]["expires_at"] is None
        assert service.verify_token(result["token"]) is not None

    def test_scope_enforced(self, app, admin_id):
        service = ApiTokenService(app.db)
        read_only = service.issue_token(admin_id, "ro", ["read"])
        assert service.verify_token(read_only["token"], required_scope="read") is not None
        assert service.verify_token(read_only["token"], required_scope="write") is None

    def test_write_scope_grants_read(self, app, admin_id):
        service = ApiTokenService(app.db)
        rw = service.issue_token(admin_id, "rw", ["read", "write"])
        assert service.verify_token(rw["token"], required_scope="read") is not None
        assert service.verify_token(rw["token"], required_scope="write") is not None

    def test_invalid_scope_rejected(self, app, admin_id):
        service = ApiTokenService(app.db)
        with pytest.raises(ValueError, match="scopes invalidos"):
            service.issue_token(admin_id, "t", ["admin"])

    def test_scopes_normalized_and_deduped(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["write", "read", "read", ""])
        assert result["record"]["scopes"] == "read write"

    def test_revoke_twice_returns_false(self, app, admin_id):
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["read"])
        assert service.revoke_token(result["record"]["id"])
        assert not service.revoke_token(result["record"]["id"])

    def test_revoke_respects_user_ownership(self, app, admin_id):
        other_id = app.db.insert(
            "users",
            {
                "username": "other",
                "password_hash": app.auth.hash_password("Sup3rSecret!Pass"),
                "role": "user",
            },
        )
        service = ApiTokenService(app.db)
        result = service.issue_token(admin_id, "t", ["read"])
        # otro usuario no puede revocar el token de admin
        assert not service.revoke_token(result["record"]["id"], user_id=other_id)
        assert not result["record"]["revoked_at"]
        # el dueno si
        assert service.revoke_token(result["record"]["id"], user_id=admin_id)

    def test_list_tokens_never_returns_hash(self, app, admin_id):
        service = ApiTokenService(app.db)
        service.issue_token(admin_id, "t", ["read"])
        tokens = service.list_tokens()
        assert len(tokens) == 1
        assert "token_hash" not in tokens[0]

    def test_hash_is_sha256(self):
        assert (
            ApiTokenService.hash_token("abc")
            == "ba7816bf8f01cfea414140de5dae2223b00361a396177a9cb410ff61f20015ad"
        )


class TestTokenManagementEndpoints:
    def test_create_requires_session(self, client):
        resp = client.post("/auth/api/tokens/", json={"name": "x", "scopes": ["read"]})
        assert resp.status_code == 302  # redirect a login

    def test_create_token(self, client, admin_session, app, admin_id):
        resp = client.post(
            "/auth/api/tokens/",
            json={"name": "CI", "scopes": ["read", "write"]},
        )
        assert resp.status_code == 201
        data = resp.get_json()
        assert data["token"]
        assert data["record"]["name"] == "CI"
        assert data["record"]["scopes"] == "read write"
        # el token plano funciona contra la DB
        assert ApiTokenService(app.db).verify_token(data["token"]) is not None

    def test_create_token_missing_name(self, client, admin_session):
        resp = client.post("/auth/api/tokens/", json={"scopes": ["read"]})
        assert resp.status_code == 400

    def test_create_token_invalid_scope(self, client, admin_session):
        resp = client.post("/auth/api/tokens/", json={"name": "x", "scopes": ["root"]})
        assert resp.status_code == 400

    def test_create_token_invalid_expiry(self, client, admin_session):
        resp = client.post(
            "/auth/api/tokens/",
            json={"name": "x", "scopes": ["read"], "expires_in_days": 9999},
        )
        assert resp.status_code == 400

    def test_list_tokens(self, client, admin_session):
        client.post("/auth/api/tokens/", json={"name": "A", "scopes": ["read"]})
        client.post("/auth/api/tokens/", json={"name": "B", "scopes": ["write"]})
        resp = client.get("/auth/api/tokens/")
        assert resp.status_code == 200
        tokens = resp.get_json()["tokens"]
        assert [t["name"] for t in tokens] == ["B", "A"]
        assert all("token_hash" not in t and "token" not in t for t in tokens)

    def test_revoke_token(self, client, admin_session):
        created = client.post(
            "/auth/api/tokens/", json={"name": "x", "scopes": ["read"]}
        ).get_json()
        resp = client.delete(f"/auth/api/tokens/{created['record']['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["revoked"] is True

        # revocar de nuevo
        resp = client.delete(f"/auth/api/tokens/{created['record']['id']}")
        assert resp.status_code == 200
        assert resp.get_json()["revoked"] is False

    def test_revoke_unknown_404(self, client, admin_session):
        resp = client.delete("/auth/api/tokens/999")
        assert resp.status_code == 404


class TestEmployeesApiWithTokens:
    def _create_employee(self, client, token, code="E001"):
        return client.post(
            "/api/employees/",
            json={"employee_code": code, "first_name": "Ana", "last_name": "Lopez"},
            headers={"Authorization": f"Bearer {token}"},
        )

    def test_no_auth_401(self, client):
        assert client.get("/api/employees/").status_code == 401

    def test_pat_read_scope_can_list(self, client, admin_session):
        token = client.post(
            "/auth/api/tokens/", json={"name": "ro", "scopes": ["read"]}
        ).get_json()["token"]
        resp = client.get(
            "/api/employees/", headers={"Authorization": f"Bearer {token}"}
        )
        assert resp.status_code == 200
        assert resp.get_json()["employees"] == []

    def test_pat_write_scope_can_create(self, client, admin_session):
        token = client.post(
            "/auth/api/tokens/",
            json={"name": "rw", "scopes": ["read", "write"]},
        ).get_json()["token"]
        assert self._create_employee(client, token).status_code == 201

    def test_pat_read_scope_cannot_create(self, client, admin_session):
        token = client.post(
            "/auth/api/tokens/", json={"name": "ro", "scopes": ["read"]}
        ).get_json()["token"]
        assert self._create_employee(client, token).status_code == 401

    def test_revoked_pat_rejected(self, client, admin_session):
        created = client.post(
            "/auth/api/tokens/", json={"name": "x", "scopes": ["read"]}
        ).get_json()
        client.delete(f"/auth/api/tokens/{created['record']['id']}")
        resp = client.get(
            "/api/employees/",
            headers={"Authorization": f"Bearer {created['token']}"},
        )
        assert resp.status_code == 401

    def test_garbage_token_401(self, client):
        resp = client.get(
            "/api/employees/", headers={"Authorization": "Bearer garbage"}
        )
        assert resp.status_code == 401

    def test_jwt_session_token_still_works(self, client, app, admin_id):
        tokens = app.auth.generate_tokens(admin_id, "admin", "admin")
        resp = client.get(
            "/api/employees/",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        assert resp.status_code == 200
