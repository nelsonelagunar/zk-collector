"""
Unit tests for WebGUI Auth module (password reset flow)
"""

from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from flask import Flask, jsonify, redirect, session, url_for

from src.webgui.auth import Auth
from src.webgui.database import Database
from src.webgui.mail import Mailer
from src.webgui.routes.auth import reset_rate_limit_store


@pytest.fixture
def app(tmp_path):
    """Create a Flask app for testing"""
    db_path = tmp_path / "data" / "webgui.db"
    buffer_db_path = tmp_path / "data" / "buffer.db"
    db_path.parent.mkdir(parents=True, exist_ok=True)


    template_dir = Path(__file__).parent.parent.parent.parent / "src" / "webgui" / "templates"

    app = Flask(__name__, template_folder=str(template_dir))
    app.config["SECRET_KEY"] = "test-secret-key"
    app.config["TESTING"] = True

    # Initialize database
    app.db = Database(db_path)
    # Copy migrations to temp dir for testing - db_path.parent.parent is where database.py looks
    import shutil

    migrations_src = Path(__file__).parent.parent.parent.parent / "migrations"
    migrations_dst = db_path.parent.parent / "migrations"
    if migrations_src.exists():
        shutil.copytree(migrations_src, migrations_dst, dirs_exist_ok=True)
    app.db.initialize()

    # Auth instance
    app.auth = Auth(app.config["SECRET_KEY"])

    # Buffer repository
    app.buffer_repo = MagicMock()

    # Register all blueprints like create_app does
    from src.webgui.routes.apidocs import apidocs_bp
    from src.webgui.routes.attendance import attendance_bp
    from src.webgui.routes.auth import auth_bp
    from src.webgui.routes.devices import devices_bp

    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(devices_bp, url_prefix="/devices")
    app.register_blueprint(apidocs_bp, url_prefix="/api")
    app.register_blueprint(attendance_bp)

    # Add index route like create_app
    @app.route("/")
    def index():
        if "user_id" not in session:
            return redirect(url_for("auth.login"))
        return "Dashboard"

    @app.route("/health")
    def health():
        return jsonify({"status": "healthy", "version": "1.0.0"})

    return app


@pytest.fixture
def client(app):
    """Create a test client"""
    return app.test_client()


@pytest.fixture
def api_client(app):
    """Create a test client with rate limit reset for API tests"""
    reset_rate_limit_store()
    return app.test_client()


@pytest.fixture
def auth():
    """Create an Auth instance for testing"""
    return Auth("test-secret-key")


@pytest.fixture
def test_user(app):
    """Create a test user in the database"""
    auth_instance = app.auth
    password_hash = auth_instance.hash_password("TestPass123!")

    user_id = app.db.insert(
        "users",
        {
            "username": "testuser",
            "email": "test@example.com",
            "password_hash": password_hash,
            "role": "admin",
        },
    )

    return {"id": user_id, "username": "testuser", "email": "test@example.com"}


