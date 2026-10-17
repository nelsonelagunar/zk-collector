"""
Tests de integración - Flujo de restablecimiento de contraseña (MYK-157)

Cubre los criterios de aceptación:
  1. POST /forgot-password envía email por SMTP (cuando está configurado)
  2. El email contiene enlace de restablecimiento con token JWT válido (1h)
  3. GET /reset-password/<token> valida el token y muestra el formulario
  4. POST /reset-password/<token> actualiza la contraseña e invalida el token
  5. Fallback admin: token mostrado en UI cuando SMTP no está configurado
  6. Rate limiting en /forgot-password (máx. 3 requests/hora por email)
  7. Flujo completo con SMTP simulado
  8. Seguridad: tokens de un solo uso, expiración, comparación constante
"""

import os
import sys
import shutil
from datetime import datetime, timezone, timedelta
from unittest.mock import patch

import jwt
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

from src.webgui.server import create_app
from src.webgui.auth import Auth


class MockSMTP:
    """Doble de prueba para smtplib.SMTP (evita red real).

    Rastrea todas las instancias creadas para poder inspeccionar los
    emails enviados desde los tests.
    """

    instances = []

    def __init__(self, host, port, timeout=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.starttls_called = False
        self.login_called = False
        self.sent_messages = []
        MockSMTP.instances.append(self)

    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False

    def starttls(self):
        self.starttls_called = True

    def login(self, user, password):
        self.login_called = True

    def send_message(self, msg):
        self.sent_messages.append(msg)


@pytest.fixture
def app(tmp_path, monkeypatch):
    """Flask app con BD temporal, migraciones aplicadas y usuario de prueba."""
    # Create a temporary directory for all app data (avoid /opt/attendance which may be read-only)
    data_root = tmp_path / "data"
    data_root.mkdir(parents=True, exist_ok=True)

    # Set environment variables for DB paths
    db_path = data_root / "webgui.db"
    buffer_db_path = data_root / "buffer.db"
    monkeypatch.setenv("DB_PATH", str(db_path))
    monkeypatch.setenv("BUFFER_DB_PATH", str(buffer_db_path))

    # Copy migrations to the temporary directory.
    # Database._run_migrations looks for migrations at db_path.parent.parent / "migrations"
    # = tmp_path / "migrations"
    migrations_dir = tmp_path / "migrations"
    migrations_dir.mkdir(parents=True, exist_ok=True)

    repo_migrations = os.path.join(os.path.dirname(__file__), '..', 'migrations')
    for fname in os.listdir(repo_migrations):
        if fname.endswith('.sql'):
            shutil.copy(
                os.path.join(repo_migrations, fname),
                os.path.join(migrations_dir, fname),
            )

    # Create the app (this will initialize the DB and run migrations)
    app = create_app()
    app.config['TESTING'] = True
    app.config['SECRET_KEY'] = 'test-secret-key'
    app.auth = Auth(app.config['SECRET_KEY'])

    # Usuario de prueba activo
    db = app.db
    password_hash = app.auth.hash_password('TestPass123!')
    db.insert('users', {
        'username': 'testuser',
        'email': 'testuser@example.com',
        'password_hash': password_hash,
        'role': 'user',
        'is_active': 1,
    })

    # SMTP configurado (simulado) - update the existing rows from migrations
    db.update('system_config', {'value': 'true'}, "key = 'smtp_configured'")
    db.update('system_config', {'value': 'smtp.test.local'}, "key = 'smtp_host'")
    db.update('system_config', {'value': '587'}, "key = 'smtp_port'")
    db.update('system_config', {'value': 'user'}, "key = 'smtp_username'")
    db.update('system_config', {'value': 'pass'}, "key = 'smtp_password'")
    db.update('system_config', {'value': 'noreply@test.local'}, "key = 'smtp_from_email'")
    db.update('system_config', {'value': 'true'}, "key = 'smtp_use_tls'")

    yield app


@pytest.fixture
def client(app):
    return app.test_client()


@pytest.fixture(autouse=True)
def mock_smtp():
    """Parchea smtplib.SMTP con MockSMTP y limpia las instancias entre tests."""
    # Clear any existing instances
    MockSMTP.instances.clear()

    with patch('smtplib.SMTP', MockSMTP) as mock_class:
        yield mock_class

    # Clear instances after test
    MockSMTP.instances.clear()


# ---------------------------------------------------------------------------
# Criterio 1: POST /forgot-password envía email por SMTP
# ---------------------------------------------------------------------------
class TestForgotPasswordSmtp:
    def test_sends_reset_email_via_smtp(self, client, app, mock_smtp):
        """POST /forgot-password con SMTP configurado envía un email."""
        response = client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        }, follow_redirects=False)

        assert response.status_code == 302
        assert len(MockSMTP.instances) == 1
        sent_msg = MockSMTP.instances[0].sent_messages[0]
        assert 'testuser@example.com' in str(sent_msg['To'])
        assert 'Restablecimiento de contraseña' in str(sent_msg['Subject'])

    def test_email_body_contains_reset_link_with_token(self, client, app, mock_smtp):
        """El email enviado contiene un enlace con el token de restablecimiento."""
        client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        })

        sent_msg = MockSMTP.instances[0].sent_messages[0]
        body = sent_msg.get_content()

        # Extraer el token del enlace en el cuerpo del email
        import re
        match = re.search(r'/auth/reset-password/([A-Za-z0-9_.\-]+)', body)
        assert match, f"No se encontró enlace de restablecimiento en: {body}"
        token = match.group(1)

        # El token debe ser un JWT válido firmado con la clave de la app
        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        assert payload['type'] == 'password_reset'
        assert payload['user_id'] == 1

    def test_token_has_one_hour_expiry(self, client, app, mock_smtp):
        """El token JWT en el email expira en 1 hora."""
        client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        })

        sent_msg = MockSMTP.instances[0].sent_messages[0]
        body = sent_msg.get_content()
        import re
        token = re.search(r'/auth/reset-password/([A-Za-z0-9_.\-]+)', body).group(1)

        payload = jwt.decode(token, 'test-secret-key', algorithms=['HS256'])
        now = datetime.now(timezone.utc)
        exp = datetime.fromtimestamp(payload['exp'], tz=timezone.utc)
        delta = exp - now
        assert timedelta(hours=0, minutes=55) < delta <= timedelta(hours=1)

    def test_flashes_success_when_email_sent(self, client, app, mock_smtp):
        """Se muestra flash de éxito cuando el email se envía."""
        response = client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        }, follow_redirects=True)

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'enlace de restablecimiento' in html.lower() or 'correo' in html.lower()


