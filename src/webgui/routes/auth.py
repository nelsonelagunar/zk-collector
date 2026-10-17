"""
Auth Routes - Login, Logout, Setup, Password Reset
"""

from datetime import datetime, timezone, timedelta
import hashlib
import hmac
import logging
import smtplib
from email.message import EmailMessage

import jwt
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

auth_bp = Blueprint('auth', __name__)

logger = logging.getLogger(__name__)

# Password reset token settings
RESET_TOKEN_EXPIRY_HOURS = 1
RESET_RATE_LIMIT_MAX = 3           # max requests per window
RESET_RATE_LIMIT_WINDOW_HOURS = 1  # sliding window in hours


def _hash_token(token: str) -> str:
    """Hash a reset token for storage (never store plaintext tokens)."""
    return hashlib.sha256(token.encode('utf-8')).hexdigest()


def _hash_email(email: str) -> str:
    """Hash an email for rate-limit storage (privacy by design)."""
    return hashlib.sha256(email.encode('utf-8')).hexdigest()


def _get_smtp_config() -> dict | None:
    """Read SMTP configuration from system_config, falling back to env vars.

    Returns a dict with host, port, username, password, from_email, use_tls
    or None when SMTP is not configured.
    """
    db = current_app.db
    keys = [
        'smtp_host', 'smtp_port', 'smtp_username', 'smtp_password',
        'smtp_from_email', 'smtp_use_tls', 'smtp_configured',
    ]
    config = {}
    for key in keys:
        row = db.fetch_one(
            "SELECT value FROM system_config WHERE key = ?", (key,))
        config[key] = row['value'] if row else None

    # Fall back to environment variables when system_config is not populated
    if not config.get('smtp_host'):
        config['smtp_host'] = __import__('os').environ.get('SMTP_HOST', '')
    if not config.get('smtp_port'):
        config['smtp_port'] = __import__('os').environ.get('SMTP_PORT', '587')
    if not config.get('smtp_username'):
        config['smtp_username'] = __import__('os').environ.get('SMTP_USERNAME', '')
    if not config.get('smtp_password'):
        config['smtp_password'] = __import__('os').environ.get('SMTP_PASSWORD', '')
    if not config.get('smtp_from_email'):
        config['smtp_from_email'] = __import__('os').environ.get('SMTP_FROM_EMAIL', '')
    if not config.get('smtp_use_tls'):
        config['smtp_use_tls'] = __import__('os').environ.get('SMTP_USE_TLS', 'true')
    if not config.get('smtp_configured'):
        config['smtp_configured'] = __import__('os').environ.get('SMTP_CONFIGURED', 'false')

    if config.get('smtp_configured') != 'true' or not config.get('smtp_host'):
        return None

    try:
        config['smtp_port'] = int(config['smtp_port'])
    except (TypeError, ValueError):
        config['smtp_port'] = 587

    return config


def _send_reset_email(to_email: str, reset_link: str) -> bool:
    """Send a password reset email via SMTP.

    Returns True if the email was sent successfully, False otherwise.
    Never raises — failures are logged and the caller falls back to admin UI.
    """
    config = _get_smtp_config()
    if not config:
        logger.warning("SMTP not configured; cannot send reset email")
        return False

    msg = EmailMessage()
    msg['Subject'] = 'Restablecimiento de contraseña - Attendance Collector'
    msg['From'] = config['smtp_from_email'] or 'noreply@localhost'
    msg['To'] = to_email
    msg.set_content(
        f"Hola,\n\nRecibiste una solicitud para restablecer tu contraseña de Attendance Collector.\n"
        f"Haz clic en el siguiente enlace para crear una contraseña nueva:\n\n{reset_link}\n\n"
        f"El enlace expira en {RESET_TOKEN_EXPIRY_HOURS} hora y solo puede usarse una vez.\n\n"
        f"Si no solicitaste este cambio, ignora este mensaje.\n"
    )

    try:
        if config['smtp_use_tls'] == 'true':
            with smtplib.SMTP(config['smtp_host'], config['smtp_port'], timeout=10) as server:
                server.starttls()
                if config['smtp_username'] and config['smtp_password']:
                    server.login(config['smtp_username'], config['smtp_password'])
                server.send_message(msg)
        else:
            with smtplib.SMTP(config['smtp_host'], config['smtp_port'], timeout=10) as server:
                if config['smtp_username'] and config['smtp_password']:
                    server.login(config['smtp_username'], config['smtp_password'])
                server.send_message(msg)
        logger.info(f"Reset email sent to {to_email}")
        return True
    except Exception as exc:
        logger.error(f"Failed to send reset email to {to_email}: {exc}")
        return False


