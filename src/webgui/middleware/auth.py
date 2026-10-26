"""
Middleware de Autenticación - JWT Validation + API Tokens (MYK-407)
"""

import threading
import time
from collections import defaultdict
from functools import wraps

from flask import flash, g, jsonify, redirect, request, session, url_for

# Rate limiting basico in-memory para endpoints con Bearer (MYK-407):
# 60 requests/minuto por token. Simple y suficiente para un collector LAN.
RATE_LIMIT_MAX_REQUESTS = 60
RATE_LIMIT_WINDOW_SECONDS = 60

_rate_limit_store: dict[str, list[float]] = defaultdict(list)
_rate_limit_lock = threading.Lock()


def _rate_limit_allow(key: str) -> bool:
    """Sliding window in-memory. Devuelve True si la request pasa."""
    now = time.time()
    with _rate_limit_lock:
        _rate_limit_store[key] = [
            t for t in _rate_limit_store[key] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        if len(_rate_limit_store[key]) >= RATE_LIMIT_MAX_REQUESTS:
            return False
        _rate_limit_store[key].append(now)
        return True


def reset_rate_limit_store():
    """Reset rate limit store for testing."""
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


def _extract_bearer_token():
    """Extrae el token del header Authorization. Devuelve (ok, token, error_response)."""
    auth_header = request.headers.get("Authorization")
    if not auth_header:
        return False, None, (jsonify({"error": "Authorization header required"}), 401)
    try:
        scheme, token = auth_header.split()
        if scheme.lower() != "bearer":
            return False, None, (jsonify({"error": "Bearer scheme required"}), 401)
    except ValueError:
        return False, None, (jsonify({"error": "Invalid authorization format"}), 401)
    return True, token, None


def api_auth_required(f=None, required_scope: str | None = None):
    """
    Decorador para APIs que requieren autenticación Bearer.

    Acepta dos tipos de token (MYK-407):
    1. Personal Access Token (PAT): verificado contra api_tokens (hash, scope, revocacion).
    2. JWT de sesion (fallback): firma verificada con Auth.verify_access_token.

    `required_scope` aplica solo a PATs; los JWT de sesion conservan acceso completo.
    Soporta ambos usos: @api_auth_required y @api_auth_required(required_scope="read").
    """

    def decorator(fn):
        @wraps(fn)
        def decorated_function(*args, **kwargs):
            ok, token, error = _extract_bearer_token()
            if not ok:
                return error

            # Rate limit basico por token
            client_key = f"{request.remote_addr}:{token[:16]}"
            if not _rate_limit_allow(client_key):
                return jsonify({"error": "rate limit exceeded"}), 429

            # 1. Personal Access Token
            from flask import current_app

            from ..api_tokens import ApiTokenService

            service = ApiTokenService(current_app.db)
            record = service.verify_token(token, required_scope=required_scope)
            if record:
                g.api_token = record
                return fn(*args, **kwargs)

            # 2. JWT de sesion (fallback)
            payload = current_app.auth.verify_access_token(token)
            if payload:
                g.jwt_payload = payload
                return fn(*args, **kwargs)

            return jsonify({"error": "Token inválido o revocado"}), 401

        return decorated_function

    if f is not None:
        # Uso directo: @api_auth_required
        return decorator(f)
    return decorator
