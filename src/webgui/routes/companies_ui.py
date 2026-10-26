"""
Companies UI Routes - seccion Razon Social (MYK-411).

Pagina WebGUI /configuracion/razon-social para CRUD de razones sociales y
ligado/desligado de relojes checadores. La logica CRUD vive en /api/companies
(este mismo PR); este blueprint expone la vista y un endpoint de soporte con
el estado de propiedad de cada reloj. Mismo patron que routes/employees_ui.py.
"""

from flask import Blueprint, current_app, jsonify, render_template

from ..middleware.auth import login_required

companies_ui_bp = Blueprint("companies_ui", __name__)


@companies_ui_bp.route("/", strict_slashes=False)
@login_required
def companies_ui():
    """Pagina de la seccion Razon Social."""
    return render_template("companies/index.html")


@companies_ui_bp.route("/api/devices")
@login_required
def api_devices():
    """Relojes habilitados con serial + razon social propietaria (si ligada)."""
    db = current_app.db
    devices = db.fetch_all(
        """
        SELECT d.id, d.name, d.address, d.serial_number,
               cd.company_id, c.razon_social
        FROM devices d
        LEFT JOIN company_devices cd ON cd.device_serial = d.serial_number
        LEFT JOIN companies c ON c.id = cd.company_id
        WHERE d.is_enabled = 1 AND d.serial_number IS NOT NULL AND d.serial_number <> ''
        ORDER BY d.name
        """
    )
    return jsonify({"devices": devices})
