from flask import Blueprint, request, jsonify, current_app
from functools import wraps

# Assuming login_required defined elsewhere
from ..middleware.auth import login_required

employees_bp = Blueprint('employees', __name__)

@employees_bp.route('/')
@login_required
def list_employees():
    db = current_app.db
    # Filters
    status = request.args.get('status')
    department = request.args.get('department')
    search = request.args.get('search')
    limit = int(request.args.get('limit', 100))
    offset = int(request.args.get('offset', 0))
    params = []
    clauses = []
    if status:
        clauses.append("status = ?")
        params.append(status)
    if department:
        clauses.append("department = ?")
        params.append(department)
    if search:
        clauses.append("(employee_code LIKE ? OR first_name LIKE ? OR last_name LIKE ?)")
        like = f"%{search}%"
        params.extend([like, like, like])
    where = " AND ".join(clauses) if clauses else "1"
    query = f"SELECT * FROM employees WHERE {where} LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    rows = db.fetch_all(query, tuple(params))
    return jsonify(rows)

@employees_bp.route('/', methods=['POST'])
@login_required
def create_employee():
    data = request.get_json() or {}
    required = ['employee_code','first_name','last_name']
    for field in required:
        if field not in data:
            return jsonify({'error': f'{field} required'}), 400
    # check unique
    existing = current_app.db.fetch_one('SELECT id FROM employees WHERE employee_code = ?', (data['employee_code'],))
    if existing:
        return jsonify({'error':'employee_code already exists'}),400
    fields = ['employee_code','first_name','last_name','email','phone','department','position','hire_date','status','notes']
    values=[data.get(f) for f in fields]
    placeholders=', '.join('?' for _ in fields)
    insert_sql=f"INSERT INTO employees ({', '.join(fields)}) VALUES ({placeholders})"
    try:
        current_app.db.execute(insert_sql, tuple(values))
    except Exception as e:
        return jsonify({'error': str(e)}),500
    return jsonify({'message':'created'}),201

@employees_bp.route('/<int:emp_id>', methods=['PUT'])
@login_required
def update_employee(emp_id):
    data = request.get_json() or {}
    allowed = ['first_name','last_name','email','phone','department','position','hire_date','status','notes']
    set_clauses=[]
    params=[]
    for f in allowed:
        if f in data:
            set_clauses.append(f"{f} = ?")
            params.append(data[f])
    if not set_clauses:
        return jsonify({'error':'no fields to update'}),400
    params.append(emp_id)
    update_sql=f"UPDATE employees SET {', '.join(set_clauses)} WHERE id = ?"
    current_app.db.execute(update_sql, tuple(params))
    return jsonify({'message':'updated'}),200

@employees_bp.route('/<int:emp_id>', methods=['DELETE'])
@login_required
def delete_employee(emp_id):
    # soft delete by status
    current_app.db.execute('UPDATE employees SET status = ? WHERE id = ?', ('inactive', emp_id))
    return jsonify({'message':'deleted'}),200

# Device links
@employees_bp.route('/<int:emp_id>/device-links', methods=['POST'])
@login_required
def add_device_link(emp_id):
    data=request.get_json() or {}
    required=['device_serial','device_user_id']
    for f in required:
        if f not in data:
            return jsonify({'error':f'{f} required'}),400
    # insert
    try:
        current_app.db.execute('INSERT INTO employee_device_links (employee_id,device_serial,device_user_id) VALUES (?,?,?)', (emp_id,data['device_serial'],data['device_user_id']))
    except Exception as e:
        return jsonify({'error':str(e)}),400
    return jsonify({'message':'linked'}),201

@employees_bp.route('/<int:emp_id>/device-links/<int:link_id>', methods=['DELETE'])
@login_required
def delete_device_link(emp_id, link_id):
    current_app.db.execute('DELETE FROM employee_device_links WHERE id = ? AND employee_id = ?', (link_id, emp_id))
    return jsonify({'message':'unlinked'}),200
