"""
API Tokens Routes - Gestion de Personal Access Tokens (MYK-407).

Endpoints para crear, listar y revocar tokens de API. Requieren sesion
admin (los tokens se emiten desde el panel, no via API abierta).
"""

from flask import Blueprint, current_app, jsonify, request, session

from ..api_tokens import ApiTokenService
from ..middleware.auth import admin_required

api_tokens_bp = Blueprint("api_tokens", __name__)

MAX_TOKENS_PER_USER = 20
DEFAULT_EXPIRES_IN_DAYS = 90


def _db():
    return current_app.db


def _service() -> ApiTokenService:
    return ApiTokenService(_db())


@api_tokens_bp.route("/", methods=["GET"])
@admin_required
def list_tokens():
    """Lista los tokens del usuario actual (admin ve todos). Sin hash nunca."""
    service = _service()
    user_id = session.get("user_id")
    if session.get("role") == "admin":
        tokens = service.list_tokens()
    else:
        tokens = service.list_tokens(user_id=user_id)
    return jsonify({"tokens": tokens})


@api_tokens_bp.route("/", methods=["POST"])
@admin_required
def create_token():
    """Crea un PAT. El token plano se devuelve UNA sola vez."""
    data = request.get_json(silent=True) or {}
    name = str(data.get("name", "")).strip()
    scopes = data.get("scopes") or ["read"]
    expires_in_days = data.get("expires_in_days", DEFAULT_EXPIRES_IN_DAYS)

    if not name:
        return jsonify({"error": "name es requerido"}), 400

    if not isinstance(scopes, list) or not scopes:
        return jsonify({"error": "scopes debe ser lista no vacia"}), 400

    if expires_in_days is not None:
        try:
            expires_in_days = int(expires_in_days)
        except (TypeError, ValueError):
            return jsonify({"error": "expires_in_days debe ser entero o null"}), 400
        if expires_in_days <= 0 or expires_in_days > 365:
            return jsonify({"error": "expires_in_days debe estar entre 1 y 365"}), 400

    user_id = session.get("user_id")
    existing = _service().list_tokens(user_id=user_id)
    active = [t for t in existing if not t["revoked_at"]]
    if len(active) >= MAX_TOKENS_PER_USER:
        return jsonify({"error": "limite de tokens activos alcanzado"}), 429

    try:
        result = _service().issue_token(
            user_id=user_id,
            name=name,
            scopes=scopes,
            expires_in_days=expires_in_days,
        )
    except ValueError as exc:
        return jsonify({"error": str(exc)}), 400

    record = result["record"]
    return (
        jsonify(
            {
                "token": result["token"],
                "record": {
                    "id": record["id"],
                    "name": record["name"],
                    "scopes": record["scopes"],
                    "expires_at": record["expires_at"],
                    "created_at": record["created_at"],
                },
            }
        ),
        201,
    )


@api_tokens_bp.route("/<int:token_id>", methods=["DELETE"])
@admin_required
def revoke_token(token_id: int):
    """Revoca un token. Solo el dueno o un admin puede revocarlo."""
    user_id = session.get("user_id")
    is_admin = session.get("role") == "admin"

    record = current_app.db.fetch_one(
        "SELECT user_id, revoked_at FROM api_tokens WHERE id = ?", (token_id,)
    )
    if not record:
        return jsonify({"error": "token no encontrado"}), 404

    if not is_admin and record["user_id"] != user_id:
        return jsonify({"error": "no autorizado"}), 403

    if record["revoked_at"]:
        return jsonify({"revoked": False, "message": "token ya revocado"})

    _service().revoke_token(token_id, user_id=user_id if not is_admin else None)
    return jsonify({"revoked": True})
