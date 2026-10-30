"""
Middleware de Autenticación - JWT Validation + Personal Access Tokens (MYK-407)
"""

import hashlib
import sqlite3
import threading
import time
from collections import defaultdict
from functools import wraps

from flask import current_app, flash, g, jsonify, redirect, request, session, url_for

from ..permissions import has_permission

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


def _scope_for_perms(perms: tuple[str, ...]) -> str | None:
    """Mapa permisos al scope de PAT requerido.
    Cualquier permiso :write requiere scope 'write'; :read requiere 'read'.
    """
    if any(p.endswith(":write") for p in perms):
        return "write"
    if any(p.endswith(":read") for p in perms):
        return "read"
    return None


def _verify_pat(token: str, required_scope: str | None = None) -> dict | None:
    """Verifica un Personal Access Token contra la tabla api_tokens.

    Si la app no expone ``db`` o la tabla api_tokens no existe (migracion 012
    aun no aplicada, p.ej. tests que montan un subconjunto de migraciones) no
    hay PATs validos: falla cerrado y devuelve None para que api_require
    responda 401 en vez de 500/AttributeError.
    """
    from ..api_tokens import ApiTokenService

    db = getattr(current_app, "db", None)
    if db is None:
        return None
    service = ApiTokenService(db)
    try:
        record = service.verify_token(token)
    except sqlite3.OperationalError:
        return None
    if record is None:
        return None
    if required_scope:
        token_scopes = (record.get("scopes") or "").split(" ")
        if required_scope not in token_scopes:
            return None
    return record


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
            auth_header = request.headers.get("Authorization")

            if auth_header:
                try:
                    scheme, token = auth_header.split()
                except ValueError:
                    return jsonify({"error": "Invalid authorization format"}), 401

                if scheme.lower() != "bearer":
                    return jsonify({"error": "Bearer scheme required"}), 401

                # Rate limiting basico por token (usa el token completo como
                # clave: truncar a 16 colisiona entre JWTs que comparten el
                # header base64 y agotaba el bucket entre tests de la sesion).
                client_key = f"{request.remote_addr}:{token}"
                if not _rate_limit_allow(client_key):
                    return jsonify({"error": "rate limit exceeded"}), 429

                auth_instance = getattr(current_app, "auth", None)
                if auth_instance is None:
                    return jsonify({"error": "Authentication is not configured"}), 401

                # Bearer JWT
                payload = auth_instance.verify_access_token(token)
                if payload is not None:
                    g.api_user = payload
                    role = payload.get("role")
                    if perms and not all(has_permission(role, perm) for perm in perms):
                        return jsonify({"error": "Insufficient permissions"}), 403
                    return f(*args, **kwargs)

                # Personal Access Token (PAT)
                required_scope = _scope_for_perms(perms)
                pat_record = _verify_pat(token, required_scope=required_scope)
                if pat_record is not None:
                    g.api_token = pat_record
                    g.api_user = {
                        "role": "pat",
                        "scopes": pat_record.get("scopes", ""),
                    }
                    return f(*args, **kwargs)

                # Bearer invalido tras JWT y PAT.
                # Si el token es una PAT real (existe en api_tokens, aunque
                # este revocada/expirada/sin-scope) se aplica 401 sin caer a
                # sesion. Si es basura/no reconocida (no hay fila), se cae a
                # sesion WebGUI: una sesion valida autentica aunque el header
                # basura este presente (no rompe al navegador del WebGUI).
                token_hash = hashlib.sha256(token.encode()).hexdigest()
                pat_es_real = False
                db = getattr(current_app, "db", None)
                if db is not None:
                    try:
                        pat_es_real = (
                            db.fetch_one(
                                "SELECT 1 FROM api_tokens WHERE token_hash = ?",
                                (token_hash,),
                            )
                            is not None
                        )
                    except sqlite3.OperationalError:
                        pat_es_real = False

                if pat_es_real:
                    return jsonify({"error": "Invalid or expired token"}), 401

                if "user_id" in session:
                    role = session.get("role")
                    if perms and not all(has_permission(role, perm) for perm in perms):
                        return jsonify({"error": "Insufficient permissions"}), 403
                    return f(*args, **kwargs)
                return jsonify({"error": "Invalid or expired token"}), 401

            # Sin header Bearer: usar sesion WebGUI
            if "user_id" not in session:
                return jsonify({"error": "Authorization header required"}), 401

            role = session.get("role")
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
