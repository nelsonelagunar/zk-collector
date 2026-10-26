"""Portal del trabajador /mi-asistencia (MYK-425, MYK-410 item 7).

Servicio puro del portal de consulta del trabajador: obtiene SOLO las marcas
del empleado autenticado (via employee_device_links) y calcula el desglose
del periodo (dias presentados, retardos, horas trabajadas y horas extra).

Reglas de computo (documentadas tambien en docs/mi_asistencia.md):
- Periodo: [start_date, end_date], maximo 92 dias, end_date no futuro.
- Se consideran TODAS las marcas del periodo (incluidos fines de semana).
- worked  : por dia con >= 2 marcas, ultima marca - primera marca.
- extra   : max(0, worked - STANDARD_WORKDAY_HOURS) por dia (LFT 61/66:
            jornada diurna maximo 8 h). El motor de reglas completo es MYK-224.
- retardos: dias cuya primera entrada (status=0) ocurre despues de
            ATTENDANCE_WORK_START (default 09:00:00, mismo criterio que
            attendance_stats MYK-241).
- Dias con una sola marca no generan horas trabajadas ni extra.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta
from typing import Any

from .database import Database

STANDARD_WORKDAY_HOURS = 8.0
MAX_PERIOD_DAYS = 92
ENTRADA_STATUS = 0
DEFAULT_WORK_START = "09:00:00"

PUNCH_STATUS_LABELS = {
    0: "Entrada",
    1: "Salida",
    2: "Salida a comer",
    3: "Regreso de comer",
    4: "Entrada extra",
    5: "Salida extra",
}


class PortalValidationError(ValueError):
    """Parametros invalidos para la consulta del portal."""


def parse_iso_date(value: object, field: str) -> date:
    try:
        return datetime.strptime(str(value).strip(), "%Y-%m-%d").date()
    except ValueError as exc:
        msg = f"{field} invalida: {value!r} (formato esperado YYYY-MM-DD)"
        raise PortalValidationError(msg) from exc


def parse_period(
    start_value: object, end_value: object, today: date | None = None
) -> tuple[date, date]:
    """Valida el rango del periodo: formato ISO, orden y ventana maxima."""
    today = today or datetime.now().date()
    start = parse_iso_date(start_value, "start_date")
    end = parse_iso_date(end_value, "end_date")
    if start > end:
        raise PortalValidationError("start_date no puede ser posterior a end_date")
    if end > today:
        raise PortalValidationError("end_date no puede ser futura")
    if (end - start).days + 1 > MAX_PERIOD_DAYS:
        msg = f"el periodo no puede exceder {MAX_PERIOD_DAYS} dias"
        raise PortalValidationError(msg)
    return start, end


def default_period(today: date | None = None) -> tuple[date, date]:
    """Mes en curso: primer dia del mes -> hoy."""
    today = today or datetime.now().date()
    return today.replace(day=1), today


def parse_work_start(value: object) -> tuple[int, int, int]:
    text = str(value if value is not None else "").strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            parsed = datetime.strptime(text, fmt)
        except ValueError:
            continue
        return (parsed.hour, parsed.minute, parsed.second)
    msg = f"work_start invalido: {value!r} (formato esperado HH:MM o HH:MM:SS)"
    raise PortalValidationError(msg)


def normalize_timestamp(value: object) -> datetime | None:
    """Acepta 'YYYY-MM-DD HH:MM:SS', ISO con 'T' y sin segundos."""
    if isinstance(value, datetime):
        return value
    text = str(value if value is not None else "").strip().replace("T", " ")
    for fmt in ("%Y-%m-%d %H:%M:%S", "%Y-%m-%d %H:%M", "%Y-%m-%d"):
        try:
            return datetime.strptime(text, fmt)
        except ValueError:
            continue
    return None


def get_employee_link_pairs(db: Database, employee_id: int) -> list[tuple[str, str]]:
    """Pares (device_ip, user_id del reloj) vinculados al empleado."""
    rows = db.fetch_all(
        """
        SELECT d.address, edl.device_user_id
        FROM employee_device_links edl
        JOIN devices d ON d.serial_number = edl.device_serial
        WHERE edl.employee_id = ?
        """,
        (employee_id,),
    )
    return [(row["address"], str(row["device_user_id"])) for row in rows]


def fetch_own_records(
    buffer_repo: Any, pairs: list[tuple[str, str]], start: date, end: date
) -> list[dict[str, Any]]:
    """Marcas del periodo que pertenecen EXCLUSIVAMENTE a los pares del empleado."""
    if not pairs:
        return []

    clauses = " OR ".join(["(device_ip = ? AND user_id = ?)"] * len(pairs))
    params: list[Any] = []
    for ip, user_id in pairs:
        params.extend([ip, user_id])

    rows: list[dict[str, Any]] = []
    with buffer_repo.get_connection() as conn:
        cursor = conn.cursor()
        cursor.execute(
            "SELECT user_id, timestamp, status, device_ip, punch_type "
            "FROM attendance_records "
            f"WHERE substr(timestamp, 1, 10) BETWEEN ? AND ? AND ({clauses}) "
            "ORDER BY timestamp ASC",
            (start.isoformat(), end.isoformat(), *params),
        )
        for row in cursor.fetchall():
            parsed = normalize_timestamp(row["timestamp"])
            if parsed is None:
                continue
            rows.append(
                {
                    "timestamp": parsed,
                    "status": int(row["status"] or 0),
                    "punch_type": row["punch_type"],
                }
            )
    return rows


def build_day_rows(
    records: list[dict[str, Any]], work_start: str = DEFAULT_WORK_START
) -> list[dict[str, Any]]:
    """Agrupa las marcas por dia y calcula jornada y horas extra."""
    work_start_t = parse_work_start(work_start)
    by_day: dict[date, list[dict[str, Any]]] = {}
    for record in records:
        by_day.setdefault(record["timestamp"].date(), []).append(record)

    day_rows: list[dict[str, Any]] = []
    for day in sorted(by_day):
        marks = by_day[day]
        first = marks[0]["timestamp"]
        last = marks[-1]["timestamp"]
        first_entrada = next((m["timestamp"] for m in marks if m["status"] == ENTRADA_STATUS), None)

        worked_seconds = int((last - first).total_seconds()) if len(marks) >= 2 else 0
        extra_seconds = max(0, worked_seconds - int(STANDARD_WORKDAY_HOURS * 3600))
        late = bool(
            first_entrada is not None
            and (first_entrada.hour, first_entrada.minute, first_entrada.second) > work_start_t
        )

        day_rows.append(
            {
                "date": day,
                "marks": [
                    {
                        "time": m["timestamp"].strftime("%H:%M:%S"),
                        "status": m["status"],
                        "label": PUNCH_STATUS_LABELS.get(m["status"], "Marca"),
                        "punch_type": m["punch_type"],
                    }
                    for m in marks
                ],
                "first_mark": first.strftime("%H:%M:%S") if len(marks) >= 2 else None,
                "last_mark": last.strftime("%H:%M:%S") if len(marks) >= 2 else None,
                "worked_seconds": worked_seconds,
                "extra_seconds": extra_seconds,
                "late": late,
            }
        )
    return day_rows


def summarize_period(day_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Totales del periodo: dias con marcas, horas trabajadas, extra y retardos."""
    worked_seconds = sum(row["worked_seconds"] for row in day_rows)
    extra_seconds = sum(row["extra_seconds"] for row in day_rows)
    return {
        "days_with_marks": len(day_rows),
        "days_late": sum(1 for row in day_rows if row["late"]),
        "worked_hours": round(worked_seconds / 3600, 2),
        "extra_hours": round(extra_seconds / 3600, 2),
    }


def period_quick_links(today: date | None = None) -> list[dict[str, str]]:
    """Atajos de periodo para el selector: mes actual, mes anterior, ultimos 30 dias."""
    today = today or datetime.now().date()
    first_of_month = today.replace(day=1)
    prev_end = first_of_month - timedelta(days=1)
    prev_start = prev_end.replace(day=1)
    return [
        {
            "label": "Mes actual",
            "start_date": first_of_month.isoformat(),
            "end_date": today.isoformat(),
        },
        {
            "label": "Mes anterior",
            "start_date": prev_start.isoformat(),
            "end_date": prev_end.isoformat(),
        },
        {
            "label": "Ultimos 30 dias",
            "start_date": (today - timedelta(days=29)).isoformat(),
            "end_date": today.isoformat(),
        },
    ]
