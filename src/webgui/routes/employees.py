"""
Employees Routes - CRUD de colaboradores (MYK-221)
API REST para el módulo HR-1 Colaboradores ABC.
Estilo consistente con src/webgui/routes/devices.py (jsonify + status codes).

Datos laborales opcionales (CURP/RFC/NSS/tipo jornada/turno) validados en
MYK-423 via src/webgui/validators.py; export CSV en /export.
"""

import csv
import io
import sqlite3

from flask import Blueprint, Response, current_app, jsonify, request

from ..middleware.auth import api_auth_required
from ..validators import LABOR_FIELDS, normalize_labor_fields

employees_bp = Blueprint("employees", __name__)

REQUIRED_FIELDS = ("employee_code", "first_name", "last_name")
UPDATABLE_FIELDS = (
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "phone",
    "department",
    "position",
    "hire_date",
    "notes",
) + LABOR_FIELDS

EXPORT_COLUMNS = (
    "employee_code",
    "first_name",
    "last_name",
    "email",
    "department",
    "position",
    "hire_date",
    "status",
    "curp",
    "rfc",
    "nss",
    "imss_numero_seguro",
    "tipo_jornada",
    "turno",
)


def _db():
    return current_app.db


def _validate_payload(data: dict, partial: bool = False) -> list[str]:
    """Devuelve lista de errores de validación (vacía si es válido)."""
    errors: list[str] = []

    if not isinstance(data, dict):
        return ["body JSON requerido"]

    for field in REQUIRED_FIELDS:
        if not partial and not str(data.get(field, "")).strip():
            errors.append(f"{field} es requerido")

    if "employee_code" in data and data["employee_code"] is not None:
        code = str(data["employee_code"]).strip()
        if not code:
            errors.append("employee_code es requerido")
        else:
            data["employee_code"] = code

    if "first_name" in data and not str(data.get("first_name", "")).strip():
        errors.append("first_name es requerido")
    if "last_name" in data and not str(data.get("last_name", "")).strip():
        errors.append("last_name es requerido")

    try:
        normalize_labor_fields(data)
    except ValueError as exc:
        errors.append(str(exc))

    return errors


@employees_bp.route("/", methods=["GET"])
@api_auth_required
def list_employees():
    """Lista paginada de colaboradores con filtros status/department/search."""
    db = _db()

    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(max(1, request.args.get("per_page", 20, type=int)), 200)
    offset = (page - 1) * per_page

    status = request.args.get("status", "").strip()
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()

    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if department:
        conditions.append("department = ?")
        params.append(department)
    if search:
        conditions.append(
            "(employee_code LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
            "OR email LIKE ? OR department LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    total = db.fetch_one(f"SELECT COUNT(*) AS c FROM employees {where}", tuple(params))["c"]
    rows = db.fetch_all(
        f"SELECT * FROM employees {where} ORDER BY last_name, first_name LIMIT ? OFFSET ?",
        tuple(params + [per_page, offset]),
    )

    total_pages = (total + per_page - 1) // per_page

    return jsonify(
        {
            "employees": rows,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": total_pages,
                "has_next": page < total_pages,
                "has_prev": page > 1,
            },
        }
    )


