"""
Export legal de asistencia (MYK-424, compliance_nomina_2027 seccion 4 item 6).

Reconstruye GET /attendance/export con el formato legal: columnas de empleado
(codigo, CURP, RFC), razon social del patron (RFC, migration 008),
centro de trabajo (ubicacion del dispositivo, modo degradado hasta CT-1/MYK-427),
fecha-hora con zona horaria (MYK-420), tipo de marca y desglose de jornada
(LFT 61/66-68: jornada ordinaria, primeras 9 horas extra semanales al doble
y el resto al triple).

Todo el computo de jornada es puro y probado sin HTTP; la ruta solo ensambla
filtros y serializa CSV/XLSX.
"""

from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any
from zoneinfo import ZoneInfo

from ..utils.timezones import to_local

STANDARD_WORKDAY_HOURS = 8.0
WEEKLY_EXTRA_DOUBLE_CAP_HOURS = 9.0

PUNCH_TYPE_NAMES: dict[int, str] = {
    0: "entrada",
    1: "salida",
    2: "salida_comida",
    3: "entrada_comida",
    4: "entrada_extra",
    5: "salida_extra",
}

LEGAL_HEADERS: list[str] = [
    "Codigo empleado",
    "Colaborador",
    "CURP",
    "RFC",
    "Razon social",
    "RFC patron",
    "Centro de trabajo",
    "Fecha/Hora",
    "Tipo de marca",
    "Estado",
    "Semana ISO",
    "Horas ordinarias",
    "Horas extra dobles",
    "Horas extra triples",
]

EMPTY_JORNADA = ("", "", "")


def fmt_hours(hours: float) -> str:
    """Numero de horas con ceros finales recortados (40, 2.5, 9)."""
    text = f"{hours:.2f}"
    return text.rstrip("0").rstrip(".")


def punch_type_name(status: Any) -> str:
    """Nombre del tipo de marca para un status de dispositivo (0-5)."""
    try:
        return PUNCH_TYPE_NAMES[int(status)]
    except (TypeError, ValueError, KeyError):
        return "desconocido"


def _tipo_marca_legal(record: dict[str, Any]) -> str:
    """Tipo de marca de un registro: la columna punch_type ya trae el nombre
    (entrada/salida/...); si falta, se deriva del status numerico (0-5)."""
    raw = record.get("punch_type")
    if raw is not None:
        text = str(raw)
        if text.isdigit():
            return punch_type_name(int(text))
        return text
    return punch_type_name(record.get("status"))


def iso_week_key(local_dt: datetime) -> str:
    """Etiqueta ISO 8601 de la semana del centro de trabajo (YYYY-Www)."""
    iso_year, iso_week, _iso_weekday = local_dt.date().isocalendar()
    return f"{iso_year}-W{iso_week:02d}"


def jornada_semana(marks_by_day: dict[date, list[datetime]]) -> tuple[float, float, float]:
    """Desglose de jornada de una semana ISO para una persona.

    Reglas (consistente con el operador del portal, src/webgui/portal.py):
    - Dia con >= 2 marcas: trabajado = ultima marca - primera marca.
    - Ordinario del dia = min(trabajado, 8 h); extra del dia = max(0, trabajado - 8 h).
    - Semana: extra dobles = min(extra semanal, 9 h); extra triples = el resto (LFT 66-68).

    Devuelve (horas_ordinarias, horas_extra_dobles, horas_extra_triples).
    """
    segundos_ordinarios = 0.0
    segundos_extra = 0.0
    for day_marks in marks_by_day.values():
        if len(day_marks) < 2:
            continue
        worked_seconds = (max(day_marks) - min(day_marks)).total_seconds()
        segundos_ordinarios += min(worked_seconds, STANDARD_WORKDAY_HOURS * 3600)
        segundos_extra += max(0.0, worked_seconds - STANDARD_WORKDAY_HOURS * 3600)

    doble = min(segundos_extra, WEEKLY_EXTRA_DOUBLE_CAP_HOURS * 3600)
    triple = max(0.0, segundos_extra - WEEKLY_EXTRA_DOUBLE_CAP_HOURS * 3600)
    return (
        segundos_ordinarios / 3600,
        doble / 3600,
        triple / 3600,
    )


@dataclass(frozen=True)
class EmployeeRow:
    employee_code: str
    first_name: str | None
    last_name: str | None
    curp: str | None
    rfc: str | None
    department: str | None


