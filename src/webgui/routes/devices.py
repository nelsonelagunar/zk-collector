"""
Devices Routes - CRUD de dispositivos ZKTeco
"""

import logging
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    flash,
    jsonify,
    redirect,
    render_template,
    request,
    url_for,
)
from zk import ZK
from zk.exception import ZKError

from src.zk_client.discovery import discover_devices

logger = logging.getLogger(__name__)

devices_bp = Blueprint("devices", __name__)


@devices_bp.route("/")
def list_devices():
    """Lista de dispositivos"""
    db = current_app.db
    devices = db.fetch_all("SELECT * FROM devices ORDER BY name")
    return render_template("devices/list.html", devices=devices)


@devices_bp.route("/new", methods=["GET", "POST"])
def create_device():
    """Crear nuevo dispositivo"""
    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "location": request.form.get("location", ""),
            "zone": request.form.get("zone", ""),
            "ip": request.form.get("address", ""),  # Form uses 'address', DB uses 'ip'
            "port": int(request.form.get("port", 4370)),
            "password": int(request.form.get("password", 0)),
            "timeout": int(request.form.get("timeout", 5)),
            "protocol": request.form.get("protocol", "tcp"),
        }

        # Validaciones
        errors = []
        if not data["name"]:
            errors.append("Nombre es requerido")
        if not data["ip"]:
            errors.append("Dirección es requerida")

        if errors:
            for error in errors:
                flash(error, "error")
            return render_template("devices/create.html")

        # Guardar en DB
        db = current_app.db
        db.insert("devices", data)

        flash(f'Dispositivo "{data["name"]}" creado exitosamente', "success")
        return redirect(url_for("devices.list_devices"))

    return render_template("devices/create.html")


@devices_bp.route("/<int:device_id>/edit", methods=["GET", "POST"])
def edit_device(device_id):
    """Editar dispositivo"""
    db = current_app.db

    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "location": request.form.get("location", ""),
            "zone": request.form.get("zone", ""),
            "ip": request.form.get("address", ""),  # Form uses 'address', DB uses 'ip'
            "port": int(request.form.get("port", 4370)),
            "password": int(request.form.get("password", 0)),
            "timeout": int(request.form.get("timeout", 5)),
            "protocol": request.form.get("protocol", "tcp"),
            "updated_at": datetime.now().isoformat(),
        }

        # Validaciones
        if not data["name"] or not data["ip"]:
            flash("Nombre y dirección son requeridos", "error")
            return render_template("devices/edit.html", device_id=device_id)

        # Actualizar en DB
        db.update("devices", data, "id = ?", (device_id,))

        flash("Dispositivo actualizado", "success")
        return redirect(url_for("devices.list_devices"))

    # GET - mostrar form
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        flash("Dispositivo no encontrado", "error")
        return redirect(url_for("devices.list_devices"))

    # Template expects 'address' field (form field name)
    device["address"] = device["ip"]
    return render_template("devices/edit.html", device=device)


@devices_bp.route("/<int:device_id>/delete", methods=["POST"])
def delete_device(device_id):
    """Eliminar dispositivo"""
    db = current_app.db
    db.delete("devices", "id = ?", (device_id,))

    flash("Dispositivo eliminado", "success")
    return redirect(url_for("devices.list_devices"))


