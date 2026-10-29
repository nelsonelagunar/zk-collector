"""
API Buffer - Retención efectiva para QA (MYK-505).

Endpoint read-only que expone la retención configurada y la bitácora de
purgas/archivados del collector, para verificar la retención efectiva sin
acceder al LXC.
"""
from flask import Blueprint, current_app, jsonify

from ..middleware.auth import api_require

api_buffer_bp = Blueprint("api_buffer", __name__)


@api_buffer_bp.route("/retention", methods=["GET"])
@api_require("reports:read")
def get_retention():
    """Retención efectiva del collector (QA recurrente, MYK-505).

    Devuelve:
    - retention_days efectivo del runtime (default 790 = 26 meses, RT-1)
    - archive_enabled: si archive-and-purge está configurado
    - total_records / pending_sync
    - últimas entradas de las bitácoras de retención y archivado
    """
    repo = current_app.buffer_repo
    stats = repo.get_stats()

    return jsonify(
        {
            "retention_days": stats.get("retention_days"),
            "archive_enabled": stats.get("archive_enabled", False),
            "total_records": stats.get("total_records", 0),
            "pending_sync": stats.get("pending_sync", 0),
            "retention_audit": repo.get_retention_audit(limit=10),
            "archive_log": repo.get_archive_log(limit=10),
        }
    )