def _rate_limit_exceeded(email: str) -> bool:
    """Return True if the email has exceeded the rate limit (max 3/hour).

    On each call, prunes entries older than the window and increments the
    counter for the current window.
    """
    db = current_app.db
    email_hash = _hash_email(email)
    now = datetime.now(timezone.utc)
    window_start = now - timedelta(hours=RESET_RATE_LIMIT_WINDOW_HOURS)

    # Prune stale entries outside the window
    db.execute(
        "DELETE FROM password_reset_rate_limit WHERE last_request_at < ?",
        (window_start.isoformat(),),
    )

    row = db.fetch_one(
        "SELECT * FROM password_reset_rate_limit WHERE email_hash = ?",
        (email_hash,),
    )

    if row is None:
        db.insert('password_reset_rate_limit', {
            'email_hash': email_hash,
            'request_count': 1,
            'first_request_at': now.isoformat(),
            'last_request_at': now.isoformat(),
        })
        return False

    count = int(row['request_count']) + 1
    db.update('password_reset_rate_limit', {
        'request_count': count,
        'last_request_at': now.isoformat(),
    }, 'email_hash = ?', (email_hash,))

    return count > RESET_RATE_LIMIT_MAX


def _generate_reset_token(user_id: int) -> str:
    """Generate a single-use JWT reset token (1h expiry) and store its hash."""
    now = datetime.now(timezone.utc)
    payload = {
        'user_id': user_id,
        'type': 'password_reset',
        'exp': now + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS),
        'iat': now,
        'jti': __import__('secrets').token_hex(16),
    }
    secret_key = current_app.config.get('SECRET_KEY') or \
        __import__('os').environ.get('WEBGUI_SECRET_KEY', '')
    token = jwt.encode(payload, secret_key, algorithm='HS256')

    # Store the hashed token for single-use enforcement
    db = current_app.db
    db.insert('password_reset_tokens', {
        'user_id': user_id,
        'token_hash': _hash_token(token),
        'expires_at': payload['exp'].isoformat(),
        'used_at': None,
    })

    return token


def _validate_reset_token(token: str) -> dict | None:
    """Validate a reset token: signature, expiry, single-use, constant-time compare.

    Returns the payload dict if valid, None otherwise.
    """
    secret_key = current_app.config.get('SECRET_KEY') or \
        __import__('os').environ.get('WEBGUI_SECRET_KEY', '')

    try:
        payload = jwt.decode(token, secret_key, algorithms=['HS256'])
    except jwt.ExpiredSignatureError:
        logger.warning("Reset token expired")
        return None
    except jwt.InvalidTokenError as exc:
        logger.error(f"Reset token invalid: {exc}")
        return None

    if payload.get('type') != 'password_reset':
        logger.warning("Reset token has wrong type")
        return None

    token_hash = _hash_token(token)
    db = current_app.db
    row = db.fetch_one(
        "SELECT * FROM password_reset_tokens WHERE token_hash = ? AND user_id = ? AND used_at IS NULL",
        (token_hash, payload['user_id']),
    )
    if row is None:
        logger.warning("Reset token not found or already used")
        return None

    # Constant-time comparison to avoid timing attacks on the stored hash
    if not hmac.compare_digest(row['token_hash'], token_hash):
        logger.warning("Reset token hash mismatch (constant-time check failed)")
        return None

    expires_at = row['expires_at']
    if isinstance(expires_at, str):
        expires_at = datetime.fromisoformat(expires_at)
    if expires_at.tzinfo is None:
        expires_at = expires_at.replace(tzinfo=timezone.utc)
    if expires_at <= datetime.now(timezone.utc):
        logger.warning("Reset token expired (stored expiry check)")
        return None

    return payload


def _invalidate_reset_token(token: str) -> None:
    """Mark a reset token as used (single-use enforcement)."""
    token_hash = _hash_token(token)
    db = current_app.db
    db.update('password_reset_tokens', {'used_at': datetime.now(timezone.utc).isoformat()},
              'token_hash = ?', (token_hash,))


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # Validar contra DB
        db = current_app.db
        query = (
            "SELECT id, username, password_hash, role "
            "FROM users WHERE username = ? AND is_active = 1"
        )
        user = db.fetch_one(query, (username,))

        if user:
            # Verificar password con Argon2id
            auth = current_app.auth
            if auth.verify_password(password, user['password_hash']):
                # Actualizar last_login
                db.update('users', {'last_login': datetime.now().isoformat()},
                         'id = ?', (user['id'],))

                # Guardar en sesión
                session['user_id'] = user['id']
                session['username'] = user['username']
                session['role'] = user['role']

                flash(f'Bienvenido, {user["username"]}!', 'success')

                # Redirect a next o dashboard
                next_url = request.args.get('next')
                if next_url:
                    return redirect(next_url)
                return redirect(url_for('index'))

        flash('Usuario o contraseña inválidos', 'error')

    return render_template('login.html')


