"""
Attendance Routes - Consulta y exportación de registros de asistencia
"""

import io
from datetime import datetime

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_file,
    session,
    url_for,
)
from openpyxl import Workbook
from openpyxl.cell import WriteOnlyCell
from openpyxl.styles import Alignment, Border, Font, PatternFill, Side
from openpyxl.utils import get_column_letter

attendance_bp = Blueprint("attendance", __name__)


@attendance_bp.route("/attendance")
def attendance_page():
    """Página de consulta de asistencia"""
    if "user_id" not in session:
        return redirect(url_for("auth.login"))
    return render_template("attendance/list.html")


@attendance_bp.route("/api/attendance")
def api_attendance():
    """API para obtener registros de asistencia con paginación y filtros"""
    # Verificar autenticación
    if "user_id" not in session:
        return jsonify({"error": "No autenticado"}), 401

    # Parámetros de filtro
    start_date = request.args.get("start_date", "")
    end_date = request.args.get("end_date", "")
    device_ip = request.args.get("device_ip", "")
    user_id = request.args.get("user_id", "")
    page = int(request.args.get("page", 1))
    per_page = min(int(request.args.get("per_page", 50)), 500)

    offset = (page - 1) * per_page

    repo = current_app.buffer_repo
    if not repo:
        return jsonify({"error": "Buffer repository no disponible"}), 503

    records = repo.get_attendance_records(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        device_ip=device_ip if device_ip else None,
        user_id=user_id if user_id else None,
        limit=per_page,
        offset=offset,
    )

    total = repo.get_attendance_count(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        device_ip=device_ip if device_ip else None,
        user_id=user_id if user_id else None,
    )

    return jsonify(
        {
            "records": records,
            "pagination": {
                "page": page,
                "per_page": per_page,
                "total": total,
                "total_pages": (total + per_page - 1) // per_page,
            },
        }
    )


@attendance_bp.route("/attendance/export")
@attendance_bp.route("/api/export/attendance")
def export_attendance():
    """Exportar asistencia a CSV o Excel con streaming para datasets grandes

    Query params:
        start: Fecha inicio (YYYY-MM-DD)
        end: Fecha fin (YYYY-MM-DD)
        device_ip: IP del dispositivo (opcional)
        user_id: ID del empleado (opcional)
        format: csv|xlsx
    """
    # Verificar autenticación
    if "user_id" not in session:
        return jsonify({"error": "No autenticado"}), 401

    # Parámetros (accept both start/end and start_date/end_date for backward compat)
    format_type = request.args.get("format", "csv").lower()
    start = request.args.get("start", request.args.get("start_date", ""))
    end = request.args.get("end", request.args.get("end_date", ""))
    device_ip = request.args.get("device_ip", "")
    user_id = request.args.get("user_id", "")

    if format_type not in ("csv", "xlsx"):
        return jsonify({"error": "Formato no soportado. Use csv o xlsx"}), 400

    repo = current_app.buffer_repo
    if not repo:
        return jsonify({"error": "Buffer repository no disponible"}), 503

    total_records = repo.get_attendance_count(
        start_date=start if start else None,
        end_date=end if end else None,
        device_ip=device_ip if device_ip else None,
        user_id=user_id if user_id else None,
    )

    # Generar nombre de archivo
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    date_suffix = ""
    if start or end:
        sd = start or "inicio"
        ed = end or "fin"
        date_suffix = f"_{sd}_a_{ed}"
    if device_ip:
        date_suffix += f"_dev-{device_ip.replace('.', '-')}"
    if user_id:
        date_suffix += f"_emp-{user_id}"

    filename = f"asistencia{date_suffix}_{timestamp}.{format_type}"

    if format_type == "csv":
        return _export_csv_streaming(repo, start, end, device_ip, user_id, filename, total_records)
    else:
        return _export_xlsx_streaming(repo, start, end, device_ip, user_id, filename, total_records)