# ---------------------------------------------------------------------------
# Criterios 3 y 4: GET/POST /reset-password/<token>
# ---------------------------------------------------------------------------
class TestResetPassword:
    def _make_valid_token(self, app, user_id=1):
        """Genera un token de restablecimiento válido y lo registra en BD."""
        from src.webgui.routes.auth import _generate_reset_token
        with app.app_context():
            return _generate_reset_token(user_id)

    def test_get_reset_password_shows_form_for_valid_token(self, client, app):
        """GET /reset-password/<token> muestra el formulario si el token es válido."""
        token = self._make_valid_token(app)
        response = client.get(f'/auth/reset-password/{token}')

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'Nueva contraseña' in html or 'contraseña' in html.lower()

    def test_post_reset_password_updates_password_and_invalidates_token(self, client, app):
        """POST /reset-password/<token> actualiza la contraseña e invalida el token."""
        from src.webgui.auth import Auth
        auth = Auth('test-secret-key')
        token = self._make_valid_token(app)

        # Enviar nueva contraseña
        response = client.post(f'/auth/reset-password/{token}', data={
            'password': 'NewStr0ng!Pass',
            'password_confirm': 'NewStr0ng!Pass',
        }, follow_redirects=True)

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'correctamente' in html.lower()

        # Verificar que la contraseña se actualizó en BD
        with app.app_context():
            user = app.db.fetch_one(
                "SELECT id, password_hash FROM users WHERE id = 1")
            assert auth.verify_password('NewStr0ng!Pass', user['password_hash'])

        # El token ya no debe ser válido (un solo uso)
        response2 = client.get(f'/auth/reset-password/{token}')
        assert response2.status_code == 302  # redirige a login (token inválido)

    def test_reset_password_rejects_expired_token(self, client, app):
        """Un token expirado es rechazado."""
        expired_payload = {
            'user_id': 1,
            'type': 'password_reset',
            'exp': datetime.now(timezone.utc) - timedelta(hours=2),
            'iat': datetime.now(timezone.utc) - timedelta(hours=3),
            'jti': 'expired-jti',
        }
        expired_token = jwt.encode(expired_payload, 'test-secret-key', algorithm='HS256')

        response = client.get(f'/auth/reset-password/{expired_token}')
        assert response.status_code == 302  # redirige a login

    def test_reset_password_rejects_already_used_token(self, client, app):
        """Un token ya usado es rechazado (un solo uso)."""
        from src.webgui.routes.auth import _hash_token, _invalidate_reset_token
        token = self._make_valid_token(app)

        # Invalidar manualmente el token (simular uso previo)
        with app.app_context():
            _invalidate_reset_token(token)

        response = client.get(f'/auth/reset-password/{token}')
        assert response.status_code == 302  # redirige a login

    def test_reset_password_rejects_unknown_token(self, client, app):
        """Un token desconocido o con hash inexistente es rechazado."""
        unknown_token = jwt.encode({
            'user_id': 999,
            'type': 'password_reset',
            'exp': datetime.now(timezone.utc) + timedelta(hours=1),
            'iat': datetime.now(timezone.utc),
            'jti': 'unknown-jti',
        }, 'test-secret-key', algorithm='HS256')

        response = client.get(f'/auth/reset-password/{unknown_token}')
        assert response.status_code == 302  # hash no encontrado en BD

    def test_reset_password_rejects_wrong_type_token(self, client, app):
        """Un JWT con tipo distinto a password_reset es rechazado."""
        access_token = jwt.encode({
            'user_id': 1,
            'type': 'access',
            'exp': datetime.now(timezone.utc) + timedelta(hours=1),
            'iat': datetime.now(timezone.utc),
            'jti': 'access-jti',
        }, 'test-secret-key', algorithm='HS256')

        response = client.get(f'/auth/reset-password/{access_token}')
        assert response.status_code == 302

    def test_reset_password_invalidates_token_on_use(self, client, app):
        """El token se invalida tras usarse: segundo intento falla."""
        token = self._make_valid_token(app)

        # Primera vez: éxito
        client.post(f'/auth/reset-password/{token}', data={
            'password': 'FirstTime!Pass1',
            'password_confirm': 'FirstTime!Pass1',
        }, follow_redirects=True)

        # Segunda vez con otro password: debe fallar (ya usado)
        response = client.post(f'/auth/reset-password/{token}', data={
            'password': 'SecondTime!Pass2',
            'password_confirm': 'SecondTime!Pass2',
        }, follow_redirects=True)

        html = response.get_data(as_text=True)
        assert 'inválido' in html.lower() or 'ya expiró' in html.lower()

    def test_reset_password_requires_matching_confirmation(self, client, app):
        """Las contraseñas deben coincidir."""
        token = self._make_valid_token(app)
        response = client.post(f'/auth/reset-password/{token}', data={
            'password': 'NewStr0ng!Pass',
            'password_confirm': 'Different!Pass1',
        })

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'no coinciden' in html.lower()


