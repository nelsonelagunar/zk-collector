# Contrato de integración EX-1 — Export de cumplimiento y consulta self-service

> Contrato v1 (2026-10-26, integrations-dev). Define ANTES de codear: endpoints, auth,
> formatos, modos de falla y criterio de paridad. Implementa MYK-430 (EX-1).
> Base legal/requisitos: docs/compliance_nomina_2027.md (R5 exportaciones, R8 consulta
> del trabajador, R9 readiness nómina digital).
>
> Campos [TZ-1]/[CT-1]/[ID-1] dependen de MYK-426/427/431 (backend, backlog). El export
> los publica desde el día que existan; modo degradado en §5.

## 1. Endpoints

### 1.1 Export crudo de cumplimiento (extiende GET /api/attendance/export existente)

- Auth: `api_auth_required` — Bearer JWT / PAT (MYK-443/451).
- Query: `start_date`, `end_date` (YYYY-MM-DD, `end_date` inclusivo — MYK-383),
  `user_id`, `device_ip`, `status`, `punch_type`, `synced`, `format=csv|xlsx|json`.
- `format=json` nuevo; misma fuente de verdad que CSV/XLSX (§4).
- Columnas nuevas vs export crudo de master: `employee_code`, `department`,
  `work_center` [CT-1], `curp`, `rfc`, `nss` [ID-1], `utc_timestamp`, `tz_offset` [TZ-1].
- CSV: BOM utf-8-sig; XLSX: openpyxl; JSON: mismo orden de filas/valores que CSV.

### 1.2 Reporte por trabajador/día (nuevo: GET /api/attendance/report/day)

- Query: `start_date`, `end_date`, `employee_id` (opcional), `format=csv|xlsx|json`.
- Lógica: reutiliza `compute_attendance_stats` / `compute_report` (MYK-241). NO se bifurca
  cálculo; un solo camino de datos para dashboard, API y export.
- Filas: `employee_code`, nombre, `department`, `work_center` [CT-1], `fecha`,
  `check_in`, `check_out` (hora centro + offset), `utc_check_in`, `utc_check_out` [TZ-1],
  `curp`, `rfc` [ID-1] y totales del periodo.

### 1.3 Consulta self-service del trabajador (nuevo: GET /api/self/attendance[?format=json|csv])

- Auth: JWT con scope `self` ligado a `employee_id` (emisión manual por admin en v1;
  sin auto-registro del trabajador en v1).
- Solo-lectura y SOLO registros propios: `employee_id` se toma del token; si el query
  trae otro se ignora y se responde 400 (anti-IDOR por construcción).
- Resolución de identidad: `employees → employee_device_links(device_serial,
  device_user_id) → attendance_records.user_id` (migration 002).
- Rate limit: 60 req/min por token (patrón MYK-407); 429 + `Retry-After`.
- Trabajador sin dispositivo ligado → 200 con `records: []` (no es error del trabajador).

## 2. Formato de fila (fuente única para CSV / XLSX / JSON)

| Campo JSON | Header CSV/XLSX | Tipo | Origen | Depende |
|---|---|---|---|---|
| employee_code | Código | texto | employees.employee_code | — |
| employee_name | Colaborador | texto | employees.first/last_name | — |
| department | Departamento | texto | employees.department | — |
| work_center | Centro de trabajo | texto | work_centers.name | [CT-1] |
| date | Fecha | date (local centro) | attendance_records.timestamp | — |
| check_in | Entrada | ISO-8601 con offset | pares de marcas (status 0/1) | — |
| check_out | Salida | ISO-8601 con offset | pares de marcas (status 1/0) | — |
| utc_timestamp | UTC | ISO-8601 offset | attendance_records.utc_timestamp | [TZ-1] |
| tz_offset | Offset tz | texto (+HH:MM) | attendance_records.tz_offset | [TZ-1] |
| curp | CURP | texto | employees.curp | [ID-1] |
| rfc | RFC | texto | employees.rfc | [ID-1] |

## 3. Ejemplo de handshake (reproducible con curl)

```
# raw export (admin)
curl -s -H "Authorization: Bearer $ADMIN_TOKEN" \
  "http://localhost:5000/api/attendance/export?start_date=2026-10-01&end_date=2026-10-31&format=json"

# self-service (trabajador)
curl -s -H "Authorization: Bearer $WORKER_TOKEN" \
  "http://localhost:5000/api/self/attendance?start_date=2026-10-01&end_date=2026-10-31&format=json"
```

Respuesta JSON del self-service (esquema):

```json
{
  "employee_code": "E-00123",
  "period": {"start": "2026-10-01", "end": "2026-10-31"},
  "timezone": "America/Mexico_City",
  "records": [
    {"date": "2026-10-01", "check_in": "2026-10-01T08:00:00-05:00",
     "check_out": "2026-10-01T17:30:00-05:00", "utc_timestamp": "2026-10-01T13:00:00+00:00",
     "work_center": "Planta Norte"}
  ],
  "generated_at": "2026-10-26T09:00:00+00:00"
}
```

## 4. Paridad dashboard vs API vs export (criterio 2, patrón MYK-242)

Un test (tests/unit/webgui/) compara, para idénticos filtros:

1. Dashboard WebGUI `/reportes` (MYK-242)
2. `GET /api/attendance/stats` (JSON KPIs, MYK-241)
3. Export CSV/XLSX/JSON parseado del reporte por día

Exige: totales de entrada/salida por trabajador idénticos en las tres vistas; y JSON export
== filas del CSV (mismos valores, distinto transporte). Las tres vistas comparten
`compute_attendance_stats`/`compute_report` para no bifurcar cifras.

## 5. Modo degradado y modos de falla

- Dependencias [TZ-1]/[CT-1]/[ID-1] no mergeadas: columnas presentes pero vacías
  (`""` CSV / `null` JSON); JSON incluye `"schema_version": 1` y `"fields_pending":
  ["utc_timestamp","work_center","curp",...]`. Nada se rompe; se rellena al hacer merge.
- Rango fuera de política de retención (RT-1, MYK-428): 400 con mensaje y límite máximo.
- Sin registros para el filtro: 200, CSV solo headers, XLSX hoja vacía, JSON `records: []`.
- Fecha inválida: 400 `StatsValidationError` (patrón existente en attendance_stats.py).
- `employee_id` ajeno en self-service: 400 (token vence cualquier override).

## 6. Re-validación STPS (criterio 3)

Cuando STPS publique las disposiciones finales (Anexo 20/RMF), diff campo a campo contra
§2 y abrir issue con el delta. Owner: integrations-dev; disparo: comentario en MYK-430.

## 7. Criterios de aceptación (issue MYK-430)

1. Export incluye hora del centro + UTC + centro de trabajo + identidad (employee_code y,
   cuando existan, CURP/RFC).
2. Test de paridad dashboard vs API vs export pasa en CI.
3. Re-validación contra STPS cuando se publiquen (ver §6).