def _export_csv_streaming(repo, start_date, end_date, device_ip, user_id, filename, total_records):
    """Exportar CSV con streaming para datasets grandes

    UTF-8 BOM included for Excel compatibility with special characters.
    """

    def generate():
        # UTF-8 BOM for Excel compatibility
        yield "﻿"
        # Headers
        yield "ID,Usuario,Fecha/Hora,Estado,Dispositivo,Tipo Marca,Sincronizado\n"

        chunk_size = 1000
        for chunk in repo.stream_attendance_records(
            start_date=start_date if start_date else None,
            end_date=end_date if end_date else None,
            device_ip=device_ip if device_ip else None,
            user_id=user_id if user_id else None,
            chunk_size=chunk_size,
        ):
            for record in chunk:
                status_text = _status_to_text(record["status"])
                punch_text = record["punch_type"] or ""
                synced_text = "Sí" if record["synced"] else "No"

                row = [
                    str(record["id"]),
                    record["user_id"],
                    record["timestamp"],
                    status_text,
                    record["device_ip"],
                    punch_text,
                    synced_text,
                ]
                yield (
                    ",".join(f'"{str(cell).replace(chr(34), chr(34) + chr(34))}"' for cell in row)
                    + "\n"
                )

    response = Response(generate(), mimetype="text/csv; charset=utf-8")
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["X-Total-Records"] = str(total_records)
    return response


def _export_xlsx_streaming(repo, start_date, end_date, device_ip, user_id, filename, total_records):
    """Exportar Excel (xlsx) - para datasets grandes usa openpyxl write_only mode"""
    wb = Workbook(write_only=True)
    ws = wb.create_sheet("Asistencia")

    # Estilos
    header_font = Font(bold=True, color="FFFFFF")
    header_fill = PatternFill(start_color="2563EB", end_color="2563EB", fill_type="solid")
    thin_border = Border(
        left=Side(style="thin"),
        right=Side(style="thin"),
        top=Side(style="thin"),
        bottom=Side(style="thin"),
    )

    # Headers
    headers = ["ID", "Usuario", "Fecha/Hora", "Estado", "Dispositivo", "Tipo Marca", "Sincronizado"]
    header_row = []
    for _col_idx, header in enumerate(headers, 1):
        cell = WriteOnlyCell(ws, value=header)
        cell.font = header_font
        cell.fill = header_fill
        cell.alignment = Alignment(horizontal="center")
        cell.border = thin_border
        header_row.append(cell)
    ws.append(header_row)

    # Datos
    chunk_size = 1000
    for chunk in repo.stream_attendance_records(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        device_ip=device_ip if device_ip else None,
        user_id=user_id if user_id else None,
        chunk_size=chunk_size,
    ):
        for record in chunk:
            status_text = _status_to_text(record["status"])
            punch_text = record["punch_type"] or ""
            synced_text = "Sí" if record["synced"] else "No"

            row_data = [
                record["id"],
                record["user_id"],
                record["timestamp"],
                status_text,
                record["device_ip"],
                punch_text,
                synced_text,
            ]

            row_cells = []
            for _col_idx, value in enumerate(row_data, 1):
                cell = WriteOnlyCell(ws, value=value)
                cell.border = thin_border
                row_cells.append(cell)
            ws.append(row_cells)

    # Ajustar anchos de columna
    column_widths = [10, 20, 22, 15, 18, 15, 15]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Guardar a buffer
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    response = send_file(
        output,
        mimetype="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        as_attachment=True,
        download_name=filename,
    )
    response.headers["X-Total-Records"] = str(total_records)
    return response


def _status_to_text(status: int) -> str:
    """Convertir código de estado a texto legible"""
    status_map = {
        0: "Entrada",
        1: "Salida",
        2: "Entrada Almuerzo",
        3: "Salida Almuerzo",
        4: "Horas Extra Entrada",
        5: "Horas Extra Salida",
    }
    return status_map.get(status, f"Desconocido ({status})")