@devices_bp.route("/<int:device_id>/test")
def test_device(device_id):
    """Probar conexión con dispositivo - API endpoint"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    try:
        # Intentar conexión - DB uses 'ip' column
        zk = ZK(
            device["ip"],
            port=device["port"],
            timeout=device["timeout"],
            password=device["password"],
            force_udp=(device["protocol"] == "udp"),
        )

        conn = zk.connect()

        if conn:
            # Obtener información
            device_info = {
                "firmware": zk.get_firmware_version(),
                "serial": zk.get_serialnumber(),
                "platform": zk.get_platform(),
            }

            # Actualizar estado en DB
            db.update(
                "devices",
                {
                    "status": "online",
                    "last_seen": datetime.now().isoformat(),
                    "firmware_version": device_info["firmware"],
                    "serial_number": device_info["serial"],
                },
                "id = ?",
                (device_id,),
            )

            zk.disconnect()

            return jsonify(
                {"success": True, "message": "Conexión exitosa", "device_info": device_info}
            )
        else:
            return jsonify({"success": False, "message": "No se pudo conectar al dispositivo"})

    except ZKError as e:
        # Actualizar estado offline
        db.update("devices", {"status": "offline"}, "id = ?", (device_id,))

        return jsonify({"success": False, "message": f"Error ZK: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@devices_bp.route("/api/devices/test", methods=["POST"])
def api_test_device():
    """API endpoint para test de conexión desde el form"""
    data = request.get_json()

    try:
        zk = ZK(
            data.get("address", ""),
            port=data.get("port", 4370),
            timeout=data.get("timeout", 5),
            password=data.get("password", 0),
            force_udp=(data.get("protocol") == "udp"),
        )

        conn = zk.connect()

        if conn:
            device_info = {
                "firmware": zk.get_firmware_version(),
                "serial": zk.get_serialnumber(),
            }
            zk.disconnect()

            return jsonify(
                {"success": True, "message": "Conexión exitosa", "device_info": device_info}
            )
        else:
            return jsonify({"success": False, "message": "No se pudo conectar"})

    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@devices_bp.route("/api/devices/discover", methods=["POST"])
def api_discover_devices():
    """API endpoint para descubrimiento automático de dispositivos en LAN"""
    data = request.get_json() or {}

    network = data.get("network")  # Optional CIDR like "192.168.1.0/24"
    timeout = data.get("timeout", 3.0)
    retries = data.get("retries", 2)
    fetch_details = data.get("fetch_details", True)

    try:
        logger = current_app.logger
        logger.info(
            f"Iniciando descubrimiento de dispositivos (network={network}, timeout={timeout})"
        )

        devices = discover_devices(
            network=network, timeout=timeout, retries=retries, fetch_details=fetch_details
        )

        # Filter out devices already in database
        db = current_app.db
        existing_ips = set(d["ip"] for d in db.fetch_all("SELECT ip FROM devices"))

        # Mark which devices are already configured
        for device in devices:
            device["already_configured"] = device["ip"] in existing_ips

        return jsonify(
            {
                "success": True,
                "message": f"Descubiertos {len(devices)} dispositivo(s)",
                "devices": devices,
            }
        )

    except Exception as e:
        logger = current_app.logger
        logger.error(f"Error en descubrimiento: {e}")
        return jsonify({"success": False, "message": f"Error en descubrimiento: {str(e)}"}), 500


@devices_bp.route("/api/devices/discover/quick", methods=["POST"])
def api_quick_discover():
    """Quick discovery - just UDP broadcast without TCP detail fetch (faster)"""
    data = request.get_json() or {}

    network = data.get("network")
    timeout = data.get("timeout", 2.0)
    retries = data.get("retries", 1)

    try:
        logger = current_app.logger
        logger.info(f"Quick discovery: network={network}")

        devices = discover_devices(
            network=network, timeout=timeout, retries=retries, fetch_details=False
        )

        db = current_app.db
        existing_ips = set(d["ip"] for d in db.fetch_all("SELECT ip FROM devices"))

        for device in devices:
            device["already_configured"] = device["ip"] in existing_ips

        return jsonify(
            {
                "success": True,
                "message": f"Encontrados {len(devices)} dispositivo(s)",
                "devices": devices,
            }
        )

    except Exception as e:
        logger = current_app.logger
        logger.error(f"Error en quick discovery: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@devices_bp.route("/discover", methods=["GET"])
def discover_page():
    """Página de descubrimiento de dispositivos en LAN"""
    return render_template("devices/discover.html")


@devices_bp.route("/api/devices/discover", methods=["GET"])
def api_discover_devices_get():
    """API endpoint GET para descubrimiento automático de dispositivos en LAN"""
    network = request.args.get("network")  # Optional CIDR like "192.168.1.0/24"
    timeout = float(request.args.get("timeout", 3.0))
    retries = int(request.args.get("retries", 2))
    fetch_details = request.args.get("fetch_details", "true").lower() == "true"

    try:
        logger.info(
            f"Iniciando descubrimiento de dispositivos (network={network}, timeout={timeout})"
        )

        devices = discover_devices(
            network=network, timeout=timeout, retries=retries, fetch_details=fetch_details
        )

        # Filter out devices already in database
        db = current_app.db
        existing_ips = set(d["ip"] for d in db.fetch_all("SELECT ip FROM devices"))

        # Mark which devices are already configured
        for device in devices:
            device["already_configured"] = device["ip"] in existing_ips

        return jsonify(
            {
                "success": True,
                "message": f"Descubiertos {len(devices)} dispositivo(s)",
                "devices": devices,
            }
        )

    except Exception as e:
        logger.error(f"Error en descubrimiento: {e}")
        return jsonify({"success": False, "message": f"Error en descubrimiento: {str(e)}"}), 500


@devices_bp.route("/api/devices/add-from-discovery", methods=["POST"])
def api_add_from_discovery():
    """API endpoint para agregar dispositivo desde descubrimiento"""
    data = request.get_json()

    if not data:
        return jsonify({"success": False, "message": "Datos requeridos"}), 400

    required_fields = ["ip", "name"]
    for field in required_fields:
        if not data.get(field):
            return jsonify({"success": False, "message": f"Campo requerido: {field}"}), 400

    try:
        db = current_app.db

        # Check if device already exists
        existing = db.fetch_one("SELECT id FROM devices WHERE ip = ?", (data["ip"],))
        if existing:
            return (
                jsonify({"success": False, "message": "Ya existe un dispositivo con esta IP"}),
                409,
            )

        # Create device with pre-filled config from discovery
        device_data = {
            "name": data["name"],
            "ip": data["ip"],
            "port": data.get("port", 4370),
            "password": data.get("password", 0),
            "timeout": data.get("timeout", 5),
            "protocol": data.get("protocol", "tcp"),
            "location": data.get("location", ""),
            "zone": data.get("zone", ""),
            "status": "unknown",
            "enabled": 1,
            "mac": data.get("mac", ""),
            "model": data.get("model", ""),
            "firmware_version": data.get("firmware", ""),
            "serial_number": data.get("serial", ""),
            "created_at": datetime.now().isoformat(),
            "updated_at": datetime.now().isoformat(),
        }

        device_id = db.insert("devices", device_data)

        logger.info(f"Dispositivo agregado desde descubrimiento: {data['name']} ({data['ip']})")

        return jsonify(
            {
                "success": True,
                "message": f'Dispositivo "{data["name"]}" agregado exitosamente',
                "device_id": device_id,
            }
        )

    except Exception as e:
        logger.error(f"Error agregando dispositivo desde descubrimiento: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@devices_bp.route("/<int:device_id>/toggle", methods=["POST"])
def toggle_device(device_id):
    """Activar/desactivar dispositivo"""
    db = current_app.db

    device = db.fetch_one("SELECT is_enabled FROM devices WHERE id = ?", (device_id,))
    if device:
        new_status = 0 if device["is_enabled"] else 1
        db.update("devices", {"is_enabled": new_status}, "id = ?", (device_id,))

    return redirect(url_for("devices.list_devices"))


@devices_bp.route("/<int:device_id>")
def device_detail(device_id):
    """Detalle del dispositivo"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        flash("Dispositivo no encontrado", "error")
        return redirect(url_for("devices.list_devices"))

    return render_template("devices/detail.html", device=device)


