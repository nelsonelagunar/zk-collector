"""
Attendance Routes - WebGUI
Rutas para visualización y exportación de registros de asistencia
"""

import csv
import io
from datetime import datetime

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)
from openpyxl import Workbook
from openpyxl.utils import get_column_letter

attendance_bp = Blueprint('attendance', __name__)


def get_buffer_repo():
    """Obtener BufferRepository desde current_app"""
    return current_app.buffer_repo


def get_webgui_db():
    """Obtener Database (webgui.db) desde current_app"""
    return current_app.db


@attendance_bp.route('/')
def list_attendance():
    """Página principal de asistencia - renderiza template"""
    return render_template('attendance/list.html')


@attendance_bp.route('/api/devices')
def api_devices():
    """API para obtener lista de dispositivos para el select de filtro"""
    db = get_webgui_db()
    # Usar columnas reales: ip, enabled (no address, is_enabled)
    devices = db.fetch_all(
        "SELECT id, name, ip, enabled FROM devices WHERE enabled = 1 ORDER BY name"
    )
    return jsonify({'devices': devices})


@attendance_bp.route('/api/attendance')
def api_attendance():
    """
    API paginada con filtros para registros de asistencia

    Query params:
    - page: página (default 1)
    - per_page: registros por página (default 50, max 200)
    - start_date: fecha inicio ISO (YYYY-MM-DD)
    - end_date: fecha fin ISO (YYYY-MM-DD)
    - user_id: filtro por user_id
    - device_ip: filtro por IP de dispositivo
    - status: filtro por status (0-5)
    - punch_type: filtro por tipo de marca
    - synced: filtro por sincronizado (0/1)
    - sort: campo para ordenar
    - order: asc/desc
    """
    buffer_repo = get_buffer_repo()
    db = get_webgui_db()

    # Parámetros de paginación
    page = max(1, request.args.get('page', 1, type=int))
    per_page = min(max(10, request.args.get('per_page', 50, type=int)), 200)
    offset = (page - 1) * per_page

    # Parámetros de filtro
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    user_id = request.args.get('user_id', '')
    device_ip = request.args.get('device_ip', '')
    status = request.args.get('status', '')
    punch_type = request.args.get('punch_type', '')
    synced = request.args.get('synced', '')
    sort = request.args.get('sort', 'timestamp')
    order = request.args.get('order', 'desc')

    # Validar sort field
    allowed_sorts = ['id', 'user_id', 'timestamp', 'status', 'device_ip', 'punch_type', 'synced']
    if sort not in allowed_sorts:
        sort = 'timestamp'
    if order.lower() not in ['asc', 'desc']:
        order = 'desc'

    # Construir WHERE clause
    where_conditions = []
    params = []

    if start_date:
        where_conditions.append("timestamp >= ?")
        params.append(start_date + " 00:00:00")
    if end_date:
        where_conditions.append("timestamp <= ?")
        params.append(end_date + " 23:59:59")
    if user_id:
        where_conditions.append("user_id = ?")
        params.append(user_id)
    if device_ip:
        where_conditions.append("device_ip = ?")
        params.append(device_ip)
    if status != '':
        where_conditions.append("status = ?")
        params.append(int(status))
    if punch_type:
        where_conditions.append("punch_type = ?")
        params.append(punch_type)
    if synced != '':
        where_conditions.append("synced = ?")
        params.append(int(synced))

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""

    # Contar total
    count_query = f"SELECT COUNT(*) FROM attendance_records {where_clause}"
    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(count_query, params)
        total = cursor.fetchone()[0]

    # Obtener registros paginados
    data_query = f"""
        SELECT id, user_id, timestamp, status, device_ip, punch_type, synced
        FROM attendance_records
        {where_clause}
        ORDER BY {sort} {order.upper()}
        LIMIT ? OFFSET ?
    """
    params_with_pagination = params + [per_page, offset]

    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(data_query, params_with_pagination)
        rows = cursor.fetchall()

    # Enriquecer con nombres de usuario desde device_users (webgui.db)
    user_names = {}
    if rows:
        user_ids = list(set(row['user_id'] for row in rows))
        if user_ids:
            # SQLite doesn't support row-value IN, use individual placeholders
            placeholders = ','.join('?' * len(user_ids))
            query = f"SELECT user_id, name FROM device_users WHERE user_id IN ({placeholders})"
            user_rows = db.fetch_all(query, tuple(user_ids))
            user_names = {row['user_id']: row['name'] for row in user_rows}

    records = []
    for row in rows:
        record = dict(row)
        record['user_name'] = user_names.get(record['user_id'], record['user_id'])
        records.append(record)

    total_pages = (total + per_page - 1) // per_page

    return jsonify({
        'records': records,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': total_pages,
            'has_next': page < total_pages,
            'has_prev': page > 1,
        },
        'filters': {
            'start_date': start_date,
            'end_date': end_date,
            'user_id': user_id,
            'device_ip': device_ip,
            'status': status,
            'punch_type': punch_type,
            'synced': synced,
            'sort': sort,
            'order': order,
        }
    })


