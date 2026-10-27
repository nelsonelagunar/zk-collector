"""
Devices Routes - CRUD de dispositivos ZKTeco
"""

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

from ..middleware.auth import api_auth_required, login_required

devices_bp = Blueprint("devices", __name__)


def _user_field(user, attr, default=""):
    """Lee un campo de un usuario ZK tolerando los shapes que devuelve pyzk.

    MYK-397: zk.user.User real expone atributos (uid, name, privilege,
    password, group_id, user_id, card) SIN user_role y SIN .get(); llamar
    user.get() sobre el es un AttributeError. Se prefiere atributo, luego
    dict-like, y si el campo no existe se devuelve el default.
    """
    value = getattr(user, attr, None)
    if value is not None:
        return value
    if hasattr(user, "get"):
        return user.get(attr, default)
    return default


@devices_bp.route("/<int:device_id>/sync-users", methods=["POST"])
@api_auth_required(required_scope="write")
def sync_users(device_id):
    """Sincronizar usuarios desde el dispositivo ZKTeco a la base de datos WebGUI"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    try:
        # ommit_ping: el probe real es el handshake TCP; pyzk.test_ping() (ICMP)
        # falla en redes que filtran ICMP (misma clase que MYK-384)
        zk = ZK(
            device["address"],
            port=device["port"],
            timeout=device["timeout"],
            password=device["password"],
            force_udp=(device["protocol"] == "udp"),
            ommit_ping=True,
        )

        conn = zk.connect()

        if not conn:
            return jsonify({"success": False, "message": "No se pudo conectar al dispositivo"})

        # Obtener usuarios del dispositivo
        users = zk.get_users()
        zk.disconnect()

        if not users:
            return jsonify(
                {"success": True, "message": "No hay usuarios en el dispositivo", "synced_count": 0}
            )

        # Upsert en device_users
        synced_count = 0
        for user in users:
            user_id = str(_user_field(user, "user_id", ""))
            name = _user_field(user, "name", "")
            privilege = _user_field(user, "privilege", 0)
            password = _user_field(user, "password", "")
            group_id = str(_user_field(user, "group_id", ""))
            user_role = _user_field(user, "user_role", 0)

            # Verificar si existe
            existing = db.fetch_one(
                "SELECT id FROM device_users WHERE device_id = ? AND user_id = ?",
                (device_id, user_id),
            )

            if existing:
                db.update(
                    "device_users",
                    {
                        "name": name,
                        "privilege": privilege,
                        "password": password,
                        "group_id": group_id,
                        "user_role": user_role,
                        "updated_at": datetime.now().isoformat(),
                    },
                    "id = ?",
                    (existing["id"],),
                )
            else:
                db.insert(
                    "device_users",
                    {
                        "device_id": device_id,
                        "user_id": user_id,
                        "name": name,
                        "privilege": privilege,
                        "password": password,
                        "group_id": group_id,
                        "user_role": user_role,
                    },
                )
            synced_count += 1

        return jsonify(
            {
                "success": True,
                "message": f"Sincronizados {synced_count} usuarios",
                "synced_count": synced_count,
            }
        )

    except ZKError as e:
        return jsonify({"success": False, "message": f"Error ZK: {str(e)}"})
    except Exception as e:
        return jsonify({"success": False, "message": f"Error: {str(e)}"})


@devices_bp.route("/api/device-users")
@api_auth_required(required_scope="read")
def api_device_users():
    """API para obtener lista de usuarios de un dispositivo"""
    db = current_app.db
    device_ip = request.args.get("device_ip", "")

    if not device_ip:
        return jsonify({"success": False, "message": "device_ip es requerido"}), 400

    # Obtener device_id por IP
    device = db.fetch_one("SELECT id FROM devices WHERE address = ?", (device_ip,))
    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    users = db.fetch_all(
        # MYK-451: la tabla tiene updated_at (migracion 001), no synced_at;
        # el alias preserva el shape {"users": [{..., "synced_at": ...}]}
        # que consume devices/detail.html.
        "SELECT user_id, name, privilege, group_id, user_role, "
        "updated_at AS synced_at "
        "FROM device_users WHERE device_id = ? ORDER BY user_id",
        (device["id"],),
    )

    return jsonify({"users": users})


@devices_bp.route("/api/device-users/stats")
@api_auth_required(required_scope="read")
def api_device_users_stats():
    """API para obtener estadísticas de usuarios de un dispositivo"""
    db = current_app.db
    device_ip = request.args.get("device_ip", "")

    if not device_ip:
        return jsonify({"success": False, "message": "device_ip es requerido"}), 400

    device = db.fetch_one("SELECT id FROM devices WHERE address = ?", (device_ip,))
    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    total = db.fetch_one(
        "SELECT COUNT(*) as count FROM device_users WHERE device_id = ?", (device["id"],)
    )

    with_names = db.fetch_one(
        "SELECT COUNT(*) as count FROM device_users "
        "WHERE device_id = ? AND name IS NOT NULL AND name != ''",
        (device["id"],),
    )

    return jsonify(
        {
            "total": total["count"] if total else 0,
            "with_names": with_names["count"] if with_names else 0,
        }
    )


@devices_bp.route("/", strict_slashes=False)
@login_required
def list_devices():
    """Lista de dispositivos"""
    db = current_app.db
    devices = db.fetch_all("SELECT * FROM devices ORDER BY name")
    return render_template("devices/list.html", devices=devices)


@devices_bp.route("/new", methods=["GET", "POST"])
@login_required
def create_device():
    """Crear nuevo dispositivo"""
    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "location": request.form.get("location", ""),
            "zone": request.form.get("zone", ""),
            "address": request.form.get("address", ""),
            "port": int(request.form.get("port", 4370)),
            "password": int(request.form.get("password", 0)),
            "timeout": int(request.form.get("timeout", 5)),
            "protocol": request.form.get("protocol", "tcp"),
        }

        # Validaciones
        errors = []
        if not data["name"]:
            errors.append("Nombre es requerido")
        if not data["address"]:
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
@login_required
def edit_device(device_id):
    """Editar dispositivo"""
    db = current_app.db

    if request.method == "POST":
        data = {
            "name": request.form.get("name", ""),
            "location": request.form.get("location", ""),
            "zone": request.form.get("zone", ""),
            "address": request.form.get("address", ""),
            "port": int(request.form.get("port", 4370)),
            "password": int(request.form.get("password", 0)),
            "timeout": int(request.form.get("timeout", 5)),
            "protocol": request.form.get("protocol", "tcp"),
            "updated_at": datetime.now().isoformat(),
        }

        # Validaciones
        if not data["name"] or not data["address"]:
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

    return render_template("devices/edit.html", device=device)


@devices_bp.route("/<int:device_id>/delete", methods=["POST"])
@login_required
def delete_device(device_id):
    """Eliminar dispositivo"""
    db = current_app.db
    db.delete("devices", "id = ?", (device_id,))

    flash("Dispositivo eliminado", "success")
    return redirect(url_for("devices.list_devices"))


@devices_bp.route("/<int:device_id>/test")
@api_auth_required(required_scope="write")
def test_device(device_id):
    """Probar conexión con dispositivo - API endpoint"""
    db = current_app.db
    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        return jsonify({"success": False, "message": "Dispositivo no encontrado"}), 404

    try:
        # Intentar conexión — ommit_ping: el probe real es el handshake TCP,
        # pyzk.test_ping() (ICMP) falla en redes que filtran ICMP (MYK-384)
        zk = ZK(
            device["address"],
            port=device["port"],
            timeout=device["timeout"],
            password=device["password"],
            force_udp=(device["protocol"] == "udp"),
            ommit_ping=True,
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
@api_auth_required(required_scope="write")
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
            ommit_ping=True,
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


@devices_bp.route("/<int:device_id>/detail")
@login_required
def device_detail(device_id):
    """Vista detallada del dispositivo con tabs"""
    db = current_app.db

    device = db.fetch_one("SELECT * FROM devices WHERE id = ?", (device_id,))

    if not device:
        flash("Dispositivo no encontrado", "error")
        return redirect(url_for("devices.list_devices"))

    return render_template("devices/detail.html", device=device)


@devices_bp.route("/<int:device_id>/toggle", methods=["POST"])
@login_required
def toggle_device(device_id):
    """Activar/desactivar dispositivo"""
    db = current_app.db

    device = db.fetch_one("SELECT is_enabled FROM devices WHERE id = ?", (device_id,))
    if device:
        new_status = 0 if device["is_enabled"] else 1
        db.update("devices", {"is_enabled": new_status}, "id = ?", (device_id,))

    return redirect(url_for("devices.list_devices"))