class TestAuthPasswordReset:
    """Tests for password reset functionality"""

    def test_generate_password_reset_token(self, auth):
        """Test reset token generation"""
        token = Auth.generate_password_reset_token()

        assert isinstance(token, str)
        assert len(token) > 20  # URL-safe base64 of 32 bytes

        # Each call should generate a unique token
        token2 = Auth.generate_password_reset_token()
        assert token != token2

    def test_hash_reset_token(self, auth):
        """Test reset token hashing"""
        token = "test-token-123"
        token_hash = Auth.hash_reset_token(token)

        assert isinstance(token_hash, str)
        assert len(token_hash) == 64  # SHA256 hex

        # Same token should produce same hash
        assert Auth.hash_reset_token(token) == token_hash

        # Different token should produce different hash
        assert Auth.hash_reset_token("different") != token_hash

    def test_verify_reset_token(self, auth):
        """Test reset token verification"""
        token = "test-token-123"
        token_hash = Auth.hash_reset_token(token)

        assert Auth.verify_reset_token(token, token_hash) is True
        assert Auth.verify_reset_token("wrong", token_hash) is False

    def test_generate_reset_token_and_hash(self, auth):
        """Test generating token and hash together"""
        token, token_hash = auth.generate_reset_token_and_hash()

        assert isinstance(token, str)
        assert isinstance(token_hash, str)
        assert len(token_hash) == 64

        # Token should verify against its hash
        assert Auth.verify_reset_token(token, token_hash) is True

    def test_validate_password_strength_valid(self, auth):
        """Test password strength validation - valid passwords"""
        # 12+ chars, upper, lower, digit, special
        valid_passwords = [
            "TestPass123!",
            "MySecure1@Pass",
            "Complex#Pass123",
            "LongEnough123$Pass",
        ]

        for pwd in valid_passwords:
            is_valid, errors = Auth.validate_password_strength(pwd)
            assert is_valid is True, f"Expected '{pwd}' to be valid, got errors: {errors}"
            assert errors == []

    def test_validate_password_strength_invalid(self, auth):
        """Test password strength validation - invalid passwords"""
        test_cases = [
            ("short1!", ["Mínimo 12 caracteres"]),
            ("nouppercase123!", ["Al menos una mayúscula"]),
            ("NOLOWERCASE123!", ["Al menos una minúscula"]),
            ("NoDigitsHere!", ["Al menos un número"]),
            ("NoSpecialChar123", ["Al menos un carácter especial"]),
            (
                "",
                [
                    "Mínimo 12 caracteres",
                    "Al menos una mayúscula",
                    "Al menos una minúscula",
                    "Al menos un número",
                    "Al menos un carácter especial",
                ],
            ),
        ]

        for pwd, expected_errors in test_cases:
            is_valid, errors = Auth.validate_password_strength(pwd)
            assert is_valid is False
            for err in expected_errors:
                assert err in errors, f"Expected '{err}' in errors for '{pwd}', got: {errors}"

    def test_forgot_password_get(self, client):
        """Test GET /auth/forgot-password renders template"""
        response = client.get("/auth/forgot-password")

        assert response.status_code == 200
        assert b"Recuperar Contrase" in response.data
        assert b"Email" in response.data

    def test_forgot_password_post_no_email(self, client):
        """Test POST /auth/forgot-password without email"""
        response = client.post("/auth/forgot-password", data={})

        assert response.status_code == 200  # Returns form with error
        assert b"Por favor ingresa tu email" in response.data

    def test_forgot_password_post_nonexistent_email(self, client, test_user):
        """Test POST /auth/forgot-password with non-existent email (should not reveal)"""
        response = client.post("/auth/forgot-password", data={"email": "nonexistent@example.com"})

        assert response.status_code == 302  # Redirect to login
        # Should show success message for security (no user enumeration)
        with client.session_transaction() as sess:
            pass  # Flash messages not easily testable in this setup

    def test_forgot_password_post_existing_email_no_smtp(self, client, test_user, app):
        """Test POST /auth/forgot-password with existing email, no SMTP configured"""
        # No SMTP configured, should show token in flash
        response = client.post("/auth/forgot-password", data={"email": "test@example.com"})

        assert response.status_code == 302  # Redirect to login

        # Check that token was stored in DB
        token_record = app.db.fetch_one(
            "SELECT token_hash, expires_at, used_at FROM password_reset_tokens WHERE user_id = ?",
            (test_user["id"],),
        )

        assert token_record is not None
        assert token_record["token_hash"] is not None
        assert token_record["used_at"] is None
        assert token_record["expires_at"] is not None

    def test_reset_password_get_valid_token(self, client, test_user, app):
        """Test GET /auth/reset-password/<token> with valid token"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

        app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        response = client.get(f"/auth/reset-password/{token}")

        assert response.status_code == 200
        assert b"Nueva Contrase" in response.data
        assert "Mínimo 12 caracteres".encode() in response.data  # Password strength hints

    def test_reset_password_get_invalid_token(self, client, test_user, app):
        """Test GET /auth/reset-password/<token> with invalid token"""
        response = client.get("/auth/reset-password/invalid-token")

        assert response.status_code == 302  # Redirect to forgot password
        # Flash message should be set

    def test_reset_password_get_expired_token(self, client, test_user, app):
        """Test GET /auth/reset-password/<token> with expired token"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() - timedelta(hours=1)).isoformat()  # Expired

        app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        response = client.get(f"/auth/reset-password/{token}")

        assert response.status_code == 302  # Redirect to forgot password

    def test_reset_password_get_used_token(self, client, test_user, app):
        """Test GET /auth/reset-password/<token> with already used token"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

        token_id = app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
                "used_at": datetime.now().isoformat(),  # Already used
            },
        )

        response = client.get(f"/auth/reset-password/{token}")

        assert response.status_code == 302  # Redirect to forgot password

    def test_reset_password_post_password_mismatch(self, client, test_user, app):
        """Test POST /auth/reset-password with mismatched passwords"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

        app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        response = client.post(
            f"/auth/reset-password/{token}",
            data={"password": "NewPass123!", "password_confirm": "DifferentPass123!"},
        )

        assert response.status_code == 200  # Returns form with error
        assert "Las contraseñas no coinciden".encode() in response.data

    def test_reset_password_post_weak_password(self, client, test_user, app):
        """Test POST /auth/reset-password with weak password"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

        app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        response = client.post(
            f"/auth/reset-password/{token}", data={"password": "weak", "password_confirm": "weak"}
        )

        assert response.status_code == 200  # Returns form with errors
        assert "Mínimo 12 caracteres".encode() in response.data

    def test_reset_password_post_valid(self, client, test_user, app):
        """Test POST /auth/reset-password with valid data"""
        auth_instance = app.auth
        token, token_hash = auth_instance.generate_reset_token_and_hash()
        expires_at = (datetime.now() + timedelta(hours=1)).isoformat()

        app.db.insert(
            "password_reset_tokens",
            {
                "user_id": test_user["id"],
                "token_hash": token_hash,
                "expires_at": expires_at,
            },
        )

        new_password = "NewStrongPass123!"
        response = client.post(
            f"/auth/reset-password/{token}",
            data={"password": new_password, "password_confirm": new_password},
        )

        assert response.status_code == 302  # Redirect to login

        # Verify password was updated
        user = app.db.fetch_one("SELECT password_hash FROM users WHERE id = ?", (test_user["id"],))
        assert user is not None
        assert auth_instance.verify_password(new_password, user["password_hash"]) is True

        # Verify token was marked as used
        token_record = app.db.fetch_one(
            "SELECT used_at FROM password_reset_tokens WHERE id = ?",
            (token_hash,),  # Wait, we need to look up by hash
        )
        # Actually need to query by hash
        token_record = app.db.fetch_one(
            "SELECT used_at FROM password_reset_tokens WHERE token_hash = ?", (token_hash,)
        )
        assert token_record is not None
        assert token_record["used_at"] is not None


class TestAuthAPIEndpoints:
    """Tests for API endpoints"""

    def test_api_forgot_password_no_email(self, api_client):
        """Test API forgot password without email"""
        response = api_client.post("/auth/api/forgot-password", json={})

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Email es requerido" in data["message"]

    def test_api_forgot_password_rate_limit(self, api_client):
        """Test API forgot password rate limiting"""
        # Make 3 requests (limit is 3 per hour)
        for i in range(3):
            response = api_client.post(
                "/auth/api/forgot-password", json={"email": "test@example.com"}
            )
            assert response.status_code == 200  # Always returns success to prevent enumeration

        # 4th request should be rate limited
        response = api_client.post("/auth/api/forgot-password", json={"email": "test@example.com"})
        assert response.status_code == 429
        data = response.get_json()
        assert data["success"] is False
        assert "Demasiadas solicitudes" in data["message"]

    def test_api_reset_password_missing_fields(self, api_client):
        """Test API reset password with missing fields"""
        response = api_client.post("/auth/api/reset-password", json={"token": "abc"})

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Token y contraseña son requeridos" in data["message"]

    def test_api_reset_password_mismatch(self, api_client):
        """Test API reset password with mismatched passwords"""
        response = api_client.post(
            "/auth/api/reset-password",
            json={"token": "abc", "password": "pass1", "password_confirm": "pass2"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Las contraseñas no coinciden" in data["message"]

    def test_api_reset_password_weak_password(self, api_client):
        """Test API reset password with weak password"""
        response = api_client.post(
            "/auth/api/reset-password",
            json={"token": "abc", "password": "weak", "password_confirm": "weak"},
        )

        assert response.status_code == 400
        data = response.get_json()
        assert data["success"] is False
        assert "Contraseña débil" in data["message"]
        assert "errors" in data


class TestMailer:
    """Tests for Mailer class"""

    def test_mailer_from_config_no_smtp(self, app):
        """Test Mailer.from_config returns None when SMTP not configured"""
        config = {
            "smtp_host": "",
            "smtp_configured": "false",
        }
        mailer = Mailer.from_config(config)
        assert mailer is None

    def test_mailer_from_config_not_configured(self):
        """Test Mailer.from_config returns None when smtp_configured is false"""
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_configured": "false",
        }
        mailer = Mailer.from_config(config)
        assert mailer is None

    def test_mailer_from_config_valid(self):
        """Test Mailer.from_config with valid config"""
        config = {
            "smtp_host": "smtp.example.com",
            "smtp_port": "587",
            "smtp_username": "user@example.com",
            "smtp_password": "password",
            "smtp_from_email": "from@example.com",
            "smtp_use_tls": "true",
            "smtp_configured": "true",
        }
        mailer = Mailer.from_config(config)

        assert mailer is not None
        assert mailer.host == "smtp.example.com"
        assert mailer.port == 587
        assert mailer.username == "user@example.com"
        assert mailer.password == "password"
        assert mailer.from_email == "from@example.com"
        assert mailer.use_tls is True


class TestLoginFlow:
    """Tests for login flow with password reset link"""

    def test_login_page_has_forgot_password_link(self, client):
        """Test login page has 'Forgot Password' link"""
        response = client.get("/auth/login")

        assert response.status_code == 200
        assert "¿Olvidaste tu contraseña?".encode() in response.data
        assert b"/auth/forgot-password" in response.data

    def test_login_post_invalid_credentials(self, client, test_user):
        """Test login with invalid credentials"""
        response = client.post(
            "/auth/login", data={"username": "testuser", "password": "WrongPass123!"}
        )

        assert response.status_code == 200  # Returns form with error
        assert "Usuario o contraseña inválidos".encode() in response.data

    def test_login_post_valid_credentials(self, client, test_user):
        """Test login with valid credentials"""
        response = client.post(
            "/auth/login", data={"username": "testuser", "password": "TestPass123!"}
        )

        assert response.status_code == 302  # Redirect to dashboard

        # Verify session was set
        with client.session_transaction() as sess:
            assert sess["user_id"] == test_user["id"]
            assert sess["username"] == "testuser"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
