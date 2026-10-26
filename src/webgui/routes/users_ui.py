"""
Users UI Routes - Seccion Usuarios (MYK-377).

Alta/baja de usuarios WebGUI dentro del layout con menus. La sesion la
gestiona /auth; aqui solo listado, alta y activacion/desactivacion.
"""

from typing import cast

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

from ..database import Database
from ..middleware.auth import admin_required, login_required
from ..permissions import ALLOWED_ROLES

users_ui_bp = Blueprint("users_ui", __name__)


@users_ui_bp.route("/", strict_slashes=False)
@login_required
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
@admin_required
def create_user_ui():
    """Alta de usuario WebGUI (solo admin)."""
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


@users_ui_bp.route("/<int:user_id>/toggle", methods=["POST"], strict_slashes=False)
@admin_required
def toggle_user_ui(user_id: int):
    """Activar/desactivar usuario WebGUI (solo admin)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]

    user = db.fetch_one("SELECT id, username, is_active FROM users WHERE id = ?", (user_id,))
    if not user:
        flash("Usuario no encontrado", "error")
        return redirect(url_for("users_ui.list_users_ui"))
    if user["id"] == session.get("user_id"):
        flash("No puedes desactivar tu propia cuenta", "error")
        return redirect(url_for("users_ui.list_users_ui"))

    db.update("users", {"is_active": 0 if user["is_active"] else 1}, "id = ?", (user_id,))
    estado = "activado" if not user["is_active"] else "desactivado"
    flash(f'Usuario "{user["username"]}" {estado}', "success")
    return redirect(url_for("users_ui.list_users_ui"))
