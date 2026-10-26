"""
API Devices - Estado de dispositivos para consumo externo (MYK-407).

Endpoint read-only del estado de los relojes checadores registrados:
id, nombre, direccion, estado, ultima conexion, firmware, serial.
"""

from flask import Blueprint, current_app, jsonify

from ..middleware.auth import api_auth_required

api_devices_bp = Blueprint("api_devices", __name__)


@api_devices_bp.route("/", methods=["GET"])
@api_auth_required(required_scope="read")
def list_device_status():
    """Estado de todos los dispositivos registrados."""
    db = current_app.db
    devices = db.fetch_all(
        """
        SELECT id, name, address, port, status, is_enabled,
               firmware_version, serial_number, last_seen
        FROM devices ORDER BY name
        """
    )
    online = sum(1 for d in devices if d["status"] == "online")
    return jsonify(
        {
            "devices": devices,
            "summary": {
                "total": len(devices),
                "online": online,
                "offline": len(devices) - online,
            },
        }
    )


@api_devices_bp.route("/<int:device_id>", methods=["GET"])
@api_auth_required(required_scope="read")
def get_device_status(device_id: int):
    """Estado de un dispositivo por id."""
    db = current_app.db
    device = db.fetch_one(
        """
        SELECT id, name, address, port, status, is_enabled,
               firmware_version, serial_number, last_seen
        FROM devices WHERE id = ?
        """,
        (device_id,),
    )
    if not device:
        return jsonify({"error": "dispositivo no encontrado"}), 404
    return jsonify({"device": device})