@employees_bp.route("/export", methods=["GET"])
@api_auth_required
def export_employees():
    """Export CSV de colaboradores con columnas laborales (MYK-423): incluye CURP y RFC."""
    db = _db()

    status = request.args.get("status", "").strip()
    department = request.args.get("department", "").strip()
    search = request.args.get("search", "").strip()

    conditions: list[str] = []
    params: list = []

    if status:
        conditions.append("status = ?")
        params.append(status)
    if department:
        conditions.append("department = ?")
        params.append(department)
    if search:
        conditions.append(
            "(employee_code LIKE ? OR first_name LIKE ? OR last_name LIKE ? "
            "OR email LIKE ? OR department LIKE ?)"
        )
        like = f"%{search}%"
        params.extend([like, like, like, like, like])

    where = f"WHERE {' AND '.join(conditions)}" if conditions else ""

    rows = db.fetch_all(
        f"SELECT {', '.join(EXPORT_COLUMNS)} FROM employees {where} ORDER BY last_name, first_name",
        tuple(params),
    )

    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(EXPORT_COLUMNS)
    for row in rows:
        writer.writerow(["" if row[col] is None else row[col] for col in EXPORT_COLUMNS])

    return Response(
        buffer.getvalue(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=colaboradores.csv"},
    )


@employees_bp.route("/", methods=["POST"])
@api_auth_required
def create_employee():
    """Crear colaborador."""
    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    fields = {k: data[k] for k in UPDATABLE_FIELDS if k in data and data[k] is not None}

    db = _db()
    try:
        employee_id = db.create_employee(fields)
    except sqlite3.IntegrityError:
        return jsonify({"error": "employee_code ya existe"}), 409

    employee = db.get_employee_by_id(employee_id)
    return jsonify({"employee": employee}), 201


@employees_bp.route("/<int:employee_id>", methods=["GET"])
@api_auth_required
def get_employee(employee_id: int):
    """Obtener colaborador por id."""
    db = _db()
    employee = db.get_employee_by_id(employee_id)
    if not employee:
        return jsonify({"error": "colaborador no encontrado"}), 404
    return jsonify({"employee": employee})


@employees_bp.route("/<int:employee_id>", methods=["PUT"])
@api_auth_required
def update_employee(employee_id: int):
    """Actualizar colaborador (parcial)."""
    db = _db()
    if not db.get_employee_by_id(employee_id):
        return jsonify({"error": "colaborador no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    errors = _validate_payload(data, partial=True)
    if errors:
        return jsonify({"error": "; ".join(errors)}), 400

    fields = {k: data[k] for k in UPDATABLE_FIELDS if k in data and data[k] is not None}
    if not fields:
        return jsonify({"error": "sin campos para actualizar"}), 400

    try:
        db.update_employee(employee_id, fields)
    except sqlite3.IntegrityError:
        return jsonify({"error": "employee_code ya existe"}), 409

    return jsonify({"employee": db.get_employee_by_id(employee_id)})


@employees_bp.route("/<int:employee_id>", methods=["DELETE"])
@api_auth_required
def delete_employee(employee_id: int):
    """Baja lógica (soft-delete → status inactive)."""
    db = _db()
    if not db.get_employee_by_id(employee_id):
        return jsonify({"error": "colaborador no encontrado"}), 404

    db.delete_employee(employee_id)
    return jsonify({"success": True, "message": "colaborador dado de baja (inactive)"})


@employees_bp.route("/<int:employee_id>/device-links", methods=["POST"])
@api_auth_required
def link_device(employee_id: int):
    """Asociar device_serial + device_user_id al colaborador."""
    db = _db()
    if not db.get_employee_by_id(employee_id):
        return jsonify({"error": "colaborador no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    device_serial = str(data.get("device_serial", "")).strip()
    device_user_id = str(data.get("device_user_id", "")).strip()

    if not device_serial or not device_user_id:
        return jsonify({"error": "device_serial y device_user_id son requeridos"}), 400

    try:
        db.link_employee_to_device(employee_id, device_serial, device_user_id)
    except sqlite3.IntegrityError:
        return jsonify({"error": "enlace ya existe"}), 409

    return jsonify(
        {
            "success": True,
            "link": {
                "employee_id": employee_id,
                "device_serial": device_serial,
                "device_user_id": device_user_id,
            },
        }
    ), 201


@employees_bp.route("/<int:employee_id>/device-links", methods=["DELETE"])
@api_auth_required
def unlink_device(employee_id: int):
    """Desasociar device_serial + device_user_id del colaborador."""
    db = _db()
    if not db.get_employee_by_id(employee_id):
        return jsonify({"error": "colaborador no encontrado"}), 404

    data = request.get_json(silent=True) or {}
    device_serial = str(data.get("device_serial", "")).strip()
    device_user_id = str(data.get("device_user_id", "")).strip()

    if not device_serial or not device_user_id:
        return jsonify({"error": "device_serial y device_user_id son requeridos"}), 400

    deleted = db.unlink_employee_from_device(employee_id, device_serial, device_user_id)
    if not deleted:
        return jsonify({"error": "enlace no encontrado"}), 404

    return jsonify({"success": True, "message": "enlace eliminado"})


@employees_bp.route("/<int:employee_id>/device-links", methods=["GET"])
@api_auth_required
def list_device_links(employee_id: int):
    """Listar dispositivos vinculados al colaborador."""
    db = _db()
    if not db.get_employee_by_id(employee_id):
        return jsonify({"error": "colaborador no encontrado"}), 404

    return jsonify(
        {
            "device_links": db.fetch_all(
                "SELECT device_serial, device_user_id FROM employee_device_links "
                "WHERE employee_id = ? ORDER BY device_serial",
                (employee_id,),
            )
        }
    )
