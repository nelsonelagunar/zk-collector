"""Tests para el flujo de recuperación de contraseña (MYK-303).

Cubre: página forgot/reset (query y path token), creación y consumo de tokens,
API endpoints, rate limiting y no-enumeración de emails.
"""

import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pytest
from flask import Flask

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.routes.auth import auth_bp

MIGRATIONS_DIR = Path(__file__).resolve().parents[1] / "migrations"
MIGRATION_CHAIN = (
    "001_initial_schema.sql",
    "002_employees.sql",
    "003_medical_leaves.sql",
    "004_password_reset_tokens.sql",
)


def _reset_rate_limit_store():
    from src.webgui.routes.auth import reset_rate_limit_store

    reset_rate_limit_store()


STRONG_PASSWORD = "Sup3rSecret!Pass"


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
    app.register_blueprint(auth_bp, url_prefix="/auth")
    return app


@pytest.fixture
def app(tmp_path: Path) -> Flask:
    application = _build_app(tmp_path)
    _reset_rate_limit_store()
    yield application
    _reset_rate_limit_store()


@pytest.fixture
def client(app: Flask):
    return app.test_client()


@pytest.fixture
def user_id(app: Flask) -> int:
    return app.db.insert(
        "users",
        {
            "username": "admin",
            "email": "admin@example.com",
            "password_hash": app.auth.hash_password(STRONG_PASSWORD),
            "role": "admin",
        },
    )


def _insert_reset_token(app: Flask, user_id: int, token: str, **extra) -> int:
    values = {
        "user_id": user_id,
        "token_hash": app.auth.hash_reset_token(token),
        "expires_at": (datetime.now() + timedelta(hours=1)).isoformat(),
        **extra,
    }
    return app.db.insert("password_reset_tokens", values)


class TestForgotPasswordPage:
    def test_get_renders_form(self, client):
        """Sin el fix esto es 500 (TemplateNotFound forgot_password.html)."""
        response = client.get("/auth/forgot-password")
        assert response.status_code == 200
        assert b"email" in response.data.lower()

    def test_post_without_email_shows_error(self, client):
        response = client.post("/auth/forgot-password", data={"email": ""})
        assert response.status_code == 200