@attendance_bp.route('/attendance/stats')
def attendance_stats():
    """Estadísticas rápidas de asistencia"""
    buffer_repo = get_buffer_repo()
    stats = buffer_repo.get_stats()

    # Agregar breakdown por estado
    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()

        # Por estado (punch_type)
        cursor.execute("""
            SELECT punch_type, COUNT(*) as count
            FROM attendance_records
            GROUP BY punch_type
        """)
        by_punch_type = {row['punch_type']: row['count'] for row in cursor.fetchall()}

        # Por dispositivo
        cursor.execute("""
            SELECT device_ip, COUNT(*) as count
            FROM attendance_records
            GROUP BY device_ip
        """)
        by_device = {row['device_ip']: row['count'] for row in cursor.fetchall()}

        # Por sincronizado
        cursor.execute("""
            SELECT synced, COUNT(*) as count
            FROM attendance_records
            GROUP BY synced
        """)
        by_synced = {row['synced']: row['count'] for row in cursor.fetchall()}

    stats['by_punch_type'] = by_punch_type
    stats['by_device'] = by_device
    stats['by_synced'] = by_synced

    return jsonify(stats)


def _build_attendance_query(params: dict) -> tuple[str, list]:
    """Construir query base con filtros para export"""
    where_conditions = []
    query_params = []

    if params.get('start_date'):
        where_conditions.append("timestamp >= ?")
        query_params.append(params['start_date'] + " 00:00:00")
    if params.get('end_date'):
        where_conditions.append("timestamp <= ?")
        query_params.append(params['end_date'] + " 23:59:59")
    if params.get('user_id'):
        where_conditions.append("user_id = ?")
        query_params.append(params['user_id'])
    if params.get('device_ip'):
        where_conditions.append("device_ip = ?")
        query_params.append(params['device_ip'])
    if params.get('status') != '':
        where_conditions.append("status = ?")
        query_params.append(int(params['status']))
    if params.get('punch_type'):
        where_conditions.append("punch_type = ?")
        query_params.append(params['punch_type'])
    if params.get('synced') != '':
        where_conditions.append("synced = ?")
        query_params.append(int(params['synced']))

    where_clause = "WHERE " + " AND ".join(where_conditions) if where_conditions else ""
    return where_clause, query_params


