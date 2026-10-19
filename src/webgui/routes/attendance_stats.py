"""
Attendance Stats Routes - WebGUI (MYK-241)

API de reportes de asistencia:
- GET /api/attendance/stats          -> JSON con KPIs por periodo
- GET /api/attendance/stats/export   -> CSV/Excel con los mismos filtros

Filtros (compartidos por ambos endpoints):
- start_date, end_date (YYYY-MM-DD; default: mes actual)
- employee_id, department
- group_by: employee | department | company
- export: format=csv|xlsx

El export reutiliza el patron del export existente de asistencia
(`routes/attendance.py`): csv.DictWriter con BOM utf-8-sig y openpyxl.
"""

import csv
import io
from datetime import date, datetime

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    request,
    send_file,
)
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

from ..attendance_stats import (
    DEFAULT_COMPANY,
    DEFAULT_WORK_START,
    StatsValidationError,
    compute_attendance_stats,
)
from ..middleware.auth import api_auth_required

attendance_stats_bp = Blueprint("attendance_stats", __name__)

_NUMERIC_COLUMNS: tuple[tuple[str, str], ...] = (
    ("days_expected", "Días Esperados"),
    ("days_present", "Días Presentes"),
    ("days_absent", "Días Ausentes"),
    ("days_incapacity", "Días Incapacidad"),
    ("days_vacation", "Días Vacaciones"),
    ("late_arrivals", "Retardos"),
    ("punctuality_pct", "Puntualidad %"),
    ("absenteeism_pct", "Ausentismo %"),
)

_LABEL_COLUMNS: dict[str, tuple[tuple[str, str], ...]] = {
    "employee": (
        ("employee_code", "Código"),
        ("employee_name", "Colaborador"),
        ("department", "Departamento"),
    ),
    "department": (("department", "Departamento"),),
    "company": (("company", "Empresa"),),
}


def _collect_filters() -> dict:
    today = date.today()
    employee_id_raw = request.args.get("employee_id")
    employee_id: int | None = None
    if employee_id_raw:
        try:
            employee_id = int(employee_id_raw)
        except ValueError as exc:
            raise StatsValidationError("employee_id debe ser un entero") from exc
    return {
        "start_date": request.args.get("start_date") or today.replace(day=1).isoformat(),
        "end_date": request.args.get("end_date") or today.isoformat(),
        "employee_id": employee_id,
        "department": request.args.get("department") or None,
        "group_by": request.args.get("group_by", "employee"),
    }


def _compute_report() -> dict:
    filters = _collect_filters()
    return compute_attendance_stats(
        current_app.db,  # type: ignore[attr-defined]
        current_app.buffer_repo,  # type: ignore[attr-defined]
        filters["start_date"],
        filters["end_date"],
        employee_id=filters["employee_id"],
        department=filters["department"],
        group_by=filters["group_by"],
        work_start=current_app.config.get("ATTENDANCE_WORK_START", DEFAULT_WORK_START),
        company_name=current_app.config.get("COMPANY_NAME", DEFAULT_COMPANY),
    )


@attendance_stats_bp.route("/stats")
@api_auth_required
def stats_report():
    """Reporte de asistencia (presentes/ausentes/retardos/incapacidades/vacaciones)."""
    try:
        report = _compute_report()
    except StatsValidationError as exc:
        return jsonify({"error": str(exc)}), 400
    return jsonify(report)


@attendance_stats_bp.route("/stats/export")
@api_auth_required
def stats_export():
    """Exportar el reporte de asistencia a CSV o Excel con los mismos filtros."""
    try:
        report = _compute_report()
    except StatsValidationError as exc:
        return jsonify({"error": str(exc)}), 400

    format_type = request.args.get("format", "csv").lower()
    label_columns = _LABEL_COLUMNS[report["group_by"]]
    headers = [header for _, header in label_columns] + [header for _, header in _NUMERIC_COLUMNS]
    export_rows = _build_export_rows(report["rows"], report["group_by"])
    export_rows.append(_total_export_row(report["totals"], report["group_by"]))

    if format_type == "xlsx":
        return _export_xlsx(headers, export_rows)
    return _export_csv(headers, export_rows)


def _build_export_rows(rows: list[dict], group_by: str) -> list[list]:
    label_keys = [key for key, _ in _LABEL_COLUMNS[group_by]]
    numeric_keys = [key for key, _ in _NUMERIC_COLUMNS]
    return [
        [row.get(key) for key in label_keys] + [row.get(key) for key in numeric_keys]
        for row in rows
    ]


def _total_export_row(totals: dict, group_by: str) -> list:
    label_keys = [key for key, _ in _LABEL_COLUMNS[group_by]]
    labels = ["TOTAL"] + [""] * (len(label_keys) - 1)
    return labels + [totals.get(key) for key, _ in _NUMERIC_COLUMNS]


def _export_csv(headers: list[str], rows: list[list]) -> Response:
    """Exportar a CSV (BOM utf-8-sig para compatibilidad Excel)."""
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)
    for row in rows:
        writer.writerow(["" if value is None else value for value in row])
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reporte_asistencia_{timestamp}.csv"
    return send_file(
        io.BytesIO(output.getvalue().encode("utf-8-sig")),
        mimetype="text/csv; charset=utf-8",
        as_attachment=True,
        download_name=filename,
    )


def _export_xlsx(headers: list[str], rows: list[list]) -> Response:
    """Exportar a Excel (XLSX)."""
    wb = Workbook()
    ws = wb.active
    ws.title = "Reporte Asistencia"

    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = cell.font.copy(bold=True)

    for row_idx, row in enumerate(rows, 2):
        for col, value in enumerate(row, 1):
            ws.cell(row=row_idx, column=col, value=value if value is not None else None)

    widths = [max(len(str(header)) + 4, 14) for header in headers]
    for idx, width in enumerate(widths, 1):
        ws.column_dimensions[get_column_letter(idx)].width = width

    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    filename = f"reporte_asistencia_{timestamp}.xlsx"
    return send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
