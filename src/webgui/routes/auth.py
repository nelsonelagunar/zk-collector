"""
Auth Routes - Login, Logout, Setup
"""

from datetime import datetime

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
    """Recuperar contraseña"""
    if request.method == 'POST':
        request.form.get('email', '')

        # TODO: Implementar recovery con email
        # Por ahora, solo mostrar mensaje
        flash('La recuperación por email estará disponible próximamente', 'info')
        return redirect(url_for('auth.login'))

    return render_template('forgot_password.html')