@auth_bp.route('/logout')
def logout():
    """Cerrar sesión"""
    session.clear()
    flash('Sesión cerrada', 'info')
    return redirect(url_for('auth.login'))


@auth_bp.route('/setup', methods=['GET', 'POST'])
def setup():
    """Setup wizard inicial"""
    db = current_app.db
    auth = current_app.auth

    # Verificar si setup ya fue completado
    config = db.fetch_one("SELECT value FROM system_config WHERE key = 'setup_completed'")
    if config and config['value'] == 'true':
        flash('El setup ya fue completado', 'warning')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        username = request.form.get('username', '')
        email = request.form.get('email', '')
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validaciones
        errors = []

        if len(username) < 3:
            errors.append('Usuario debe tener al menos 3 caracteres')

        if password != password_confirm:
            errors.append('Las contraseñas no coinciden')

        # Validar fortaleza de contraseña
        is_strong, pwd_errors = auth.validate_password_strength(password)
        if not is_strong:
            errors.extend(pwd_errors)

        # Verificar que no exista el usuario
        existing = db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            errors.append('El usuario ya existe')

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('setup.html')

        # Crear usuario admin
        password_hash = auth.hash_password(password)

        db.insert('users', {
            'username': username,
            'email': email or '',
            'password_hash': password_hash,
            'role': 'admin'
        })

        # Marcar setup como completado
        db.update('system_config', {'value': 'true'}, "key = 'setup_completed'")

        flash('Setup completado exitosamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('setup.html')


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    """Recuperar contraseña — envía email con token JWT de un solo uso."""
    if request.method == 'POST':
        email = (request.form.get('email') or '').strip().lower()
        if not email:
            flash('Ingresa tu correo electrónico', 'error')
            return render_template('auth/forgot_password.html')

        db = current_app.db

        # Rate limiting: max 3 requests/hour per email
        if _rate_limit_exceeded(email):
            flash('Demasiadas solicitudes. Intenta nuevamente en una hora.', 'error')
            return render_template('auth/forgot_password.html')

        # Buscar usuario por email (existencia se no revela para evitar enumeración)
        user = db.fetch_one(
            "SELECT id, username, email FROM users WHERE LOWER(email) = LOWER(?) AND is_active = 1",
            (email,),
        )

        reset_link = None
        if user:
            token = _generate_reset_token(user['id'])
            reset_link = url_for('auth.reset_password', token=token, _external=True)

            smtp_configured = _get_smtp_config() is not None
            if smtp_configured:
                sent = _send_reset_email(email, reset_link)
                if sent:
                    flash('Se ha enviado un enlace de restablecimiento a tu correo.', 'success')
                else:
                    # SMTP falló: mostrar token en UI (admin fallback)
                    flash('No se pudo enviar el correo. Usa este token para restablecer tu contraseña: '
                          f'{token}', 'warning')
            else:
                # Admin fallback: SMTP no configurado, mostrar token en UI
                flash('El correo SMTP no está configurado. Usa este token para restablecer tu contraseña: '
                      f'{token}', 'warning')
        else:
            # No revelar si el email existe o no (evitar enumeración de usuarios)
            flash('Si existe una cuenta activa con ese correo, recibirás las instrucciones de restablecimiento.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('auth/forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Restablecer contraseña con token de un solo uso."""
    # Validar token (firma, expiración, un solo uso, comparación constante)
    payload = _validate_reset_token(token)
    if payload is None:
        flash('El enlace de restablecimiento es inválido o ya expiró.', 'error')
        return redirect(url_for('auth.login'))

    user_id = payload['user_id']
    db = current_app.db

    if request.method == 'POST':
        new_password = request.form.get('password', '')
        confirm_password = request.form.get('password_confirm', '')

        if not new_password:
            flash('Ingresa una contraseña nueva', 'error')
            return render_template('auth/reset_password.html', token=token)

        if new_password != confirm_password:
            flash('Las contraseñas no coinciden', 'error')
            return render_template('auth/reset_password.html', token=token)

        is_strong, pwd_errors = current_app.auth.validate_password_strength(new_password)
        if not is_strong:
            for error in pwd_errors:
                flash(error, 'error')
            return render_template('auth/reset_password.html', token=token)

        # Actualizar contraseña del usuario
        password_hash = current_app.auth.hash_password(new_password)
        db.update('users', {'password_hash': password_hash},
                  'id = ?', (user_id,))

        # Invalidar el token (un solo uso)
        _invalidate_reset_token(token)

        flash('Tu contraseña se ha actualizado correctamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)