@attendance_bp.route('/export')
def export_attendance():
    """
    Exportar registros de asistencia a CSV o Excel

    Query params:
    - format: csv|xlsx (default csv)
    - mismos filtros que /api/attendance
    """
    buffer_repo = get_buffer_repo()
    db = get_webgui_db()

    format_type = request.args.get('format', 'csv').lower()

    # Recolectar filtros
    filter_params = {
        'start_date': request.args.get('start_date', ''),
        'end_date': request.args.get('end_date', ''),
        'user_id': request.args.get('user_id', ''),
        'device_ip': request.args.get('device_ip', ''),
        'status': request.args.get('status', ''),
        'punch_type': request.args.get('punch_type', ''),
        'synced': request.args.get('synced', ''),
    }

    where_clause, query_params = _build_attendance_query(filter_params)

    # Obtener todos los registros (sin paginación)
    query = f"""
        SELECT id, user_id, timestamp, status, device_ip, punch_type, synced
        FROM attendance_records
        {where_clause}
        ORDER BY timestamp DESC, id DESC
    """

    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(query, query_params)
        rows = cursor.fetchall()

    # Enriquecer con nombres de usuario
    user_names = {}
    if rows:
        user_ids = list(set(row['user_id'] for row in rows))
        if user_ids:
            placeholders = ','.join('?' * len(user_ids))
            user_query = f"SELECT user_id, name FROM device_users WHERE user_id IN ({placeholders})"
            user_rows = db.fetch_all(user_query, tuple(user_ids))
            user_names = {row['user_id']: row['name'] for row in user_rows}

    # Preparar datos para export
    export_data = []
    for row in rows:
        record = dict(row)
        record['user_name'] = user_names.get(record['user_id'], record['user_id'])
        record['synced_label'] = 'Sí' if record['synced'] else 'No'
        status_labels = {
            0: 'Entrada', 1: 'Salida', 2: 'Salida Comida',
            3: 'Entrada Comida', 4: 'Entrada Extra', 5: 'Salida Extra'
        }
        record['status_label'] = status_labels.get(record['status'], f'Status {record["status"]}')
        export_data.append(record)

    if format_type == 'xlsx':
        return _export_xlsx(export_data)
    else:
        return _export_csv(export_data)


def _export_csv(data: list[dict]) -> send_file:
    """Exportar a CSV"""
    output = io.StringIO()

    if not data:
        output.write('ID,Usuario,Fecha/Hora,Estado,Dispositivo,Tipo Marca,Sincronizado\n')
    else:
        writer = csv.DictWriter(output, fieldnames=[
            'id', 'user_name', 'timestamp', 'status_label',
            'device_ip', 'punch_type', 'synced_label'
        ])
        writer.writeheader()
        for row in data:
            writer.writerow({
                'id': row['id'],
                'user_name': row['user_name'],
                'timestamp': row['timestamp'],
                'status_label': row['status_label'],
                'device_ip': row['device_ip'],
                'punch_type': row['punch_type'],
                'synced_label': row['synced_label'],
            })

    output.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'asistencia_{timestamp}.csv'

    # Use utf-8-sig to include BOM for Excel compatibility
    return send_file(
        io.BytesIO(output.getvalue().encode('utf-8-sig')),
        mimetype='text/csv; charset=utf-8',
        as_attachment=True,
        download_name=filename
    )


def _export_xlsx(data: list[dict]) -> send_file:
    """Exportar a Excel (XLSX)"""
    wb = Workbook()
    ws = wb.active
    ws.title = "Asistencia"

    # Headers
    headers = ['ID', 'Usuario', 'Fecha/Hora', 'Estado', 'Dispositivo', 'Tipo Marca', 'Sincronizado']
    for col, header in enumerate(headers, 1):
        cell = ws.cell(row=1, column=col, value=header)
        cell.font = cell.font.copy(bold=True)

    # Data
    for row_idx, record in enumerate(data, 2):
        ws.cell(row=row_idx, column=1, value=record['id'])
        ws.cell(row=row_idx, column=2, value=record['user_name'])
        ws.cell(row=row_idx, column=3, value=record['timestamp'])
        ws.cell(row=row_idx, column=4, value=record['status_label'])
        ws.cell(row=row_idx, column=5, value=record['device_ip'])
        ws.cell(row=row_idx, column=6, value=record['punch_type'])
        ws.cell(row=row_idx, column=7, value=record['synced_label'])

    # Ajustar anchos de columna
    column_widths = [8, 20, 22, 18, 18, 18, 12]
    for i, width in enumerate(column_widths, 1):
        ws.column_dimensions[get_column_letter(i)].width = width

    # Guardar a BytesIO
    output = io.BytesIO()
    wb.save(output)
    output.seek(0)

    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    filename = f'asistencia_{timestamp}.xlsx'

    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=filename
    )
