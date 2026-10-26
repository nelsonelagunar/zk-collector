"""
Attendance Integrity Routes - WebGUI (MYK-422 / MYK-410 item 4)

- GET  /api/attendance/integrity                -> verificacion de la cadena
  SHA-256 de attendance_records + resumen de la bitacora (solo admin).
- POST /api/attendance/records/<id>/correction  -> correccion auditada:
  anula el original e inserta la fila corregida, dejando entradas en
  attendance_audit_log (quien/cuando/motivo/anterior-posterior).

Autenticacion admin: sesion WebGUI (flujo UI) o Bearer JWT con role=admin
(flujo API). Un UPDATE directo a un registro NO pasa por aqui: lo detecta
el verificador (hash_mismatch) y los triggers lo dejan en la bitacora.
"""

import sqlite3
from datetime import datetime

from flask import Blueprint, current_app, jsonify, request, session

attendance_integrity_bp = Blueprint("attendance_integrity", __name__)

_CORRECTABLE_FIELDS = ("timestamp", "status", "punch_type", "device_ip")


def _admin_actor() -> tuple[str | None, tuple | None]:
    """
    Resuelve el actor admin del request (sesion WebGUI o Bearer JWT).

    Returns:
        (username, None) si es admin; (None, (respuesta, status)) si no.
    """
    if session.get("role") == "admin" and session.get("username"):
        return str(session["username"]), None

    auth_header = request.headers.get("Authorization", "")
    if auth_header.startswith("Bearer "):
        payload = current_app.auth.verify_access_token(  # type: ignore[attr-defined]
            auth_header[len("Bearer ") :]
        )
        if payload and payload.get("role") == "admin":
            return str(payload.get("username") or f"user:{payload.get('user_id')}"), None

    if not session.get("user_id") and not auth_header:
        return None, (jsonify({"error": "authentication required"}), 401)
    return None, (jsonify({"error": "admin role required"}), 403)


@attendance_integrity_bp.route("/integrity")
def integrity_report():
    """Verificacion de cadena: 200 con valid true/false (nunca 4xx por cadenas rotas)."""
    _, error = _admin_actor()
    if error:
        return error
    report = current_app.buffer_repo.verify_integrity()  # type: ignore[attr-defined]
    return jsonify(report)


@attendance_integrity_bp.route("/records/<int:record_id>/correction", methods=["POST"])
def correct_attendance_record(record_id: int):
    """Correccion auditada de una marcada. Body JSON: campo(s) a corregir + reason (obligatorio)."""
    actor, error = _admin_actor()
    if error:
        return error

    body = request.get_json(silent=True) or {}
    reason = str(body.get("reason") or "").strip()
    if not reason:
        return jsonify({"error": "reason (motivo) es obligatorio"}), 400

    updates: dict[str, object] = {}
    if body.get("timestamp"):
        try:
            updates["timestamp"] = datetime.fromisoformat(str(body["timestamp"])).isoformat()
        except ValueError:
            return jsonify({"error": "timestamp debe ser ISO-8601 (YYYY-MM-DDTHH:MM:SS)"}), 400
    if body.get("status") is not None:
        try:
            updates["status"] = int(body["status"])
        except (TypeError, ValueError):
            return jsonify({"error": "status debe ser entero"}), 400
    if body.get("punch_type") is not None:
        punch_type = str(body["punch_type"]).strip()
        if punch_type:
            updates["punch_type"] = punch_type
    if body.get("device_ip"):
        updates["device_ip"] = str(body["device_ip"]).strip()

    if not updates:
        return (
            jsonify(
                {"error": "correccion sin cambios: indica " + ", ".join(_CORRECTABLE_FIELDS)}
            ),
            400,
        )

    try:
        result = current_app.buffer_repo.correct_record(  # type: ignore[attr-defined]
            record_id, actor=actor, reason=reason, **updates
        )
    except KeyError:
        return jsonify({"error": f"registro {record_id} no existe"}), 404
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 409
    except sqlite3.IntegrityError:
        return (
            jsonify(
                {
                    "error": "la correccion colisiona con un registro activo "
                    "(usuario+fecha+dispositivo ya existen)"
                }
            ),
            409,
        )

    return jsonify({"status": "corrected", "audit": "recorded", **result})
