"""
Middleware de Autenticación - JWT Validation + API Tokens (MYK-407)
"""

import sqlite3
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import current_app, flash, g, jsonify, redirect, request, session, url_for

from ..api_tokens import ApiTokenService
from ..permissions import has_permission

# Rate limiting basico in-memory para endpoints con Bearer (MYK-407):
# sliding window por token, default 60 req/min. In-memory por worker:
# suficiente para un collector LAN; para multi-worker usar Redis si crece.
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()


def _rate_limit_allow(key: str, max_requests: int | None = None) -> bool:
    """Sliding window in-memory. Devuelve True si la request pasa."""
    limit = max_requests if max_requests is not None else RATE_LIMIT_MAX_REQUESTS
    now = time.time()
    with _rate_limit_lock:
        _rate_limit_store[key] = [
            t for t in _rate_limit_store[key] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(_rate_limit_store[key]) >= limit:
            return False
        _rate_limit_store[key].append(now)
        return True


def reset_rate_limit_store():
    """Limpia el store de rate limit (tests)."""
    with _rate_limit_lock:
        _rate_limit_store.clear()


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


def api_require(*perms, required_scope: str | None = None):
    """
    Decorador para APIs con JWT y permisos RBAC (ADR-001, MYK-413).

    Acepta cualquiera de las tres credenciales:
    - Sesión WebGUI activa (``user_id`` en session) — llamadas del propio
      WebGUI desde el browser (fetch same-origin con cookie de sesión).
    - Bearer Personal Access Token (PAT, MYK-407): verificado contra
      ``api_tokens`` (hash SHA256, scopes, revocacion, expiracion). El rol
      del dueno sigue mandando para los permisos RBAC; ``required_scope``
      restringe ademas el token (read/write).
    - Bearer JWT válido firmado con el mismo secreto que el login
      (``Auth.verify_access_token``, payload ``type == "access"``).

    Con permisos pedidos, exige TODOS (AND) para el rol de la credencial
    (``session["role"]``, rol del dueno del PAT o claim ``role`` del
    payload); si no, 403 JSON. Sin credencial válida -> 401. Fail-closed si
    la app no tiene ``auth``. El payload verificado queda en ``g.api_user``
    (solo via JWT) y el registro del PAT en ``g.api_token`` (solo via PAT).
    Los Bearer van rate-limited (429).
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

            # 2) Bearer: PAT (MYK-407) o JWT de sesion
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

            # Rate limit basico por token (MYK-407)
            configured_limit = current_app.config.get("API_RATE_LIMIT_MAX_REQUESTS")
            client_key = f"{request.remote_addr}:{token[:16]}"
            if not _rate_limit_allow(client_key, configured_limit):
                return jsonify({"error": "rate limit exceeded"}), 429

            # 2a) Personal Access Token. Si la tabla no existe aun (deploy
            # sin migracion 009), degrada a JWT sin fallar la request.
            db = getattr(current_app, "db", None)
            if db is not None:
                try:
                    pat = ApiTokenService(db).verify_token(token)
                except sqlite3.OperationalError:
                    pat = None
                if pat is not None:
                    scopes = (pat["scopes"] or "").split()
                    if required_scope and required_scope not in scopes:
                        return jsonify({"error": "Insufficient permissions"}), 403

                    g.api_token = pat
                    if perms:
                        owner = db.fetch_one(
                            "SELECT role FROM users WHERE id = ?", (pat["user_id"],)
                        )
                        role = owner["role"] if owner else None
                        if not all(has_permission(role, perm) for perm in perms):
                            return jsonify({"error": "Insufficient permissions"}), 403
                    return f(*args, **kwargs)

            # 2b) JWT de sesion (consumidores externos de la API)
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


def api_auth_required(f=None, required_scope: str | None = None):
    """
    DEPRECATED (MYK-413): usa ``api_require()``. Alias de ``api_require()``
    sin permisos (solo autenticacion). Se elimina cuando ninguna ruta lo
    referencie (migracion de usos en el issue de aplicacion por blueprint).

    MYK-407: admite ``@api_auth_required(required_scope="read"|"write")``
    para exigir scope a los PATs (JWT/sesion conservan acceso completo).
    """

    if f is not None:
        return api_require(required_scope=required_scope)(f)
    return api_require(required_scope=required_scope)
