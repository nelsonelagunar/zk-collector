# Attendance Stats — Endpoints estadísticos de asistencia (MYK-241)

API de reportes de asistencia por periodo con KPIs de RRHH.

## Endpoints

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/attendance/stats` | Reporte JSON de KPIs por periodo |
| GET | `/api/attendance/stats/export` | Export del mismo reporte en CSV o Excel |

Ambos requieren header `Authorization: Bearer <token>`.

## Filtros (compartidos)

| Param | Tipo | Default | Notas |
|-------|------|---------|-------|
| `start_date` | YYYY-MM-DD | primer día del mes actual | |
| `end_date` | YYYY-MM-DD | hoy | |
| `employee_id` | integer | — | filtra a un colaborador |
| `department` | string | — | filtra por departamento exacto |
| `group_by` | `employee` \| `department` \| `company` | `employee` | nivel de agrupación |
| `format` (solo export) | `csv` \| `xlsx` | `csv` | |

Fechas inválidas, `start_date > end_date`, `group_by` o `employee_id` inválidos → `400 {"error": ...}`.

## Reglas de cómputo (días hábiles = Lun–Vie)

- `days_expected`: hábiles en `[max(start_date, hire_date), end_date]` (sin `hire_date` no hay tope).
- `days_present`: hábiles con **≥ 1 registro** de asistencia del colaborador (cualquier tipo de marca).
- `days_incapacity`: hábiles cubiertos por `medical_leaves` **activas** y no presentados — el día trabajado tiene precedencia sobre la incapacidad.
- `days_vacation`: hábiles cubiertos por vacaciones aprobadas. Hoy siempre `0`: no existe fuente de datos (módulo de vacaciones no implementado). El campo ya forma parte del contrato para cuando exista.
- `days_absent`: `max(0, expected - present - incapacity - vacation)`.
- `late_arrivals` (retardos): días presentados cuyo **primer punch de entrada** (status `0`) es posterior a la hora default de inicio — config `ATTENDANCE_WORK_START` (default `09:00:00`), configurable por deployment. Computo simple vs horario default según decisión de PO (MYK-241); el motor completo de reglas de retardos vive en MYK-224.
- `punctuality_pct`: `100 * (present - retardos) / present`; `null` si `present == 0`.
- `absenteeism_pct`: `100 * ausentes / expected`; `null` si `expected == 0`.
- Registros que no mapean a un colaborador activo (sin `employee_device_links`) se cuentan en `meta.unlinked_records` y no afectan KPIs.

Acepta timestamps del buffer en formato `YYYY-MM-DD HH:MM:SS` e ISO con `T` (el emulador/colector escribe con `isoformat()`).

## Response shape (JSON)

```json
{
  "period": {"start_date": "2026-10-05", "end_date": "2026-10-09"},
  "filters": {"start_date": "...", "end_date": "...", "employee_id": null, "department": null, "group_by": "employee"},
  "group_by": "employee",
  "work_start": "09:00:00",
  "rows": [
    {
      "employee_id": 1, "employee_code": "E001", "employee_name": "Ana Lopez", "department": "IT",
      "days_expected": 5, "days_present": 3, "days_absent": 1, "days_incapacity": 1,
      "days_vacation": 0, "late_arrivals": 1, "punctuality_pct": 66.7, "absenteeism_pct": 20.0
    }
  ],
  "totals": {"days_expected": 8, "days_present": 3, "days_absent": 4, "days_incapacity": 1, "days_vacation": 0, "late_arrivals": 1, "punctuality_pct": 66.7, "absenteeism_pct": 50.0},
  "meta": {"employees_total": 2, "unlinked_records": 0}
}
```

Con `group_by=department` cada fila lleva `department`; con `group_by=company` una sola fila lleva `company` (config `COMPANY_NAME`, default `default`).

## Export

CSV con BOM `utf-8-sig` (compatibilidad Excel) y XLSX vía openpyxl, reutilizando el patrón del export de asistencia (`src/webgui/routes/attendance.py`). Columnas: las etiquetas del nivel de agrupación + los 8 KPIs, más una fila `TOTAL`.

## Implementación

- Servicio puro: `src/webgui/attendance_stats.py` (`compute_attendance_stats`).
- Rutas: `src/webgui/routes/attendance_stats.py`.
- WebGUI dashboard: `src/webgui/routes/attendance_stats_ui.py` + `templates/reports/stats.html`
  (GET /reportes, MYK-242); reutiliza `compute_report` y `build_export_response` de la API.
- Tests: `tests/test_attendance_stats.py` (servicio, números contra fixtures),
  `tests/test_attendance_stats_routes.py` (API + export) y
  `tests/test_attendance_stats_ui.py` (dashboard: paridad con API, filtros, export, <2s con 10k).
