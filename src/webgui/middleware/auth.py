"""
Middleware de Autenticación - JWT Validation
"""

from functools import wraps

from flask import current_app, flash, g, jsonify, redirect, request, session, url_for


def login_required(f):
    """
    Decorador para requerir login en rutas
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder", "warning")
            return redirect(url_for("auth.login", next=request.url))
        return f(*args, **kwargs)

    return decorated_function


def admin_required(f):
    """
    Decorador para requerir rol de administrador
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder", "warning")
            return redirect(url_for("auth.login", next=request.url))

        if session.get("role") != "admin":
            flash("No tienes permisos de administrador", "error")
            return redirect(url_for("index"))

        return f(*args, **kwargs)

    return decorated_function


def api_auth_required(f):
    """
    Decorador para APIs que requieren autenticación JWT (MYK-443).

    Acepta cualquiera de las dos credenciales:
    - Sesión WebGUI activa (``user_id`` en session) — llamadas del propio
      WebGUI desde el browser (fetch same-origin con cookie de sesión).
    - Bearer JWT válido firmado con el mismo secreto que el login
      (``Auth.verify_access_token``, payload ``type == "access"``).
    Todo lo demás responde 401. Fail-closed si la app no tiene ``auth``.
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # 1) Sesión WebGUI (browser fetch del propio dashboard)
        if "user_id" in session:
            return f(*args, **kwargs)

        # 2) Bearer JWT (consumidores externos de la API)
        auth_header = request.headers.get("Authorization")

        if not auth_header:
            return jsonify({"error": "Authorization header required"}), 401

        # Extraer token
        try:
            scheme, token = auth_header.split()
            if scheme.lower() != "bearer":
                return jsonify({"error": "Bearer scheme required"}), 401
        except ValueError:
            return jsonify({"error": "Invalid authorization format"}), 401

        auth_instance = getattr(current_app, "auth", None)
        if auth_instance is None:
            return jsonify({"error": "Authentication is not configured"}), 401

        payload = auth_instance.verify_access_token(token)
        if payload is None:
            return jsonify({"error": "Invalid or expired token"}), 401

        g.api_user = payload
        return f(*args, **kwargs)

    return decorated_function