@devices_bp.route("/<int:device_id>/users")
def device_users(device_id):
    """Usuarios del dispositivo"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        flash("Dispositivo no encontrado", "error")
        return redirect(url_for("devices.list_devices"))

    return render_template("devices/users.html", device=device)


@devices_bp.route("/<int:device_id>/sync-users", methods=["POST"])
def sync_users(device_id):
    """Sincronizar usuarios desde dispositivo ZKTeco"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    try:
        from src.zk_client.client import ZKClient

        client = ZKClient(
            ip=device["ip"],
            port=device["port"],
            timeout=device["timeout"],
            password=str(device["password"]),
            force_udp=(device["protocol"] == "udp"),
        )

        if not client.connect(max_retries=2, retry_delay=1.0):
            return jsonify({"success": False, "message": "No se pudo conectar al dispositivo"}), 500

        users = client.get_users()
        client.disconnect()

        if users is None:
            return (
                jsonify({"success": False, "message": "Error obteniendo usuarios del dispositivo"}),
                500,
            )

        # Upsert users into device_users table
        synced_count = 0
        for user in users:
            db.execute(
                """
                INSERT INTO device_users (device_ip, user_id, name, privilege, group_id, user_role, synced_at)
                VALUES (?, ?, ?, ?, ?, ?, CURRENT_TIMESTAMP)
                ON CONFLICT(device_ip, user_id) DO UPDATE SET
                    name = excluded.name,
                    privilege = excluded.privilege,
                    group_id = excluded.group_id,
                    user_role = excluded.user_role,
                    synced_at = CURRENT_TIMESTAMP,
                    updated_at = CURRENT_TIMESTAMP
                """,
                (
                    device["ip"],
                    user["user_id"],
                    user["name"],
                    user["privilege"],
                    user["group_id"],
                    user["user_role"],
                ),
            )
            synced_count += 1

        return jsonify(
            {"success": True, "message": f"Sincronizados {synced_count} usuarios", "count": synced_count}
        )

    except Exception as e:
        logger.error(f"Error sincronizando usuarios: {e}")
        return jsonify({"success": False, "message": f"Error: {str(e)}"}), 500


@devices_bp.route("/api/device-users")
def api_device_users():
    """API para obtener lista de usuarios de un dispositivo"""
    device_ip = request.args.get("device_ip", "")

    if not device_ip:
        return jsonify({"error": "device_ip parameter required"}), 400

    db = current_app.db
    users = db.fetch_all(
        "SELECT user_id, name FROM device_users WHERE device_ip = ? ORDER BY name",
        (device_ip,),
    )

    return jsonify(
        {"users": [{"user_id": u["user_id"], "name": u["name"]} for u in users]}
    )
