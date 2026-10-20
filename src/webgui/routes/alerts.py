"""
Alertas HR - Rutas WebGUI (MYK-227 / HR-6).

API para listar alertas, marcar leida/resuelta y preferencias de notificacion
por usuario (opt-in por tipo). Sirve de capa de datos a la vista de alertas
del WebGUI.
"""

from flask import Blueprint, current_app, jsonify, request

alerts_bp = Blueprint("alerts", __name__)

ALERT_STATUSES = ("pending", "sent", "read", "resolved")


def _db():
    return current_app.db


def _engine():
    engine = getattr(current_app, "alert_engine", None)
    if engine is None:
        from ..alerts import AlertEngine

        engine = AlertEngine(current_app.db)
        current_app.alert_engine = engine
    return engine


@alerts_bp.route("/", methods=["GET"])
def list_alerts():
    """Lista de alertas con filtros opcionales (status, employee_id, event_type)."""
    db = _db()

    status = request.args.get("status", "").strip()
    employee_id = request.args.get("employee_id", type=int)
    event_type = request.args.get("event_type", "").strip()

    conditions: list[str] = []
    params: list = []
    if status:
        if status not in ALERT_STATUSES:
            return jsonify({"error": "status invalido"}), 400
        conditions.append("status = ?")
        params.append(status)
    if employee_id is not None:
        conditions.append("employee_id = ?")
        params.append(employee_id)
    if event_type:
        conditions.append("event_type = ?")
        params.append(event_type)

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""
    total = db.fetch_one(f"SELECT COUNT(*) AS c FROM alerts {where}", tuple(params))["c"]
    rows = db.fetch_all(
        f"SELECT * FROM alerts {where} ORDER BY created_at DESC",
        tuple(params),
    )

    return jsonify({"alerts": rows, "total": total})


@alerts_bp.route("/<int:alert_id>/read", methods=["PATCH"])
def mark_read(alert_id: int):
    """Marca una alerta como leída."""
    db = _db()
    if not db.fetch_one("SELECT id FROM alerts WHERE id = ?", (alert_id,)):
        return jsonify({"error": "alerta no encontrada"}), 404
    _engine().mark_read(alert_id)
    return jsonify({"success": True, "alert_id": alert_id, "status": "read"})


@alerts_bp.route("/<int:alert_id>/resolved", methods=["PATCH"])
def mark_resolved(alert_id: int):
    """Marca una alerta como resuelta."""
    db = _db()
    if not db.fetch_one("SELECT id FROM alerts WHERE id = ?", (alert_id,)):
        return jsonify({"error": "alerta no encontrada"}), 404
    _engine().mark_resolved(alert_id)
    return jsonify({"success": True, "alert_id": alert_id, "status": "resolved"})


@alerts_bp.route("/preferences", methods=["GET"])
def list_preferences():
    """Lista preferencias de notificacion por usuario y tipo de alerta."""
    db = _db()
    user_id = request.args.get("user_id", type=int)
    if user_id is None:
        return jsonify({"error": "user_id requerido"}), 400
    rows = db.fetch_all(
        "SELECT * FROM user_alert_preferences WHERE user_id = ? ORDER BY alert_type",
        (user_id,),
    )
    return jsonify({"preferences": rows})


@alerts_bp.route("/preferences", methods=["POST"])
def set_preference():
    """Establece/actualiza la preferencia de notificacion de un usuario."""
    db = _db()
    data = request.get_json(silent=True) or {}
    user_id = data.get("user_id")
    alert_type = data.get("alert_type")
    enabled = data.get("enabled", True)

    if not user_id or not alert_type:
        return jsonify({"error": "user_id y alert_type son requeridos"}), 400

    updated = db.update(
        "user_alert_preferences",
        {"enabled": 1 if enabled else 0},
        "user_id = ? AND alert_type = ?",
        (int(user_id), alert_type),
    )
    if updated == 0:
        db.insert(
            "user_alert_preferences",
            {
                "user_id": int(user_id),
                "alert_type": alert_type,
                "enabled": 1 if enabled else 0,
            },
        )

    return jsonify(
        {
            "success": True,
            "user_id": int(user_id),
            "alert_type": alert_type,
            "enabled": bool(enabled),
        }
    ), 201
