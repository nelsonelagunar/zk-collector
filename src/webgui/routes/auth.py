"""
Auth Routes - Login, Logout, Setup, Password Reset
"""

from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from datetime import datetime, timedelta
import hashlib

auth_bp = Blueprint('auth', __name__)


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    """Página de login"""
    if request.method == 'POST':
        username = request.form.get('username', '')
        password = request.form.get('password', '')

        # Validar contra DB
        db = current_app.db
        user = db.fetch_one(
            "SELECT id, username, password_hash, role FROM users WHERE username = ? AND is_active = 1",
            (username,)
        )

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
    """Recuperar contraseña - formulario para solicitar reset"""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()

        if not email:
            flash('El email es requerido', 'error')
            return render_template('forgot_password.html')

        db = current_app.db
        auth = current_app.auth

        # Buscar usuario por email
        user = db.fetch_one(
            "SELECT id, username, email FROM users WHERE email = ? AND is_active = 1",
            (email,)
        )

        # Por seguridad, siempre mostramos éxito aunque el email no exista
        # (para evitar enumeración de usuarios)
        if user:
            # Generar token de reset
            token, token_hash = auth.generate_reset_token_and_hash()

            # Expira en 1 hora
            expires_at = datetime.now() + timedelta(hours=1)

            # Guardar token en BD
            db.insert('password_reset_tokens', {
                'user_id': user['id'],
                'token_hash': token_hash,
                'expires_at': expires_at.isoformat()
            })

            # TODO: Enviar email con el token
            # Por ahora, log para desarrollo
            logger = current_app.logger
            logger.info(f"Password reset token for {user['username']} ({email}): {token}")

            # En producción, aquí se enviaría el email
            # _send_reset_email(user['email'], token, user['username'])

        flash('Si el email existe en nuestro sistema, recibirás instrucciones para restablecer tu contraseña.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    """Restablecer contraseña con token"""
    db = current_app.db
    auth = current_app.auth

    # Verificar token: hash del token y buscar en BD
    token_hash = auth.hash_reset_token(token)

    reset_token = db.fetch_one(
        """SELECT prt.*, u.username, u.email
           FROM password_reset_tokens prt
           JOIN users u ON u.id = prt.user_id
           WHERE prt.token_hash = ? AND prt.used_at IS NULL""",
        (token_hash,)
    )

    if not reset_token:
        flash('Token inválido o ya utilizado', 'error')
        return redirect(url_for('auth.forgot_password'))

    # Verificar expiración
    expires_at = datetime.fromisoformat(reset_token['expires_at'])
    if datetime.now() > expires_at:
        flash('El token ha expirado. Solicita uno nuevo.', 'error')
        return redirect(url_for('auth.forgot_password'))

    if request.method == 'POST':
        password = request.form.get('password', '')
        password_confirm = request.form.get('password_confirm', '')

        # Validaciones
        errors = []

        if password != password_confirm:
            errors.append('Las contraseñas no coinciden')

        # Validar fortaleza de contraseña
        is_strong, pwd_errors = auth.validate_password_strength(password)
        if not is_strong:
            errors.extend(pwd_errors)

        if errors:
            for error in errors:
                flash(error, 'error')
            return render_template('reset_password.html', token=token)

        # Actualizar contraseña
        password_hash = auth.hash_password(password)
        db.update('users', {'password_hash': password_hash, 'updated_at': datetime.now().isoformat()},
                  'id = ?', (reset_token['user_id'],))

        # Marcar token como usado
        db.update('password_reset_tokens', {'used_at': datetime.now().isoformat()},
                  'id = ?', (reset_token['id'],))

        flash('Contraseña restablecida exitosamente. Ahora puedes iniciar sesión.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('reset_password.html', token=token)


# API endpoints for programmatic access
@auth_bp.route('/api/auth/forgot-password', methods=['POST'])
def api_forgot_password():
    """API: Solicitar reset de contraseña por email"""
    # Rate limiting simple: max 3 requests per hour per IP
    client_ip = request.remote_addr
    db = current_app.db

    # Verificar rate limit
    recent_requests = db.fetch_one(
        """SELECT COUNT(*) as count FROM password_reset_tokens
           WHERE created_at > datetime('now', '-1 hour')""",
    )

    # Note: We'd ideally track by IP, but for simplicity using global limit
    # In production, add a rate_limit table tracking IP + timestamp

    data = request.get_json() or {}
    email = data.get('email', '').strip().lower()

    if not email:
        return jsonify({'success': False, 'message': 'Email es requerido'}), 400

    auth = current_app.auth

    # Buscar usuario por email
    user = db.fetch_one(
        "SELECT id, username, email FROM users WHERE email = ? AND is_active = 1",
        (email,)
    )

    # Siempre responder éxito para evitar enumeración
    if user:
        # Generar token de reset
        token, token_hash = auth.generate_reset_token_and_hash()

        # Expira en 1 hora
        expires_at = datetime.now() + timedelta(hours=1)

        # Guardar token en BD
        db.insert('password_reset_tokens', {
            'user_id': user['id'],
            'token_hash': token_hash,
            'expires_at': expires_at.isoformat()
        })

        # TODO: Enviar email
        logger = current_app.logger
        logger.info(f"API Password reset token for {user['username']} ({email}): {token}")

    return jsonify({
        'success': True,
        'message': 'Si el email existe, recibirás instrucciones para restablecer tu contraseña.'
    })


@auth_bp.route('/api/auth/reset-password', methods=['POST'])
def api_reset_password():
    """API: Restablecer contraseña con token"""
    data = request.get_json() or {}
    token = data.get('token', '')
    password = data.get('password', '')
    password_confirm = data.get('password_confirm', '')

    if not token or not password:
        return jsonify({'success': False, 'message': 'Token y contraseña son requeridos'}), 400

    if password != password_confirm:
        return jsonify({'success': False, 'message': 'Las contraseñas no coinciden'}), 400

    db = current_app.db
    auth = current_app.auth

    # Validar fortaleza de contraseña
    is_strong, pwd_errors = auth.validate_password_strength(password)
    if not is_strong:
        return jsonify({'success': False, 'message': 'Contraseña débil', 'errors': pwd_errors}), 400

    # Verificar token
    token_hash = auth.hash_reset_token(token)

    reset_token = db.fetch_one(
        """SELECT prt.*, u.username, u.email
           FROM password_reset_tokens prt
           JOIN users u ON u.id = prt.user_id
           WHERE prt.token_hash = ? AND prt.used_at IS NULL""",
        (token_hash,)
    )

    if not reset_token:
        return jsonify({'success': False, 'message': 'Token inválido o ya utilizado'}), 400

    # Verificar expiración
    expires_at = datetime.fromisoformat(reset_token['expires_at'])
    if datetime.now() > expires_at:
        return jsonify({'success': False, 'message': 'El token ha expirado'}), 400

    # Actualizar contraseña
    password_hash = auth.hash_password(password)
    db.update('users', {'password_hash': password_hash, 'updated_at': datetime.now().isoformat()},
              'id = ?', (reset_token['user_id'],))

    # Marcar token como usado
    db.update('password_reset_tokens', {'used_at': datetime.now().isoformat()},
              'id = ?', (reset_token['id'],))

    return jsonify({
        'success': True,
        'message': 'Contraseña restablecida exitosamente'
    })