"""
Users UI Routes - Seccion Usuarios (MYK-377, RBAC en MYK-416).

Alta/edicion/baja de usuarios WebGUI dentro del layout con menus. La sesion
la gestiona /auth; aqui listado, alta, edicion (rol/email/nombre) y
activacion/desactivacion.

Gating users:manage (MYK-416): referencia de la semantica que `require()`
(MYK-413/414) debe preservar en rutas UI de escritura —
  * sin sesion -> redirect a login (302);
  * GET sin permiso -> flash + redirect a la pagina 403 amigable;
  * POST sin permiso -> 403 (AC MYK-416: POST con rol no-admin devuelve 403).
"""

from datetime import datetime
from functools import wraps
from typing import cast

from flask import (
    Blueprint,
    abort,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    session,
    url_for,
)

from ..database import Database
from ..permissions import ALLOWED_ROLES, has_permission

users_ui_bp = Blueprint("users_ui", __name__)


def users_manage_ui_required(view):
    """Gate UI de users:manage (ver docstring del modulo)."""

    @wraps(view)
    def decorated(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión para acceder", "warning")
            return redirect(url_for("auth.login", next=request.url))
        if not has_permission(str(session.get("role", "")), "users:manage"):
            if request.method == "POST":
                abort(403)
            flash("Tu rol no tiene permiso para administrar usuarios", "error")
            return redirect(url_for("errors_ui.forbidden"))
        return view(*args, **kwargs)

    return decorated


def _count_active_admins(db: Database) -> int:
    row = db.fetch_one("SELECT COUNT(*) AS c FROM users WHERE role = 'admin' AND is_active = 1")
    return row["c"] if row else 0


@users_ui_bp.route("/", strict_slashes=False)
@users_manage_ui_required
def list_users_ui():
    """Listado de usuarios WebGUI."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    users = db.fetch_all(
        """
        SELECT id, username, email, full_name, role, is_active,
               last_login, created_at
        FROM users
        ORDER BY username
        """
    )
    return render_template("users/list.html", users=users)


@users_ui_bp.route("/new", methods=["GET", "POST"], strict_slashes=False)
@users_manage_ui_required
def create_user_ui():
    """Alta de usuario WebGUI (solo users:manage)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    if request.method == "POST":
        username = request.form.get("username", "").strip()
        email = request.form.get("email", "").strip()
        full_name = request.form.get("full_name", "").strip()
        # Catalogo cerrado del ADR-001; 'user' legacy ya no es rol valido
        # (la migracion 008 normaliza los rows existentes a 'auditor').
        role = request.form.get("role", "auditor")
        password = request.form.get("password", "")

        errors = []
        if not username:
            errors.append("El usuario es requerido")
        if len(password) < 8:
            errors.append("La contrasena debe tener al menos 8 caracteres")
        if role not in ALLOWED_ROLES:
            errors.append("Rol invalido")
        if username and db.fetch_one("SELECT id FROM users WHERE username = ?", (username,)):
            errors.append("Ese usuario ya existe")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template(
                "users/new.html",
                form=request.form,
            )

        db.insert(
            "users",
            {
                "username": username,
                "email": email,
                "password_hash": current_app.auth.hash_password(password),
                "full_name": full_name,
                "role": role,
                "is_active": 1,
            },
        )
        flash(f'Usuario "{username}" creado exitosamente', "success")
        return redirect(url_for("users_ui.list_users_ui"))

    return render_template("users/new.html", form={})


@users_ui_bp.route("/<int:user_id>/edit", methods=["GET", "POST"], strict_slashes=False)
@users_manage_ui_required
def edit_user_ui(user_id: int):
    """Edicion de usuario WebGUI: nombre, email y rol (catalogo ADR-001)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    user = db.fetch_one(
        """
        SELECT id, username, email, full_name, role, is_active
        FROM users WHERE id = ?
        """,
        (user_id,),
    )
    if not user:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("users_ui.list_users_ui"))

    if request.method == "POST":
        email = request.form.get("email", "").strip() or None
        full_name = request.form.get("full_name", "").strip()
        role = request.form.get("role", user["role"])

        errors = []
        if role not in ALLOWED_ROLES:
            errors.append("Rol invalido")
        if (
            email
            and db.fetch_one("SELECT id FROM users WHERE email = ? AND id != ?", (email, user_id))
        ):
            errors.append("Ese email ya está en uso")
        # Nunca degradar al ultimo admin activo (regla RBAC, MYK-415 paridad API)
        if user["role"] == "admin" and role != "admin" and _count_active_admins(db) <= 1:
            errors.append("No puedes quitar el rol al último administrador activo")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("users/edit.html", user=user, form=request.form)

        db.update(
            "users",
            {
                "email": email,
                "full_name": full_name,
                "role": role,
                "updated_at": datetime.now().isoformat(),
            },
            "id = ?",
            (user_id,),
        )
        flash(f'Usuario "{user["username"]}" actualizado', "success")
        return redirect(url_for("users_ui.list_users_ui"))

    return render_template("users/edit.html", user=user, form={})


@users_ui_bp.route("/<int:user_id>/toggle", methods=["POST"], strict_slashes=False)
@users_manage_ui_required
def toggle_user_ui(user_id: int):
    """Activar/desactivar usuario WebGUI (solo users:manage)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    user = db.fetch_one("SELECT id, username, role, is_active FROM users WHERE id = ?", (user_id,))
    if not user:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("users_ui.list_users_ui"))
    if user["id"] == session.get("user_id"):
        flash("No puedes desactivar tu propia cuenta", "error")
        return redirect(url_for("users_ui.list_users_ui"))
    # Nunca desactivar al ultimo admin activo (regla RBAC, MYK-415 paridad API)
    if user["is_active"] and user["role"] == "admin" and _count_active_admins(db) <= 1:
        flash("No puedes desactivar al último administrador activo", "error")
        return redirect(url_for("users_ui.list_users_ui"))

    db.update("users", {"is_active": 0 if user["is_active"] else 1}, "id = ?", (user_id,))
    estado = "activado" if not user["is_active"] else "desactivado"
    flash(f'Usuario "{user["username"]}" {estado}', "success")
    return redirect(url_for("users_ui.list_users_ui"))
