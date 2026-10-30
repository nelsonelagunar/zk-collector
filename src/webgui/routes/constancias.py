"""
Constancias de asistencia - WebGUI (MYK-593)

Endpoint de generacion y descarga de PDF de la constancia de asistencia
de un colaborador para un periodo de asistencia. Reutiliza la implementacion
del reporte de asistencia (`compute_attendance_stats`) de modo que los
numeros de la constancia cuadran con los del dashboard de reportes.

Rutas (sesion WebGUI o Bearer JWT; requiere permiso `reports:export`):
- GET /reportes/constancia/<int:employee_id>/pdf  -> PDF descargable
"""

from __future__ import annotations

import io
from datetime import date
from typing import cast

from flask import Blueprint, current_app, jsonify, request, send_file

from ..attendance_stats import (
    DEFAULT_COMPANY,
    DEFAULT_WORK_START,
    StatsValidationError,
    compute_attendance_stats,
    parse_iso_date,
)
from ..constancia import build_constancia_pdf
from ..database import Database
from ..middleware.auth import api_require

constancias_bp = Blueprint("constancias", __name__)

_DEFAULT_COMPANY_NAME = "Attendance Collector"


def _collect_filters() -> dict:
    today = date.today()
    return {
        "start_date": request.args.get("start_date") or today.replace(day=1).isoformat(),
        "end_date": request.args.get("end_date") or today.isoformat(),
    }


@constancias_bp.route("/constancia/<int:employee_id>/pdf")
@api_require("reports:export")
def constancia_pdf(employee_id: int):
    """Generar y descargar la constancia de asistencia en PDF de un colaborador."""
    try:
        filters = _collect_filters()
        start = parse_iso_date(filters["start_date"], "start_date")
        end = parse_iso_date(filters["end_date"], "end_date")
        if start > end:
            raise StatsValidationError("start_date no puede ser posterior a end_date")
    except StatsValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    db: Database = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employee = db.fetch_one(
        "SELECT id, employee_code, first_name, last_name, department, hire_date "
        "FROM employees WHERE id = ? AND status = 'active'",
        (employee_id,),
    )
    if employee is None:
        return jsonify({"error": "Empleado no encontrado o inactivo"}), 404

    report = compute_attendance_stats(
        db,
        current_app.buffer_repo,  # type: ignore[attr-defined]
        start.isoformat(),
        end.isoformat(),
        employee_id=employee_id,
        group_by="employee",
        work_start=current_app.config.get("ATTENDANCE_WORK_START", DEFAULT_WORK_START),
        company_name=current_app.config.get("COMPANY_NAME", DEFAULT_COMPANY),
    )
    if not report["rows"]:
        return jsonify({"error": "Empleado no encontrado o sin datos en el periodo"}), 404

    row = report["rows"][0]
    company_name = current_app.config.get("COMPANY_NAME", _DEFAULT_COMPANY_NAME)

    pdf_bytes = build_constancia_pdf(
        employee_name=row["employee_name"],
        employee_code=row["employee_code"],
        department=row["department"],
        hire_date=employee["hire_date"],
        period=report["period"],
        stats=row,
        company_name=company_name,
        issued_at=date.today(),
    )

    filename = f"constancia_{row['employee_code']}_{start.isoformat()}_{end.isoformat()}.pdf"
    return send_file(
        io.BytesIO(pdf_bytes),
        mimetype="application/pdf",
        as_attachment=True,
        download_name=filename,
    )