class TestResetPasswordPage:
    def test_get_with_query_token(self, client, app, user_id):
        """Criterio de aceptación MYK-303: GET /auth/reset-password?token=... -> 200.
        Sin el fix esto es 404 (ruta inexistente en master)."""
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        response = client.get("/auth/reset-password", query_string={"token": token})
        assert response.status_code == 200

    def test_get_with_path_token(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        response = client.get(f"/auth/reset-password/{token}")
        assert response.status_code == 200

    def test_get_with_invalid_token_redirects(self, client):
        response = client.get("/auth/reset-password", query_string={"token": "no-existe"})
        assert response.status_code == 302
        assert "/auth/forgot-password" in response.headers["Location"]

    def test_get_without_token_redirects(self, client):
        response = client.get("/auth/reset-password")
        assert response.status_code == 302

    def test_get_with_expired_token_redirects(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(
            app, user_id, token, expires_at=(datetime.now() - timedelta(minutes=1)).isoformat()
        )
        response = client.get("/auth/reset-password", query_string={"token": token})
        assert response.status_code == 302

    def test_get_with_used_token_redirects(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token, used_at=datetime.now().isoformat())
        response = client.get("/auth/reset-password", query_string={"token": token})
        assert response.status_code == 302


class TestForgotPasswordFlow:
    def test_post_creates_token_row(self, client, app, user_id):
        response = client.post("/auth/forgot-password", data={"email": "admin@example.com"})
        assert response.status_code == 302
        rows = app.db.fetch_all("SELECT * FROM password_reset_tokens WHERE user_id = ?", (user_id,))
        assert len(rows) == 1
        assert rows[0]["used_at"] is None

    def test_post_invalidates_previous_tokens(self, client, app, user_id):
        _insert_reset_token(app, user_id, "old-token")
        client.post("/auth/forgot-password", data={"email": "admin@example.com"})
        old = app.db.fetch_one(
            "SELECT * FROM password_reset_tokens WHERE token_hash = ?",
            (app.auth.hash_reset_token("old-token"),),
        )
        assert old["used_at"] is not None

    def test_post_unknown_email_no_enumeration(self, client, app, user_id):
        """Email inexistente responde igual (302) y no crea tokens."""
        response = client.post("/auth/forgot-password", data={"email": "nadie@example.com"})
        assert response.status_code == 302
        assert app.db.fetch_all("SELECT * FROM password_reset_tokens") == []

    def test_rate_limit_after_max_requests(self, client, app, user_id):
        for _ in range(3):
            response = client.post("/auth/forgot-password", data={"email": "admin@example.com"})
            assert response.status_code == 302
        response = client.post("/auth/forgot-password", data={"email": "admin@example.com"})
        assert response.status_code == 429


class TestResetPasswordFlow:
    def test_full_reset_updates_password(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        new_password = "NuevaClave!456"
        response = client.post(
            f"/auth/reset-password/{token}",
            data={"password": new_password, "password_confirm": new_password},
        )
        assert response.status_code == 302

        user = app.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        assert app.auth.verify_password(new_password, user["password_hash"])

        reset_row = app.db.fetch_one(
            "SELECT * FROM password_reset_tokens WHERE token_hash = ?",
            (app.auth.hash_reset_token(token),),
        )
        assert reset_row["used_at"] is not None

    def test_reuse_of_used_token_fails(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        new_password = "NuevaClave!456"
        client.post(
            f"/auth/reset-password/{token}",
            data={"password": new_password, "password_confirm": new_password},
        )
        response = client.post(
            f"/auth/reset-password/{token}",
            data={"password": new_password, "password_confirm": new_password},
        )
        assert response.status_code == 302
        assert "/auth/forgot-password" in response.headers["Location"]

    def test_weak_password_rejected(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        response = client.post(
            f"/auth/reset-password/{token}",
            data={"password": "weak", "password_confirm": "weak"},
        )
        assert response.status_code == 200
        user = app.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        assert not app.auth.verify_password("weak", user["password_hash"])


class TestPasswordResetApi:
    def test_api_forgot_password(self, client, app, user_id):
        response = client.post("/auth/api/forgot-password", json={"email": "admin@example.com"})
        assert response.status_code == 200
        body = response.get_json()
        assert body["success"] is True
        assert app.db.fetch_all("SELECT * FROM password_reset_tokens WHERE user_id = ?", (user_id,))

    def test_api_forgot_password_requires_email(self, client):
        response = client.post("/auth/api/forgot-password", json={})
        assert response.status_code == 400

    def test_api_forgot_password_rate_limited(self, client, app, user_id):
        for _ in range(3):
            client.post("/auth/api/forgot-password", json={"email": "admin@example.com"})
        response = client.post("/auth/api/forgot-password", json={"email": "admin@example.com"})
        assert response.status_code == 429

    def test_api_reset_password_full_flow(self, client, app, user_id):
        token = app.auth.generate_password_reset_token()
        _insert_reset_token(app, user_id, token)
        new_password = "NuevaClave!456"
        response = client.post(
            "/auth/api/reset-password",
            json={
                "token": token,
                "password": new_password,
                "password_confirm": new_password,
            },
        )
        assert response.status_code == 200
        assert response.get_json()["success"] is True
        user = app.db.fetch_one("SELECT * FROM users WHERE id = ?", (user_id,))
        assert app.auth.verify_password(new_password, user["password_hash"])

    def test_api_reset_password_invalid_token(self, client):
        response = client.post(
            "/auth/api/reset-password",
            json={
                "token": "malo",
                "password": "NuevaClave!456",
                "password_confirm": "NuevaClave!456",
            },
        )
        assert response.status_code == 400

    def test_api_reset_password_missing_fields(self, client):
        response = client.post("/auth/api/reset-password", json={})
        assert response.status_code == 400


class TestResetTokenHelpers:
    def test_hash_is_deterministic(self, app):
        token = "abc123"
        assert app.auth.hash_reset_token(token) == app.auth.hash_reset_token(token)

    def test_verify_reset_token(self, app):
        token = "abc123"
        token_hash = app.auth.hash_reset_token(token)
        assert app.auth.verify_reset_token(token, token_hash) is True
        assert app.auth.verify_reset_token("otro", token_hash) is False

    def test_generate_reset_token_and_hash_pair(self, app):
        token, token_hash = app.auth.generate_reset_token_and_hash()
        assert token and token_hash
        assert app.auth.verify_reset_token(token, token_hash) is True
