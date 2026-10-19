"""
Employees UI Routes - Módulo Colaboradores ABC (MYK-230).

Página WebGUI para altas/bajas/cambios de colaboradores y vinculación con
dispositivos ZKTeco. La lógica CRUD vive en /api/employees (MYK-221); este
blueprint solo expone la vista y dos endpoints de soporte para el selector
de dispositivos y usuarios del reloj.
"""

from typing import cast

from flask import Blueprint, abort, current_app, jsonify, render_template

from ..database import Database

employees_ui_bp = Blueprint("employees_ui", __name__)


@employees_ui_bp.route("/")
def list_employees_ui():
    """Página principal de colaboradores."""
    return render_template("employees/list.html")


@employees_ui_bp.route("/expediente/<int:employee_id>")
def employee_expediente_ui(employee_id: int):
    """Expediente del colaborador con sección de incapacidades (MYK-240)."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        abort(404)
    return render_template("employees/detail.html", employee=employee)


@employees_ui_bp.route("/api/devices")
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