@dataclass(frozen=True)
class CompanyRow:
    razon_social: str | None
    rfc: str | None


@dataclass(frozen=True)
class DeviceInfo:
    serial_number: str | None
    location: str | None


class ExportContext:
    """Mapas de consulta para enriquecer registros de asistencia (una lectura cada uno)."""

    def __init__(self, db: Any) -> None:
        self._employee_by_link: dict[tuple[str, str], EmployeeRow] = {}
        self._company_by_serial: dict[str, CompanyRow] = {}
        self._device_by_ip: dict[str, DeviceInfo] = {}

        device_rows = db.fetch_all("SELECT address, serial_number, location FROM devices")
        self._device_by_ip = {
            row["address"]: DeviceInfo(row["serial_number"], row["location"]) for row in device_rows
        }

        serials = {info.serial_number for info in self._device_by_ip.values() if info.serial_number}
        if serials:
            placeholders = ",".join("?" * len(serials))
            links = db.fetch_all(
                f"""
                SELECT edl.device_serial, edl.device_user_id,
                       e.employee_code, e.first_name, e.last_name,
                       e.curp, e.rfc, e.department
                FROM employee_device_links edl
                JOIN employees e ON e.id = edl.employee_id
                WHERE edl.device_serial IN ({placeholders})
                """,
                tuple(serials),
            )
            self._employee_by_link = {
                (row["device_serial"], str(row["device_user_id"])): EmployeeRow(
                    row["employee_code"] or "",
                    row["first_name"],
                    row["last_name"],
                    row["curp"],
                    row["rfc"],
                    row["department"],
                )
                for row in links
            }

            companies = db.fetch_all(
                "SELECT cd.device_serial, c.razon_social, c.rfc "
                "FROM companies c "
                "JOIN company_devices cd ON cd.company_id = c.id "
                "WHERE cd.device_serial IN (" + placeholders + ")",
                tuple(serials),
            )
            self._company_by_serial = {
                row["device_serial"]: CompanyRow(row["razon_social"], row["rfc"])
                for row in companies
            }

    def employee_for(self, device_ip: str | None, user_id: Any) -> EmployeeRow | None:
        if not device_ip:
            return None
        info = self._device_by_ip.get(str(device_ip))
        if not info or not info.serial_number:
            return None
        return self._employee_by_link.get((info.serial_number, str(user_id)))

    def pairs_for(self, person_key: tuple[str, ...]) -> list[tuple[str, str]]:
        """Pares (device_ip, device_user_id) que mapean a esa persona."""
        if person_key[0] == "U":
            return [(person_key[1], person_key[2])]
        employee_code = person_key[1]
        serial_by_ip = {
            info.serial_number: ip for ip, info in self._device_by_ip.items() if info.serial_number
        }
        pairs: list[tuple[str, str]] = []
        seen: set[tuple[str, str]] = set()
        for (serial, uid), emp in self._employee_by_link.items():
            if emp.employee_code != employee_code:
                continue
            ip = serial_by_ip.get(serial)
            if not ip or (ip, uid) in seen:
                continue
            seen.add((ip, uid))
            pairs.append((ip, uid))
        return pairs

    def company_for(self, device_ip: str | None) -> CompanyRow | None:
        if not device_ip:
            return None
        info = self._device_by_ip.get(str(device_ip))
        if not info or not info.serial_number:
            return None
        return self._company_by_serial.get(info.serial_number)

    def location_for(self, device_ip: str | None) -> str | None:
        if not device_ip:
            return None
        info = self._device_by_ip.get(str(device_ip))
        return info.location if info else None


def _person_key(
    employee: EmployeeRow | None, device_ip: str | None, user_id: Any
) -> tuple[str, ...]:
    if employee and employee.employee_code:
        return ("E", employee.employee_code)
    return ("U", str(device_ip or ""), str(user_id or ""))


def _local_dt(record: dict[str, Any], tz: ZoneInfo) -> datetime:
    parsed = to_local(record.get("timestamp"), tz)
    if parsed is None:
        return datetime.min.replace(tzinfo=tz)
    return parsed