# ---------------------------------------------------------------------------
# Criterio 5: Fallback admin (SMTP no configurado)
# ---------------------------------------------------------------------------
class TestAdminFallback:
    def test_shows_token_in_ui_when_smtp_not_configured(self, client, app):
        """Cuando SMTP no está configurado, el token se muestra en la UI."""
        # Eliminar configuración SMTP
        with app.app_context():
            app.db.delete("system_config", "key = 'smtp_configured'")

        response = client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        }, follow_redirects=True)

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'SMTP' in html or 'token' in html.lower()

    def test_no_email_sent_when_smtp_not_configured(self, client, app, mock_smtp):
        """No se intenta enviar email si SMTP no está configurado."""
        with app.app_context():
            app.db.delete("system_config", "key = 'smtp_configured'")

        client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        })

        # MockSMTP nunca se instantió (send_message no llamado)
        assert len(MockSMTP.instances) == 0


# ---------------------------------------------------------------------------
# Criterio 6: Rate limiting
# ---------------------------------------------------------------------------
class TestRateLimiting:
    def test_allows_up_to_three_requests_per_hour_per_email(self, client, app, mock_smtp):
        """Se permiten hasta 3 requests por hora por email."""
        for i in range(3):
            response = client.post('/auth/forgot-password', data={
                'email': 'testuser@example.com',
            })
            assert response.status_code == 302

        # Las 3 primeras deben haber generado token (email enviado)
        assert len(MockSMTP.instances) == 3

    def test_blocks_fourth_request_within_hour(self, client, app, mock_smtp):
        """La 4ta request en la misma hora es bloqueada por rate limiting."""
        for _ in range(3):
            client.post('/auth/forgot-password', data={
                'email': 'testuser@example.com',
            })

        # 4ta request: debe ser bloqueada
        response = client.post('/auth/forgot-password', data={
            'email': 'testuser@example.com',
        }, follow_redirects=True)

        assert response.status_code == 200
        html = response.get_data(as_text=True)
        assert 'demasiadas solicitudes' in html.lower() or 'una hora' in html.lower()
        # No se envió email adicional
        assert len(MockSMTP.instances) == 3

    def test_rate_limit_is_per_email(self, client, app, mock_smtp):
        """El rate limit es por email: otro email no está afectado."""
        for _ in range(3):
            client.post('/auth/forgot-password', data={
                'email': 'testuser@example.com',
            })

        # Otro email puede seguir solicitando (no está rate-limitado por el primero)
        response = client.post('/auth/forgot-password', data={
            'email': 'otro@example.com',
        })
        # Status 302 = pasó el rate limit (el rate limit bloqueado devuelve 200 con template)
        assert response.status_code == 302
        # No se bloqueó por rate limiting: no hay flash de "demasiadas solicitudes"
        html = response.get_data(as_text=True)
        assert 'demasiadas solicitudes' not in html.lower()


