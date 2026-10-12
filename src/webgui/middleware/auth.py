"""
Middleware de Autenticación - JWT Validation
"""

from functools import wraps

from flask import flash, jsonify, redirect, request, session, url_for


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
    Decorador para APIs que requieren autenticación JWT
    """

    @wraps(f)
    def decorated_function(*args, **kwargs):
        # Verificar header Authorization
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

        # TODO: Validar token con Auth class
        # Por ahora, pasar al siguiente
        return f(*args, **kwargs)

    return decorated_function
