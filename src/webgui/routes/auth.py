"""
Auth Routes - Login, Logout, Setup, Password Reset
"""

import time
from collections import defaultdict
from datetime import datetime, timedelta
from threading import Lock

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..mail import Mailer

auth_bp = Blueprint("auth", __name__)

RESET_TOKEN_EXPIRY_HOURS = 1

# Rate limiting: max 3 requests per hour per email
RATE_LIMIT_WINDOW_SECONDS = 3600
RATE_LIMIT_MAX_REQUESTS = 3

# In-memory rate limiter (use Redis in production for multi-worker deployments)
_rate_limit_store = defaultdict(list)
_rate_limit_lock = Lock()


def _check_rate_limit(email: str) -> tuple[bool, int]:
    """
    Check if email has exceeded rate limit.
    Returns (allowed, remaining_requests)
    """
    now = time.time()
    key = email.lower().strip()
    with _rate_limit_lock:
        # Clean old entries
        _rate_limit_store[key] = [
            t for t in _rate_limit_store[key] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]

        if len(_rate_limit_store[key]) >= RATE_LIMIT_MAX_REQUESTS:
            return False, 0

        _rate_limit_store[key].append(now)
        remaining = RATE_LIMIT_MAX_REQUESTS - len(_rate_limit_store[key])
        return True, remaining


def reset_rate_limit_store():
    """Reset rate limit store for testing"""
    global _rate_limit_store
    with _rate_limit_lock:
        _rate_limit_store.clear()


@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    """Página de login"""
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")

        # Validar contra DB
        db = current_app.db
        user = db.fetch_one(
            "SELECT id, username, password_hash, role, email FROM users WHERE username = ? AND is_active = 1",
            (username,),
        )

        if user:
            # Verificar password con Argon2id
            auth = current_app.auth
            if auth.verify_password(password, user["password_hash"]):
                # Actualizar last_login
                db.update(
                    "users", {"last_login": datetime.now().isoformat()}, "id = ?", (user["id"],)
                )

                # Guardar en sesión
                session["user_id"] = user["id"]
                session["username"] = user["username"]
                session["role"] = user["role"]
                session["email"] = user["email"]

                flash(f"Bienvenido, {user['username']}!", "success")

                # Redirect a next o dashboard
                next_url = request.args.get("next")
                if next_url:
                    return redirect(next_url)
                return redirect(url_for("index"))

        flash("Usuario o contraseña inválidos", "error")

    return render_template("login.html")


@auth_bp.route("/logout")
def logout():
    """Cerrar sesión"""
    session.clear()
    flash("Sesión cerrada", "info")
    return redirect(url_for("auth.login"))


