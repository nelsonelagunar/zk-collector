"""
Medical Leaves Routes - CRUD de incapacidades (MYK-239)
API REST para el módulo HR-3 Incapacidades.
Estilo consistente con src/webgui/routes/employees.py (jsonify + status codes).
"""

from typing import cast

from flask import Blueprint, current_app, jsonify, request

from ..database import Database
from ..medical_leaves import (
    EmployeeNotFoundError,
    LeaveNotFoundError,
    MedicalLeaveRepository,
    ValidationError,
)
from ..middleware.auth import api_auth_required

medical_leaves_bp = Blueprint("medical_leaves", __name__)


def _repo() -> MedicalLeaveRepository:
    db = current_app.db  # type: ignore[attr-defined]
    return MedicalLeaveRepository(cast(Database, db))


def _parse_pagination() -> tuple[int, int]:
    page = max(1, request.args.get("page", 1, type=int))
    per_page = min(50, max(1, request.args.get("per_page", 20, type=int)))
    return page, per_page


@medical_leaves_bp.route("/", methods=["GET"])
@api_auth_required
def list_medical_leaves():
    """Lista paginada de incapacidades con filtro opcional por employee_id."""
    repo = _repo()
    page, per_page = _parse_pagination()
    employee_id = request.args.get("employee_id", type=int)

    leaves, total = repo.list_leaves(
        employee_id=employee_id,
        page=page,
        per_page=per_page,
    )

    total_pages = (total + per_page - 1) // per_page
    return jsonify(
        {
            "leaves": leaves,
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


@medical_leaves_bp.route("/", methods=["POST"])
@api_auth_required
def create_medical_leave():
    """Crear incapacidad. `days` se calcula server-side y se ignora si llega."""
    repo = _repo()
    data = request.get_json(silent=True) or {}

    try:
        leave_id = repo.create(data)
    except EmployeeNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    leave = repo.get(leave_id)
    if leave is None:
        return jsonify({"error": "incapacidad no encontrada"}), 404
    warnings = repo.vacation_overlap_warnings(
        leave["employee_id"],
        leave["start_date"],
        leave["end_date"],
    )
    return jsonify({"leave": leave, "warnings": warnings}), 201


@medical_leaves_bp.route("/<int:leave_id>", methods=["GET"])
@api_auth_required
def get_medical_leave(leave_id: int):
    """Obtener incapacidad por id."""
    repo = _repo()
    leave = repo.get(leave_id)
    if not leave:
        return jsonify({"error": "incapacidad no encontrada"}), 404
    return jsonify({"leave": leave})


@medical_leaves_bp.route("/<int:leave_id>", methods=["PUT"])
@api_auth_required
def update_medical_leave(leave_id: int):
    """Actualizar incapacidad (parcial). `days` se recalcula server-side."""
    repo = _repo()
    data = request.get_json(silent=True) or {}

    try:
        repo.update(leave_id, data)
    except LeaveNotFoundError as exc:
        return jsonify({"error": str(exc)}), 404
    except EmployeeNotFoundError as exc:
        return jsonify({"error": str(exc)}), 400
    except ValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    leave = repo.get(leave_id)
    if leave is None:
        return jsonify({"error": "incapacidad no encontrada"}), 404
    warnings = repo.vacation_overlap_warnings(
        leave["employee_id"],
        leave["start_date"],
        leave["end_date"],
    )
    return jsonify({"leave": leave, "warnings": warnings})


@medical_leaves_bp.route("/<int:leave_id>", methods=["DELETE"])
@api_auth_required
def cancel_medical_leave(leave_id: int):
    """Borrado logico: status -> cancelled."""
    repo = _repo()
    leave = repo.get(leave_id)
    if not leave:
        return jsonify({"error": "incapacidad no encontrada"}), 404

    repo.cancel(leave_id)
    return jsonify(
        {
            "success": True,
            "message": "incapacidad cancelada",
            "leave": repo.get(leave_id),
        }
    )
