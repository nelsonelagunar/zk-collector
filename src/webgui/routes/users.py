"""
Users API Routes - CRUD de usuarios WebGUI (MYK-415, ADR-001).

Blueprint /api/users con api_require("users:manage") (MYK-413): acepta
sesion WebGUI (fetch same-origin) o Bearer JWT verificado. Paridad de
reglas con la UI /users (MYK-416):

* rol validado contra ALLOWED_ROLES en todo write path (catalogo cerrado
  ADR-001; SQLite no soporta ADD CONSTRAINT -> validacion en capa app);
* password con Auth.hash_password + Auth.validate_password_strength;
* DELETE es soft (is_active=0): el row nunca se borra (auditoria/ FKs);
* jamas degradar/desactivar al ultimo admin activo (PATCH y DELETE);
* jamas desactivar la cuenta del caller (identidad por sesion o claim
  user_id del JWT).

Contrato: docs/openapi.yaml (paths /api/users, schemas User/UserInput/
UserPatch, respuestas 401/403). La semantica de cambio de rol (aplica en
re-login / expiracion del access token de 30 min) vive en docs/security.md.
"""

from __future__ import annotations

import sqlite3
from datetime import datetime
from typing import cast

from flask import Blueprint, current_app, g, jsonify, request, session

from ..database import Database
from ..middleware.auth import api_require
from ..permissions import ALLOWED_ROLES

users_api_bp = Blueprint("users_api", __name__)

USER_FIELDS = "id, username, email, full_name, role, is_active, last_login, created_at"


def _db() -> Database:
    return cast(Database, current_app.db)  # type: ignore[attr-defined]


def _get_user(user_id: int) -> dict | None:
    return _db().fetch_one(
        f"SELECT {USER_FIELDS} FROM users WHERE id = ?",
        (user_id,),
    )


def _count_active_admins() -> int:
    row = _db().fetch_one(
        "SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND is_active = 1"
    )
    return int(row["c"]) if row else 0


def _acting_user_id() -> int | None:
    """Id del caller cuando es conocible: sesion WebGUI o claim user_id del JWT."""
    if "user_id" in session:
        return session.get("user_id")
    payload = getattr(g, "api_user", None)
    return payload.get("user_id") if payload else None


def _clean(data: dict) -> tuple[dict, list[str]]:
    """Campos actualizables presentes en el body -> (fields, errors)."""
    fields: dict = {}
    errors: list[str] = []
    for key in ("email", "full_name"):
        if key in data:
            value = data[key]
            if isinstance(value, str):
                value = value.strip()
            if value:  # vacio -> no cambiar (email es UNIQUE nullable)
                fields[key] = value
            elif key == "email":
                errors.append("email no puede quedar vacio (usa otro valor)")
    if "role" in data and data["role"] is not None:
        fields["role"] = str(data["role"]).strip()
    if "is_active" in data and data["is_active"] is not None:
        value = data["is_active"]
        if isinstance(value, bool):
            fields["is_active"] = int(value)
        elif isinstance(value, int) and value in (0, 1):
            fields["is_active"] = value
        else:
            errors.append("is_active debe ser boolean o 0/1")
    return fields, errors


@users_api_bp.route("/", methods=["GET"], strict_slashes=False)
@api_require("users:manage")
def list_users():
    """Lista de usuarios WebGUI (sin password_hash)."""
    rows = _db().fetch_all(f"SELECT {USER_FIELDS} FROM users ORDER BY id")
    return jsonify({"users": rows})


@users_api_bp.route("/", methods=["POST"], strict_slashes=False)
@api_require("users:manage")
def create_user():
    """Crear usuario. username+password requeridos; rol del catalogo ADR-001."""
    data = request.get_json(silent=True) or {}

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    role = str(data.get("role", "auditor")).strip()

    errors = []
    if not username:
        errors.append("username es requerido")
    if role not in ALLOWED_ROLES:
        errors.append(f"rol invalido: {role}")
    valid_password, password_errors = current_app.auth.validate_password_strength(password)
    if not valid_password:
        errors.append("password debil: " + "; ".join(password_errors))

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    try:
        user_id = _db().insert(
            "users",
            {
                "username": username,
                "email": str(data.get("email", "")).strip() or None,
                "password_hash": current_app.auth.hash_password(password),
                "full_name": str(data.get("full_name", "")).strip(),
                "role": role,
                "is_active": 1,
            },
        )
    except sqlite3.IntegrityError:
        return jsonify({"error": "username o email ya existe"}), 409

    return jsonify({"user": _get_user(user_id)}), 201


@users_api_bp.route("/<int:user_id>", methods=["PATCH"])
@api_require("users:manage")
def update_user(user_id: int):
    """Actualizar usuario (parcial): email, full_name, rol, is_active."""
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "usuario no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    fields, errors = _clean(data)

    if errors:
        return jsonify({"error": "; ".join(errors)}), 400
    if not fields:
        return jsonify({"error": "sin campos para actualizar"}), 400

    if "role" in fields and fields["role"] not in ALLOWED_ROLES:
        return jsonify({"error": f"rol invalido: {fields['role']}"}), 400

    # Regla RBAC: jamas degradar/desactivar al ultimo admin activo (ADR-001).
    demotes_admin = (
        user["role"] == "admin"
        and user["is_active"] == 1
        and (fields.get("role", "admin") != "admin" or fields.get("is_active", 1) == 0)
    )
    if demotes_admin and _count_active_admins() <= 1:
        return jsonify({"error": "no puedes degradar/desactivar al ultimo admin activo"}), 409

    # Paridad UI (MYK-416): el caller no puede desactivar su propia cuenta.
    if fields.get("is_active") == 0 and _acting_user_id() == user_id:
        return jsonify({"error": "no puedes desactivar tu propia cuenta"}), 409

    fields["updated_at"] = datetime.now().isoformat()

    try:
        _db().update("users", fields, "id = ?", (user_id,))
    except sqlite3.IntegrityError:
        return jsonify({"error": "email ya existe"}), 409

    return jsonify({"user": _get_user(user_id)})


@users_api_bp.route("/<int:user_id>", methods=["DELETE"])
@api_require("users:manage")
def delete_user(user_id: int):
    """Baja logica (soft delete -> is_active=0); el row se conserva."""
    user = _get_user(user_id)
    if not user:
        return jsonify({"error": "usuario no encontrado"}), 404

    # Regla RBAC: jamas desactivar al ultimo admin activo (ADR-001).
    if user["role"] == "admin" and user["is_active"] == 1 and _count_active_admins() <= 1:
        return jsonify({"error": "no puedes desactivar al ultimo admin activo"}), 409

    # Paridad UI (MYK-416): el caller no puede darse de baja a si mismo.
    if user["is_active"] == 1 and _acting_user_id() == user_id:
        return jsonify({"error": "no puedes desactivar tu propia cuenta"}), 409

    _db().update(
        "users",
        {"is_active": 0, "updated_at": datetime.now().isoformat()},
        "id = ?",
        (user_id,),
    )
    return jsonify({"success": True, "message": f'usuario "{user["username"]}" desactivado'})
