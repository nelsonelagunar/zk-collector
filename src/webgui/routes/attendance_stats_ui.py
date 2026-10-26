"""
Attendance Stats UI Routes - Dashboard de reportes (MYK-242)

Dashboard WebGUI con graficas de estadisticos de asistencia
(presentes/ausentes/retardos/incapacidades/vacaciones, puntualidad % y
ausentismo %) y filtros por rango de fechas, colaborador y departamento.

Los numeros NO se mockean: esta vista reutiliza la implementacion de los
endpoints de MYK-241 (`compute_report` sobre
`attendance_stats.compute_attendance_stats`), por lo que el dashboard y la
API `/api/attendance/stats` cuadran por construccion (los tests de
`tests/test_attendance_stats_ui.py` comparan ambas respuestas).

Rutas (sesion WebGUI, sin Bearer):
- GET /reportes           -> pagina del dashboard
- GET /reportes/api/stats -> JSON con el reporte (mismos filtros que la API)
- GET /reportes/export    -> CSV/XLSX con los mismos filtros (csv default)
"""

from datetime import date
from typing import cast

from flask import Blueprint, current_app, jsonify, render_template, request

from ..attendance_stats import StatsValidationError
from ..database import Database
from ..middleware.auth import api_auth_required, login_required
from .attendance_stats import build_export_response, compute_report

attendance_stats_ui_bp = Blueprint("attendance_stats_ui", __name__)


def _active_filter_options(db: Database) -> tuple[list[dict], list[str]]:
    """Opciones para los selects de colaborador y departamento (activos)."""
    employees = db.fetch_all(
        """
        SELECT id, employee_code, first_name, last_name
        FROM employees
        WHERE status = 'active'
        ORDER BY last_name, first_name
        """
    )
    department_rows = db.fetch_all(
        """
        SELECT DISTINCT department
        FROM employees
        WHERE status = 'active' AND department IS NOT NULL AND department != ''
        ORDER BY department
        """
    )
    return employees, [row["department"] for row in department_rows]


@attendance_stats_ui_bp.route("/", strict_slashes=False)
@login_required
def stats_dashboard():
    """Dashboard de estadisticos de asistencia con filtros."""
    db = cast(Database, current_app.db)  # type: ignore[attr-defined]
    employees, departments = _active_filter_options(db)
    today = date.today()
    return render_template(
        "reports/stats.html",
        employees=employees,
        departments=departments,
        default_start_date=today.replace(day=1).isoformat(),
        default_end_date=today.isoformat(),
    )


@attendance_stats_ui_bp.route("/api/stats")
@api_auth_required
def stats_json():
    """Reporte JSON con los mismos filtros que /api/attendance/stats."""
    try:
        report = compute_report()
    except StatsValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(report)


@attendance_stats_ui_bp.route("/export")
@api_auth_required
def stats_export():
    """Exportar el reporte del dashboard a CSV o Excel (mismos filtros)."""
    try:
        report = compute_report()
    except StatsValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    format_type = request.args.get("format", "csv").lower()
    return build_export_response(report, format_type)
