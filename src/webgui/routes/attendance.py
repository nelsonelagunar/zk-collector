"""
Attendance Routes - Listado y exportación de registros de asistencia
"""

import csv
from datetime import datetime, timedelta
from io import BytesIO, StringIO

from flask import (
    Blueprint,
    current_app,
    jsonify,
    render_template,
    request,
    send_file,
)

attendance_bp = Blueprint('attendance', __name__)


@attendance_bp.route('/attendance')
def list_attendance():
    """Página de listado de asistencia con filtros y paginación"""
    db = current_app.db

    # Obtener dispositivos para el filtro
    devices = db.fetch_all(
        "SELECT id, name, address FROM devices WHERE is_enabled = 1 ORDER BY name"
    )

    return render_template('attendance/list.html', devices=devices)


@attendance_bp.route('/api/attendance')
def api_attendance():
    """API JSON con paginación y filtros para DataTables/tabla"""
    buffer_repo = current_app.buffer_repo

    # Parámetros de paginación
    page = int(request.args.get('page', 1))
    per_page = int(request.args.get('per_page', 25))
    offset = (page - 1) * per_page

    # Filtros
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = request.args.get('user_id')
    device_ip = request.args.get('device_ip')

    # Construir query
    conditions = []
    params = []

    # Unir con devices para obtener IP/nombre
    base_query = """
        SELECT ar.*, d.name as device_name, d.address as device_address
        FROM attendance_records ar
        LEFT JOIN devices d ON ar.device_ip = d.address
        WHERE 1=1
    """

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            conditions.append("ar.timestamp >= ?")
            params.append(dt_from.isoformat())
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
            conditions.append("ar.timestamp < ?")
            params.append(dt_to.isoformat())
        except ValueError:
            pass

    if user_id:
        conditions.append("ar.user_id = ?")
        params.append(user_id)

    if device_ip:
        conditions.append("ar.device_ip = ?")
        params.append(device_ip)

    where_clause = " AND ".join(conditions) if conditions else ""

    # Count total
    count_query = f"SELECT COUNT(*) as total FROM ({base_query} {where_clause})"

    # Query con paginación
    data_query = (
        f"{base_query} {where_clause} "
        "ORDER BY ar.timestamp DESC, ar.id DESC LIMIT ? OFFSET ?"
    )
    params.extend([per_page, offset])

    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()

        # Total count
        cursor.execute(count_query, params[:-2] if where_clause else [])
        total = cursor.fetchone()['total']

        # Data
        cursor.execute(data_query, params)
        rows = cursor.fetchall()

    records = [dict(row) for row in rows]

    # Add user_name from device_users table (webgui.db) via in-memory lookup
    if records:
        # Build lookup key set: (device_ip, user_id)
        user_keys = [
            (r["device_ip"], r["user_id"])
            for r in records
            if r.get("device_ip") and r.get("user_id")
        ]

        # Query device_users from webgui.db
        db = current_app.db
        if user_keys:
            # SQLite doesn't support row-value IN syntax; build OR conditions
            conditions = " OR ".join(
                ["(device_ip=? AND user_id=?)"] * len(user_keys)
            )
            params = []
            for k in user_keys:
                params.extend([k[0], k[1]])

            query = f"""
                SELECT device_ip, user_id, name
                FROM device_users
                WHERE {conditions}
            """
            user_rows = db.fetch_all(query, tuple(params))
            user_lookup = {
                (r["device_ip"], r["user_id"]): r["name"]
                for r in user_rows
            }

            # Merge user_name into records
            for record in records:
                key = (record.get("device_ip"), record.get("user_id"))
                record["user_name"] = user_lookup.get(key, "")

    return jsonify({
        'data': records,
        'pagination': {
            'page': page,
            'per_page': per_page,
            'total': total,
            'total_pages': (total + per_page - 1) // per_page
        }
    })


@attendance_bp.route('/attendance/export')
def export_attendance():
    """Exportar CSV/Excel con streaming"""
    buffer_repo = current_app.buffer_repo

    format_type = request.args.get('format', 'csv')

    # Filtros (mismos que API)
    date_from = request.args.get('date_from')
    date_to = request.args.get('date_to')
    user_id = request.args.get('user_id')
    device_ip = request.args.get('device_ip')

    conditions = []
    params = []

    base_query = """
        SELECT ar.*, d.name as device_name
        FROM attendance_records ar
        LEFT JOIN devices d ON ar.device_ip = d.address
        WHERE 1=1
    """

    if date_from:
        try:
            dt_from = datetime.fromisoformat(date_from)
            conditions.append("ar.timestamp >= ?")
            params.append(dt_from.isoformat())
        except ValueError:
            pass

    if date_to:
        try:
            dt_to = datetime.fromisoformat(date_to) + timedelta(days=1)
            conditions.append("ar.timestamp < ?")
            params.append(dt_to.isoformat())
        except ValueError:
            pass

    if user_id:
        conditions.append("ar.user_id = ?")
        params.append(user_id)

    if device_ip:
        conditions.append("ar.device_ip = ?")
        params.append(device_ip)

    where_clause = " AND ".join(conditions) if conditions else ""
    data_query = f"{base_query} {where_clause} ORDER BY ar.timestamp DESC"

    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(data_query, params)
        rows = cursor.fetchall()

    records = [dict(row) for row in rows]

    if format_type == 'csv':
        output = StringIO()
        writer = csv.writer(output)

        # Headers
        writer.writerow([
            'ID', 'Usuario', 'Fecha/Hora', 'Estado',
            'Dispositivo', 'Tipo Marca', 'Sincronizado'
        ])

        for r in records:
            status_map = {0: 'Entrada', 1: 'Salida', 2: 'Otro'}
            writer.writerow([
                r['id'],
                r['user_id'],
                r['timestamp'],
                status_map.get(r['status'], str(r['status'])),
                r.get('device_name', r['device_ip']),
                r['punch_type'] or 'N/A',
                'Sí' if r['synced'] else 'No'
            ])

        output.seek(0)
        return send_file(
            BytesIO(output.getvalue().encode('utf-8')),
            mimetype='text/csv',
            as_attachment=True,
            download_name=f'attendance_{datetime.now().strftime("%Y%m%d_%H%M%S")}.csv'
        )

    # TODO: Excel format
    return jsonify({'error': 'Excel export not yet implemented'}), 501
