"""
API Buffer - Retención efectiva para QA (MYK-505).

Endpoint read-only de la retención efectiva del collector.
"""
from flask import Blueprint, current_app, jsonify

from ..middleware.auth import api_auth_required

api_buffer_bp = Blueprint("api_buffer", __name__)


@api_buffer_bp.route("/retention", methods=["GET"])
@api_auth_required(required_scope="read")
def get_retention():
    """Retención efectiva del collector para QA recurring.

    Devuelve:
    - retention_days EFECTIVO del runtime (Config.default() o YAML)
    - fuente de config (default|archivo+path)
    - total_records
    - ultima entrada de bitacora get_retention_audit(limit=10)
    """
    stats = current_app.buffer_repo.get_stats()
    retention_audit = current_app.buffer_repo.get_retention_audit(limit=10)

    return jsonify(
        {
            "retention_days": stats.get("retention_days", 30),
            "config_source": stats.get("config_source", "default"),
            "config_path": stats.get("config_path"),
            "total_records": stats.get("total_records", 0),
            "pending_sync": stats.get("pending_sync", 0),
            "retention_audit": retention_audit,
        }
    )