def build_legal_rows(
    records: list[dict[str, Any]],
    webgui_db: Any,
    buffer_repo: Any,
    tz: ZoneInfo,
) -> list[dict[str, str]]:
    """Enriquece registros del buffer a filas del export legal.

    `records` debe venir ordenado por timestamp ASC. `webgui_db` provee el
    catablo de empleados/dispositivos/empresas; `buffer_repo` provee el universo
    de marcas para el desglose de jornada semanal. El desglose se computa sobre
    TODAS las marcas de cada persona/semana involucradas (no solo las filas
    filtradas para exportar), de modo que la semana no se rompa cuando el filtro
    trae solo un subconjunto (p.ej. solo status=entrada).
    """
    ctx = ExportContext(webgui_db)

    localized: list[tuple[Any, datetime, EmployeeRow | None]] = []
    person_weeks: dict[Any, set[tuple[int, int]]] = defaultdict(set)
    for record in records:
        local_dt = _local_dt(record, tz)
        employee = ctx.employee_for(record.get("device_ip"), record.get("user_id"))
        person_key = _person_key(employee, record.get("device_ip"), record.get("user_id"))
        localized.append((person_key, local_dt, employee))
        iso_year, iso_week, _ = local_dt.date().isocalendar()
        person_weeks[person_key].add((iso_year, iso_week))

    spans: dict[tuple[int, int], tuple[date, date]] = {}
    for person_key in person_weeks:
        for iso_year, iso_week in person_weeks[person_key]:
            if (iso_year, iso_week) in spans:
                continue
            monday = _monday_of_iso_week(iso_year, iso_week)
            spans[(iso_year, iso_week)] = (monday - timedelta(days=1), monday + timedelta(days=7))

    jornada_lookup: dict[tuple[Any, int, int], tuple[str, str, str]] = {}
    for person_key in person_weeks:
        for iso_year, iso_week in sorted(person_weeks[person_key]):
            lo, hi = spans[(iso_year, iso_week)]
            by_day: dict[date, list[datetime]] = defaultdict(list)
            for device_ip, user_id in ctx.pairs_for(person_key):
                with buffer_repo.get_connection() as conn:
                    rows = conn.execute(
                        "SELECT timestamp FROM attendance_records "
                        "WHERE device_ip = ? AND user_id = ? "
                        "AND substr(timestamp, 1, 10) BETWEEN ? AND ? "
                        "ORDER BY id",
                        (device_ip, user_id, lo.isoformat(), hi.isoformat()),
                    ).fetchall()
                for row in rows:
                    row_dt: datetime | None = to_local(row["timestamp"], tz)
                    if row_dt is None:
                        continue
                    by_day[row_dt.date()].append(row_dt)
            ordinaria, doble, triple = jornada_semana(by_day)
            jornada_lookup[(person_key, iso_year, iso_week)] = (
                fmt_hours(ordinaria),
                fmt_hours(doble),
                fmt_hours(triple),
            )

    out: list[dict[str, str]] = []
    for record, (person_key, local_dt, employee) in zip(records, localized, strict=True):
        iso_year, iso_week, _ = local_dt.date().isocalendar()
        jornada = jornada_lookup.get((person_key, iso_year, iso_week), EMPTY_JORNADA)
        out.append(legal_row(record, local_dt, ctx, jornada, employee))
    return out


def _monday_of_iso_week(iso_year: int, iso_week: int) -> date:
    jan4 = date(iso_year, 1, 4)
    monday_week1 = jan4 - timedelta(days=jan4.weekday())
    return monday_week1 + timedelta(weeks=iso_week - 1)


def legal_row(
    record: dict[str, Any],
    local_dt: datetime,
    ctx: ExportContext,
    jornada: tuple[str, str, str],
    employee: EmployeeRow | None,
) -> dict[str, str]:
    """Una fila del export legal a partir de un registro del buffer."""
    device_ip = record.get("device_ip")
    company = ctx.company_for(device_ip)

    if employee:
        first = employee.first_name or ""
        last = employee.last_name or ""
        nombre = (first + " " + last).strip() or employee.employee_code
    else:
        nombre = ""

    return {
        "Codigo empleado": employee.employee_code if employee else "",
        "Colaborador": nombre,
        "CURP": (employee.curp or "") if employee else "",
        "RFC": (employee.rfc or "") if employee else "",
        "Razon social": (company.razon_social or "") if company else "",
        "RFC patron": (company.rfc or "") if company else "",
        "Centro de trabajo": ctx.location_for(device_ip) or "",
        "Fecha/Hora": local_dt.isoformat(),
        "Tipo de marca": _tipo_marca_legal(record),
        "Estado": str(record.get("status", "")),
        "Semana ISO": iso_week_key(local_dt),
        "Horas ordinarias": jornada[0],
        "Horas extra dobles": jornada[1],
        "Horas extra triples": jornada[2],
    }
