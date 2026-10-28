"""
Employees UI Routes - Módulo Colaboradores ABC (MYK-230).

Página WebGUI para altas/bajas/cambios de colaboradores y vinculación con
dispositivos ZKTeco. La lógica CRUD vive en /api/employees (MYK-221); este
blueprint solo expone la vista y dos endpoints de soporte para el selector
de dispositivos y usuarios del reloj.

Gestion del PIN del portal /mi-asistencia (MYK-425): RRHH/admin genera o
limpia el PIN de un colaborador desde el expediente.
"""

import secrets
from datetime import UTC, datetime
from typing import cast

from flask import Blueprint, abort, current_app, flash, jsonify, redirect, render_template, url_for

from ..database import Database
from ..middleware.auth import admin_required, api_auth_required, login_required

employees_ui_bp = Blueprint("employees_ui", __name__)


@employees_ui_bp.route("/", strict_slashes=False)
@login_required
def list_employees_ui():
    """Página principal de colaboradores."""
    return render_template("employees/list.html")


@employees_ui_bp.route("/expediente/<int:employee_id>")
@login_required
def employee_expediente_ui(employee_id: int):
    """Expediente del colaborador con sección de incapacidades (MYK-240)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        abort(404)
    return render_template("employees/detail.html", employee=employee)


@employees_ui_bp.route("/expediente/<int:employee_id>/pin/generar", methods=["POST"])
@admin_required
def generate_pin_ui(employee_id: int):
    """Genera un PIN de portal (6 digitos) para el colaborador. Se muestra una vez."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    auth = current_app.auth  # type: ignore[attr-defined]
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        abort(404)
    if employee["status"] != "active":
        flash("Solo se puede generar PIN para empleados activos.", "error")
        return redirect(url_for("employees_ui.employee_expediente_ui", employee_id=employee_id))

    pin = f"{secrets.randbelow(1_000_000):06d}"
    now = datetime.now(UTC).strftime("%Y-%m-%d %H:%M:%S")
    db.update_employee(employee_id, {"pin_hash": auth.hash_password(pin), "pin_updated_at": now})

    flash(
        f"PIN generado para {employee['first_name']} {employee['last_name']}: {pin}. "
        "Entrégaselo al colaborador y no lo conserves.",
        "warning",
    )
    return redirect(url_for("employees_ui.employee_expediente_ui", employee_id=employee_id))


@employees_ui_bp.route("/expediente/<int:employee_id>/pin/limpiar", methods=["POST"])
@admin_required
def clear_pin_ui(employee_id: int):
    """Quita el PIN de portal (desactiva el acceso del colaborador a /mi-asistencia)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        abort(404)
    db.update_employee(employee_id, {"pin_hash": None})
    flash(f"PIN de portal quitado de {employee['first_name']} {employee['last_name']}.", "success")
    return redirect(url_for("employees_ui.employee_expediente_ui", employee_id=employee_id))


@employees_ui_bp.route("/api/devices")
@api_auth_required
def api_devices():
    """Dispositivos habilitados con serial para el selector de vínculos."""
    db = current_app.db
    devices = db.fetch_all(
        """
        SELECT id, name, address, serial_number, is_enabled
        FROM devices
        WHERE is_enabled = 1
        ORDER BY name
        """
    )
    return jsonify({"devices": devices})


@employees_ui_bp.route("/api/devices/<int:device_id>/users")
@api_auth_required
def api_device_users(device_id):
    """Usuarios del reloj para el selector de user_id."""
    db = current_app.db
    device = db.fetch_one("SELECT id FROM devices WHERE id = ?", (device_id,))
    if not device:
        return jsonify({"error": "dispositivo no encontrado"}), 404

    users = db.fetch_all(
        """
        SELECT user_id, name
        FROM device_users
        WHERE device_id = ?
        ORDER BY user_id
        """,
        (device_id,),
    )
    return jsonify({"users": users})
