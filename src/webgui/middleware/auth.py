"""
Middleware de Autenticación - JWT Validation
"""

from functools import wraps

from flask import current_app, flash, g, jsonify, redirect, request, session, url_for

from ..permissions import has_permission


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
    Decorador para requerir rol de administrador.

    DEPRECATED (ADR-001, MYK-413): usar ``require("users:manage")`` o
    ``require("settings:manage")``. Se elimina cuando ninguna ruta lo referencie
    (migracion de usos en el issue de aplicacion por blueprint).
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


def require(*perms):
    """
    Decorador para rutas UI con sesion y permisos RBAC (ADR-001, MYK-413).

    Verifica sesion como ``login_required`` y que ``session["role"]`` tenga TODOS
    los permisos pedidos (semantica AND, ``has_permission``; roles desconocidos
    deniegan). Falta de sesion -> flash + redirect al login; falta de permiso ->
    flash + redirect a ``/``.
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Debes iniciar sesión para acceder", "warning")
                return redirect(url_for("auth.login", next=request.url))

            role = session.get("role")
            for perm in perms:
                if not has_permission(role, perm):
                    flash("No tienes permisos para acceder a esta sección", "error")
                    return redirect("/")

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def api_require(*perms):
    """
    Decorador para APIs con JWT y permisos RBAC (ADR-001, MYK-413).

    Acepta cualquiera de las dos credenciales:
    - Sesión WebGUI activa (``user_id`` en session) — llamadas del propio
      WebGUI desde el browser (fetch same-origin con cookie de sesión).
    - Bearer JWT válido firmado con el mismo secreto que el login
      (``Auth.verify_access_token``, payload ``type == "access"``).

    Con permisos pedidos, exige TODOS (AND) para el rol de la credencial
    (``session["role"]`` o claim ``role`` del payload); si no, 403 JSON.
    Sin credencial válida -> 401. Fail-closed si la app no tiene ``auth``.
    El payload verificado queda en ``g.api_user`` (solo via JWT).
    """

    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            # 1) Sesión WebGUI (browser fetch del propio dashboard)
            if "user_id" in session:
                role = session.get("role")
                if perms and not all(has_permission(role, perm) for perm in perms):
                    return jsonify({"error": "Insufficient permissions"}), 403
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

            role = payload.get("role")
            if perms and not all(has_permission(role, perm) for perm in perms):
                return jsonify({"error": "Insufficient permissions"}), 403

            return f(*args, **kwargs)

        return decorated_function

    return decorator


def api_auth_required(f):
    """
    DEPRECATED (MYK-413): usa ``api_require()``. Alias de ``api_require()``
    sin permisos (solo autenticacion). Se elimina cuando ninguna ruta lo
    referencie (migracion de usos en el issue de aplicacion por blueprint).
    """

    return api_require()(f)
