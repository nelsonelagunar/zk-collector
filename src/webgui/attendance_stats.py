"""
Attendance stats service - Reportes de asistencia (MYK-241)

Computo de KPIs de asistencia por periodo, agrupados por colaborador,
departamento o empresa. Contrato consumido por la API REST
`/api/attendance/stats` y su export CSV/Excel (`/api/attendance/stats/export`).

Reglas (documentadas tambien en docs/attendance_stats.md):
- Todo el computo se hace sobre dias habiles (Lunes-Viernes) del periodo.
- days_expected   : habiles en [max(start_date, hire_date), end_date].
- days_present    : habiles con >= 1 registro de asistencia del colaborador.
- days_incapacity : habiles cubiertos por `medical_leaves` activas y NO
                    presentados (el dia trabajado tiene precedencia).
- days_vacation   : habiles cubiertos por vacaciones aprobadas. Hoy es 0
                    porque no existe fuente de datos (modulo de vacaciones no
                    implementado); el campo ya forma parte del contrato.
- days_absent     : max(0, expected - present - incapacity - vacation).
- late_arrivals   : dias presentados cuyo primer punch de entrada (status=0)
                    ocurre despues de la hora default de inicio
                    (config `ATTENDANCE_WORK_START`, default 09:00:00).
- punctuality_pct : 100 * (present - late) / present; null si present == 0.
- absenteeism_pct : 100 * absent / expected; null si expected == 0.
- Los registros que no mapean a un colaborador activo (sin
  `employee_device_links`) se cuentan en `meta.unlinked_records`.
"""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from .database import Database

DEFAULT_WORK_START = "09:00:00"
DEFAULT_COMPANY = "default"
NO_DEPARTMENT = "Sin departamento"
VALID_GROUP_BY = ("employee", "department", "company")

ENTRADA_STATUS = 0

_NUMERIC_KEYS = (
    "days_expected",
    "days_present",
    "days_absent",
    "days_incapacity",
    "days_vacation",
    "late_arrivals",
)


class StatsValidationError(ValueError):
    """Parametros invalidos para el reporte de asistencia."""


def parse_iso_date(value: object, field: str) -> date:
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        msg = f"{field} invalida: {value!r} (formato esperado YYYY-MM-DD)"
        raise StatsValidationError(msg) from exc