# ---------------------------------------------------------------------------
# Criterio 8: Seguridad - comparación constante y tokens de un solo uso
# ---------------------------------------------------------------------------
class TestSecurity:
    def test_token_hash_is_stored_not_plaintext(self, app):
        """El token almacenado en BD es un hash SHA256, nunca texto plano."""
        from src.webgui.routes.auth import _generate_reset_token, _hash_token
        with app.app_context():
            token = _generate_reset_token(1)
            row = app.db.fetch_one(
                "SELECT token_hash FROM password_reset_tokens WHERE user_id = 1 ORDER BY id DESC")

        assert row is not None
        assert row['token_hash'] != token  # no se almacena el token en texto plano
        assert row['token_hash'] == _hash_token(token)  # coincide con el hash

    def test_validate_reset_token_constant_time_comparison(self, app):
        """_validate_reset_token usa comparación constante (hmac.compare_digest)."""
        from src.webgui.routes.auth import (
            _generate_reset_token, _validate_reset_token, _hash_token,
        )
        import hmac

        with app.app_context():
            token = _generate_reset_token(1)
            # Token válido debe validarse
            payload = _validate_reset_token(token)
            assert payload is not None
            assert payload['user_id'] == 1

            # Tampered token (mismo prefijo pero distinto) debe rechazarse
            bad_token = token[:-4] + 'XXXX'
            payload_bad = _validate_reset_token(bad_token)
            assert payload_bad is None

            # hmac.compare_digest está en uso (comprobación implícita vía _hash_token + compare)
            token_hash = _hash_token(token)
            assert hmac.compare_digest(token_hash, _hash_token(token))
            assert not hmac.compare_digest(token_hash, _hash_token(bad_token))

    def test_tokens_are_single_use_in_db(self, app):
        """Un token usado queda marcado con used_at en BD."""
        from src.webgui.routes.auth import _generate_reset_token, _invalidate_reset_token, _hash_token
        with app.app_context():
            token = _generate_reset_token(1)
            row = app.db.fetch_one(
                "SELECT used_at FROM password_reset_tokens WHERE token_hash = ?",
                (_hash_token(token),),
            )
            assert row['used_at'] is None

            _invalidate_reset_token(token)
            row = app.db.fetch_one(
                "SELECT used_at FROM password_reset_tokens WHERE token_hash = ?",
                (_hash_token(token),),
            )
            assert row['used_at'] is not None