@auth_bp.route("/setup", methods=["GET", "POST"])
def setup():
    """Setup wizard inicial"""
    db = current_app.db
    auth = current_app.auth

    # Verificar si setup ya fue completado
    config = db.fetch_one("SELECT value FROM system_config WHERE key = 'setup_completed'")
    if config and config["value"] == "true":
        flash("El setup ya fue completado", "warning")
        return redirect(url_for("auth.login"))

    if request.method == "POST":
        username = request.form.get("username", "")
        email = request.form.get("email", "")
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        # Validaciones
        errors = []

        if len(username) < 3:
            errors.append("Usuario debe tener al menos 3 caracteres")

        if password != password_confirm:
            errors.append("Las contraseñas no coinciden")

        # Validar fortaleza de contraseña
        is_strong, pwd_errors = auth.validate_password_strength(password)
        if not is_strong:
            errors.extend(pwd_errors)

        # Verificar que no exista el usuario
        existing = db.fetch_one("SELECT id FROM users WHERE username = ?", (username,))
        if existing:
            errors.append("El usuario ya existe")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("setup.html")

        # Crear usuario admin
        password_hash = auth.hash_password(password)

        db.insert(
            "users",
            {
                "username": username,
                "email": email or "",
                "password_hash": password_hash,
                "role": "admin",
            },
        )

        # Marcar setup como completado
        db.update("system_config", {"value": "true"}, "key = 'setup_completed'")

        flash("Setup completado exitosamente. Ahora puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("setup.html")


@auth_bp.route("/forgot-password", methods=["GET", "POST"])
def forgot_password():
    """Solicitar reset de contraseña por email"""
    if request.method == "POST":
        email = request.form.get("email", "").strip().lower()

        if not email:
            flash("Por favor ingresa tu email", "error")
            return render_template("forgot_password.html")

        # Rate limiting (by email)
        allowed, remaining = _check_rate_limit(email)
        if not allowed:
            flash("Demasiadas solicitudes. Intenta de nuevo en una hora.", "error")
            return render_template("forgot_password.html"), 429

        if not email:
            flash("Por favor ingresa tu email", "error")
            return render_template("forgot_password.html")

        db = current_app.db
        auth = current_app.auth

        # Buscar usuario por email
        user = db.fetch_one(
            "SELECT id, username, email FROM users WHERE email = ? AND is_active = 1", (email,)
        )

        if user:
            # Generar token de reset
            token, token_hash = auth.generate_reset_token_and_hash()
            expires_at = (datetime.now() + timedelta(hours=RESET_TOKEN_EXPIRY_HOURS)).isoformat()

            # Invalidar tokens anteriores no usados
            db.execute(
                "UPDATE password_reset_tokens SET used_at = CURRENT_TIMESTAMP "
                "WHERE user_id = ? AND used_at IS NULL",
                (user["id"],),
            )

            # Guardar nuevo token (hashed)
            db.insert(
                "password_reset_tokens",
                {
                    "user_id": user["id"],
                    "token_hash": token_hash,
                    "expires_at": expires_at,
                },
            )

            # Intentar enviar email si SMTP está configurado
            smtp_config = db.fetch_all(
                "SELECT key, value FROM system_config WHERE key LIKE 'smtp_%'"
            )
            smtp_dict = {row["key"]: row["value"] for row in smtp_config}

            mailer = Mailer.from_config(smtp_dict)
            if mailer:
                reset_url = url_for("auth.reset_password", token=token, _external=True)
                try:
                    mailer.send_password_reset(
                        user["email"], user["username"], reset_url, RESET_TOKEN_EXPIRY_HOURS * 60
                    )
                    flash(
                        "Se ha enviado un email con instrucciones para restablecer tu contraseña",
                        "success",
                    )
                except Exception as e:
                    logger = current_app.logger
                    logger.error(f"Error enviando email de reset: {e}")
                    flash(
                        "No se pudo enviar el email. Contacta al administrador para reset manual.",
                        "warning",
                    )
            else:
                # Sin SMTP configurado - mostrar token en pantalla (solo para desarrollo/admin)
                reset_url = url_for("auth.reset_password", token=token, _external=True)
                flash(
                    f"SMTP no configurado. Tu enlace de reset: {reset_url} (vence en {RESET_TOKEN_EXPIRY_HOURS}h)",
                    "info",
                )

        else:
            # Por seguridad, siempre mostrar éxito aunque el email no exista
            flash(
                "Si el email existe en el sistema, recibirás instrucciones para restablecer tu contraseña",
                "success",
            )

        return redirect(url_for("auth.login"))

    return render_template("forgot_password.html")


@auth_bp.route("/reset-password/<token>", methods=["GET", "POST"])
def reset_password(token: str):
    """Formulario para nueva contraseña usando token"""
    db = current_app.db
    auth = current_app.auth

    # Validar token: buscar hash y verificar expiración
    token_hash = auth.hash_reset_token(token)
    reset_token = db.fetch_one(
        "SELECT id, user_id, expires_at, used_at FROM password_reset_tokens WHERE token_hash = ?",
        (token_hash,),
    )

    if not reset_token:
        flash("Token inválido o expirado", "error")
        return redirect(url_for("auth.forgot_password"))

    if reset_token["used_at"]:
        flash("Este token ya fue utilizado", "error")
        return redirect(url_for("auth.forgot_password"))

    if datetime.fromisoformat(reset_token["expires_at"]) < datetime.now():
        flash("Token expirado. Solicita uno nuevo.", "error")
        return redirect(url_for("auth.forgot_password"))

    if request.method == "POST":
        password = request.form.get("password", "")
        password_confirm = request.form.get("password_confirm", "")

        if password != password_confirm:
            flash("Las contraseñas no coinciden", "error")
            return render_template("reset_password.html", token=token)

        # Validar fortaleza
        is_strong, pwd_errors = auth.validate_password_strength(password)
        if not is_strong:
            for error in pwd_errors:
                flash(error, "error")
            return render_template("reset_password.html", token=token)

        # Actualizar contraseña
        password_hash = auth.hash_password(password)
        db.update(
            "users",
            {"password_hash": password_hash, "updated_at": datetime.now().isoformat()},
            "id = ?",
            (reset_token["user_id"],),
        )

        # Marcar token como usado
        db.update(
            "password_reset_tokens",
            {"used_at": datetime.now().isoformat()},
            "id = ?",
            (reset_token["id"],),
        )

        flash("Contraseña actualizada exitosamente. Ya puedes iniciar sesión.", "success")
        return redirect(url_for("auth.login"))

    return render_template("reset_password.html", token=token)


# API endpoints for programmatic access
@auth_bp.route("/api/forgot-password", methods=["POST"])
def api_forgot_password():
    """API: Solicitar reset de contraseña por email"""
    # Rate limiting: max 3 requests per hour per IP
    client_ip = request.remote_addr
    allowed, remaining = _check_rate_limit(client_ip)
    if not allowed:
        return jsonify(
            {
                "success": False,
                "message": "Demasiadas solicitudes. Intenta de nuevo en una hora.",
                "retry_after": RATE_LIMIT_WINDOW_SECONDS,
            }
        ), 429

    data = request.get_json() or {}
    email = data.get("email", "").strip().lower()

    if not email:
        return jsonify({"success": False, "message": "Email es requerido"}), 400

    db = current_app.db
    auth = current_app.auth

    # Buscar usuario por email
    user = db.fetch_one(
        "SELECT id, username, email FROM users WHERE email = ? AND is_active = 1", (email,)
    )

    # Siempre responder éxito para evitar enumeración
    if user:
        # Generar token de reset
        token, token_hash = auth.generate_reset_token_and_hash()

        # Expira en 1 hora
        expires_at = datetime.now() + timedelta(hours=1)

        # Guardar token en BD
        db.insert(
            "password_reset_tokens",
            {"user_id": user["id"], "token_hash": token_hash, "expires_at": expires_at.isoformat()},
        )

        # TODO: Enviar email
        logger = current_app.logger
        logger.info(f"API Password reset token for {user['username']} ({email}): {token}")

    return jsonify(
        {
            "success": True,
            "message": "Si el email existe, recibirás instrucciones para restablecer tu contraseña.",
        }
    )


@auth_bp.route("/api/reset-password", methods=["POST"])
def api_reset_password():
    """API: Restablecer contraseña con token"""
    # Rate limiting: max 3 requests per hour per IP
    client_ip = request.remote_addr
    allowed, remaining = _check_rate_limit(client_ip)
    if not allowed:
        return jsonify(
            {
                "success": False,
                "message": "Demasiadas solicitudes. Intenta de nuevo en una hora.",
                "retry_after": RATE_LIMIT_WINDOW_SECONDS,
            }
        ), 429

    data = request.get_json() or {}
    token = data.get("token", "")
    password = data.get("password", "")
    password_confirm = data.get("password_confirm", "")

    if not token or not password:
        return jsonify({"success": False, "message": "Token y contraseña son requeridos"}), 400

    if password != password_confirm:
        return jsonify({"success": False, "message": "Las contraseñas no coinciden"}), 400

    db = current_app.db
    auth = current_app.auth

    # Validar fortaleza de contraseña
    is_strong, pwd_errors = auth.validate_password_strength(password)
    if not is_strong:
        return jsonify({"success": False, "message": "Contraseña débil", "errors": pwd_errors}), 400

    # Verificar token
    token_hash = auth.hash_reset_token(token)

    reset_token = db.fetch_one(
        """SELECT prt.*, u.username, u.email
           FROM password_reset_tokens prt
           JOIN users u ON u.id = prt.user_id
           WHERE prt.token_hash = ? AND prt.used_at IS NULL""",
        (token_hash,),
    )

    if not reset_token:
        return jsonify({"success": False, "message": "Token inválido o ya utilizado"}), 400

    # Verificar expiración
    expires_at = datetime.fromisoformat(reset_token["expires_at"])
    if datetime.now() > expires_at:
        return jsonify({"success": False, "message": "El token ha expirado"}), 400

    # Actualizar contraseña
    password_hash = auth.hash_password(password)
    db.update(
        "users",
        {"password_hash": password_hash, "updated_at": datetime.now().isoformat()},
        "id = ?",
        (reset_token["user_id"],),
    )

    # Marcar token como usado
    db.update(
        "password_reset_tokens",
        {"used_at": datetime.now().isoformat()},
        "id = ?",
        (reset_token["id"],),
    )

    return jsonify({"success": True, "message": "Contraseña restablecida exitosamente"})
