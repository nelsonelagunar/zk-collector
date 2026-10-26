"""
Companies Routes - CRUD de razon social + vinculo reloj checador (MYK-411).
API REST Bearer sobre la capa Database de MYK-405 (migration 008).
Estilo consistente con src/webgui/routes/employees.py (jsonify + status codes).
"""

import sqlite3

from flask import Blueprint, current_app, jsonify, request

from ..middleware.auth import api_auth_required

companies_bp = Blueprint("companies", __name__)

REQUIRED_FIELDS = ("razon_social",)
UPDATABLE_FIELDS = (
    "razon_social",
    "rfc",
    "imss_registro_patronal",
    "domicilio_fiscal",
)


def _db():
    return current_app.db


def _validate_payload(data, partial=False):
    """Devuelve lista de errores de validacion (vacia si es valido)."""
    errors = []

    if not isinstance(data, dict):
        return ["body JSON requerido"]

    for field in REQUIRED_FIELDS:
        if not partial and not str(data.get(field, "")).strip():
            errors.append(f"{field} es requerido")

    if "razon_social" in data and not str(data.get("razon_social", "")).strip():
        errors.append("razon_social es requerido")

    return errors


def _clean_fields(data):
    """Campos UPDATABLE presentes, strip() en strings, None fuera."""
    fields = {}
    for key in UPDATABLE_FIELDS:
        if key in data and data[key] is not None:
            value = str(data[key]).strip() if isinstance(data[key], str) else data[key]
            if value != "":
                fields[key] = value
    return fields


@companies_bp.route("/", methods=["GET"])
@api_auth_required
def list_companies():
    """Lista de razones sociales con filtro opcional status=active|inactive."""
    status = request.args.get("status", "").strip()
    rows = _db().get_companies(status=status or None)
    return jsonify({"companies": rows})


@companies_bp.route("/", methods=["POST"])
@api_auth_required
def create_company():
    """Crear razon social. razon_social requerido; RFC unico cuando se captura."""
    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    fields = _clean_fields(data)
    if not fields:
        return jsonify({"error": "razon_social es requerido"}), 400

    try:
        company_id = _db().create_company(fields)
    except sqlite3.IntegrityError:
        return jsonify({"error": "rfc ya existe"}), 409

    return jsonify({"company": _db().get_company_by_id(company_id)}), 201


@companies_bp.route("/<int:company_id>", methods=["GET"])
@api_auth_required
def get_company(company_id):
    """Obtener razon social por id (incluye inactivas)."""
    company = _db().get_company_by_id(company_id)
    if not company:
        return jsonify({"error": "razon social no encontrada"}), 404
    return jsonify({"company": company})


@companies_bp.route("/<int:company_id>", methods=["PUT"])
@api_auth_required
def update_company(company_id):
    """Actualizar razon social (parcial)."""
    if not _db().get_company_by_id(company_id):
        return jsonify({"error": "razon social no encontrada"}), 404

    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, partial=True)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    fields = _clean_fields(data)
    if not fields:
        return jsonify({"error": "sin campos para actualizar"}), 400

    try:
        _db().update_company(company_id, fields)
    except sqlite3.IntegrityError:
        return jsonify({"error": "rfc ya existe"}), 409

    return jsonify({"company": _db().get_company_by_id(company_id)})


@companies_bp.route("/<int:company_id>", methods=["DELETE"])
@api_auth_required
def delete_company(company_id):
    """Baja logica (soft delete -> status inactive); conserva vinculos."""
    if not _db().get_company_by_id(company_id):
        return jsonify({"error": "razon social no encontrada"}), 404

    _db().delete_company(company_id)
    return jsonify({"success": True, "message": "razon social dada de baja (inactive)"})


@companies_bp.route("/<int:company_id>/devices", methods=["GET"])
@api_auth_required
def list_company_devices(company_id):
    """Relojes checadores vinculados a la razon social."""
    if not _db().get_company_by_id(company_id):
        return jsonify({"error": "razon social no encontrada"}), 404

    devices = _db().get_devices_for_company(company_id)
    return jsonify({"devices": devices})


@companies_bp.route("/<int:company_id>/devices", methods=["POST"])
@api_auth_required
def link_device(company_id):
    """Ligar reloj checador a la razon social.

    El puente es 1:N con UNIQUE(device_serial): si el reloj ya pertenece a
    otra razon social, el upsert de Database.link_device_to_company TRANSFIERE
    la propiedad (comportamiento documentado en docs/companies.md).
    """
    if not _db().get_company_by_id(company_id):
        return jsonify({"error": "razon social no encontrada"}), 404

    data = request.get_json(silent=True) or {}
    device_serial = str(data.get("device_serial", "")).strip()
    if not device_serial:
        return jsonify({"error": "device_serial es requerido"}), 400

    device = _db().fetch_one(
        "SELECT id, name FROM devices WHERE serial_number = ?", (device_serial,)
    )
    if not device:
        return jsonify({"error": "dispositivo no encontrado"}), 404

    _db().link_device_to_company(company_id, device_serial)
    return jsonify(
        {
            "success": True,
            "link": {"company_id": company_id, "device_serial": device_serial},
        }
    ), 201


@companies_bp.route("/<int:company_id>/devices/<device_serial>", methods=["DELETE"])
@api_auth_required
def unlink_device(company_id, device_serial):
    """Desligar reloj checador de la razon social."""
    if not _db().get_company_by_id(company_id):
        return jsonify({"error": "razon social no encontrada"}), 404

    owner = _db().get_company_for_device(device_serial)
    if not owner or owner["id"] != company_id:
        return jsonify({"error": "vinculo no encontrado"}), 404

    _db().unlink_device_from_company(device_serial)
    return jsonify({"success": True, "message": "vinculo eliminado"})