def parse_work_start(value: object) -> tuple[int, int, int]:
    text = str(value if value is not None else "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return (parsed.hour, parsed.minute, parsed.second)
    msg = f"work_start invalido: {value!r} (formato esperado HH:MM o HH:MM:SS)"
    raise StatsValidationError(msg)


def _business_days(start: date, end: date) -> list[date]:
    days: list[date] = []
    current = start
    while current <= end:
        if current.weekday() < 5:
            days.append(current)
        current += timedelta(days=1)
    return days


def _normalize_timestamp(value: object) -> datetime | None:
    """Acepta 'YYYY-MM-DD', 'YYYY-MM-DD HH:MM:SS', ISO con 'T' y sin segundos."""
    if isinstance(value, datetime):
        return value
    text = str(value if value is not None else "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def _pct(part: int, total: int) -> float | None:
    if total <= 0:
        return None
    return round(100.0 * part / total, 1)


def _aggregate(rows: list[dict[str, Any]]) -> dict[str, Any]:
    out: dict[str, Any] = {key: sum(r[key] for r in rows) for key in _NUMERIC_KEYS}
    out["punctuality_pct"] = _pct(out["days_present"] - out["late_arrivals"], out["days_present"])
    out["absenteeism_pct"] = _pct(out["days_absent"], out["days_expected"])
    return out


def compute_attendance_stats(
    db: Database,
    buffer_repo: Any,
    start_date: str,
    end_date: str,
    employee_id: int | None = None,
    department: str | None = None,
    group_by: str = "employee",
    work_start: str = DEFAULT_WORK_START,
    company_name: str = DEFAULT_COMPANY,
) -> dict[str, Any]:
    """Computar el reporte de asistencia del periodo con los filtros dados."""
    if group_by not in VALID_GROUP_BY:
        msg = f"group_by invalido: {group_by!r} (opciones: employee|department|company)"
        raise StatsValidationError(msg)

    start = parse_iso_date(start_date, "start_date")
    end = parse_iso_date(end_date, "end_date")
    if start > end:
        raise StatsValidationError("start_date no puede ser posterior a end_date")
    work_start_t = parse_work_start(work_start)

    # 1. Colaboradores activos con filtros
    query = (
        "SELECT id, employee_code, first_name, last_name, department, hire_date "
        "FROM employees WHERE status = 'active'"
    )
    params: list[Any] = []
    if employee_id is not None:
        query += " AND id = ?"
        params.append(employee_id)
    if department:
        query += " AND department = ?"
        params.append(department)
    query += " ORDER BY last_name, first_name"
    employees = db.fetch_all(query, tuple(params))

    # 2. Mapa (device_serial, device_user_id) -> employee_id
    emp_by_link = {
        (row["device_serial"], str(row["device_user_id"])): row["employee_id"]
        for row in db.fetch_all(
            "SELECT edl.device_serial, edl.device_user_id, edl.employee_id "
            "FROM employee_device_links edl "
            "JOIN employees e ON e.id = edl.employee_id "
            "WHERE e.status = 'active'"
        )
    }
    serial_by_ip = {
        row["address"]: row["serial_number"]
        for row in db.fetch_all(
            "SELECT address, serial_number FROM devices WHERE serial_number IS NOT NULL"
        )
    }

    # 3. Registros de asistencia del periodo -> presencia y primer entrada
    present_days: dict[int, set[date]] = defaultdict(set)
    first_entrada: dict[int, dict[date, tuple[int, int, int]]] = defaultdict(dict)
    unlinked_records = 0

    # substr(timestamp,1,10) soporta ambos formatos 'YYYY-MM-DD HH:MM:SS' e ISO 'T'
    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, timestamp, status, device_ip FROM attendance_records "
            "WHERE substr(timestamp, 1, 10) BETWEEN ? AND ? AND annulled = 0",
            (start.isoformat(), end.isoformat()),
        )
        for row in cursor.fetchall():
            parsed = _normalize_timestamp(row["timestamp"])
            if parsed is None:
                continue
            serial = serial_by_ip.get(row["device_ip"])
            linked_id = emp_by_link.get((serial, str(row["user_id"]))) if serial else None
            if linked_id is None:
                unlinked_records += 1
                continue
            day = parsed.date()
            present_days[linked_id].add(day)
            if row["status"] == ENTRADA_STATUS:
                punch_time = (parsed.hour, parsed.minute, parsed.second)
                current = first_entrada[linked_id].get(day)
                if current is None or punch_time < current:
                    first_entrada[linked_id][day] = punch_time

    # 4. Incapacidades activas que traslapan el periodo (dias habiles)
    leave_days: dict[int, set[date]] = defaultdict(set)
    for leave in db.fetch_all(
        "SELECT employee_id, start_date, end_date FROM medical_leaves "
        "WHERE status = 'active' AND start_date <= ? AND end_date >= ?",
        (end.isoformat(), start.isoformat()),
    ):
        leave_start = _normalize_timestamp(leave["start_date"])
        leave_end = _normalize_timestamp(leave["end_date"])
        if leave_start is None or leave_end is None:
            continue
        for day in _business_days(max(leave_start.date(), start), min(leave_end.date(), end)):
            leave_days[leave["employee_id"]].add(day)

    # 5. KPIs por colaborador
    per_employee: list[dict[str, Any]] = []
    for emp in employees:
        emp_id = emp["id"]
        hire = _normalize_timestamp(emp["hire_date"])
        effective_start = start
        if hire is not None and hire.date() > start:
            effective_start = hire.date()
        expected_set = set(_business_days(effective_start, end))
        attended = present_days.get(emp_id, set()) & expected_set
        days_present = len(attended)

        late_arrivals = 0
        for day in attended:
            entrada_time = first_entrada.get(emp_id, {}).get(day)
            if entrada_time is not None and entrada_time > work_start_t:
                late_arrivals += 1

        days_incapacity = len(
            (leave_days.get(emp_id, set()) & expected_set) - present_days.get(emp_id, set())
        )
        days_vacation = 0
        days_absent = max(0, len(expected_set) - days_present - days_incapacity - days_vacation)

        full_name = (
            f"{(emp['first_name'] or '').strip()} {(emp['last_name'] or '').strip()}".strip()
        )
        per_employee.append(
            {
                "employee_id": emp_id,
                "employee_code": emp["employee_code"],
                "employee_name": full_name or str(emp["employee_code"]),
                "department": emp["department"] or NO_DEPARTMENT,
                "days_expected": len(expected_set),
                "days_present": days_present,
                "days_absent": days_absent,
                "days_incapacity": days_incapacity,
                "days_vacation": days_vacation,
                "late_arrivals": late_arrivals,
                "punctuality_pct": _pct(days_present - late_arrivals, days_present),
                "absenteeism_pct": _pct(days_absent, len(expected_set)),
            }
        )

    # 6. Agrupacion
    if group_by == "employee":
        rows: list[dict[str, Any]] = list(per_employee)
    elif group_by == "department":
        by_department: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in per_employee:
            by_department[row["department"]].append(row)
        rows = [
            {"department": department, **_aggregate(department_rows)}
            for department, department_rows in sorted(by_department.items())
        ]
    else:
        rows = [{"company": company_name, **_aggregate(per_employee)}]

    return {
        "period": {"start_date": start.isoformat(), "end_date": end.isoformat()},
        "filters": {
            "start_date": start.isoformat(),
            "end_date": end.isoformat(),
            "employee_id": employee_id,
            "department": department,
            "group_by": group_by,
        },
        "group_by": group_by,
        "work_start": "{:02d}:{:02d}:{:02d}".format(*work_start_t),
        "rows": rows,
        "totals": _aggregate(per_employee),
        "meta": {
            "employees_total": len(employees),
            "unlinked_records": unlinked_records,
        },
    }
