# API Incapacidades — `/api/medical-leaves`

Contrato REST del módulo HR-3 (MYK-239). Todas las rutas exigen header
`Authorization: Bearer <token>` (401 si falta).

## `GET /api/medical-leaves/`

Query params: `employee_id` (opcional), `page` (default 1), `per_page` (default 20, max 50).

```json
{
  "leaves": [
    {
      "id": 1,
      "employee_id": 1,
      "leave_type": "enfermedad",
      "start_date": "2026-01-01",
      "end_date": "2026-01-05",
      "days": 5,
      "doctor_name": "Dra. House",
      "document_ref": "/uploads/abc.pdf",
      "status": "active",
      "created_at": "2026-10-19 21:00:00",
      "updated_at": "2026-10-19 21:00:00"
    }
  ],
  "pagination": {
    "page": 1,
    "per_page": 20,
    "total": 1,
    "total_pages": 1,
    "has_next": false,
    "has_prev": false
  }
}
```

## `POST /api/medical-leaves/`

Body:

```json
{
  "employee_id": 1,
  "leave_type": "enfermedad",
  "start_date": "2026-01-01",
  "end_date": "2026-01-05",
  "doctor_name": "Dra. House",
  "document_ref": "/uploads/abc.pdf"
}
```

- `days` se ignora si llega del cliente; el servidor calcula `(end_date - start_date).days + 1`.
- `leave_type` ∈ `enfermedad`, `maternidad`, `accidente`, `otro`.
- `end_date >= start_date`; si no, HTTP 400.
- `employee_id` debe existir; si no, HTTP 400.
- `document_ref` acepta string (path) o JSON (se serializa a string).
- Traslape con vacaciones aprobadas: HTTP 200/201 con campo `warnings` (lista de strings). No bloquea.
- Si la tabla `vacation_requests` aún no existe, el chequeo de traslape devuelve `warnings: []`
  sin fallar (fallback controlado). El helper queda listo para activarse cuando MYK-222 aterrice.

Respuesta `201`:

```json
{
  "leave": { "...": "..." },
  "warnings": []
}
```

## `GET /api/medical-leaves/<id>`

Respuesta `200` con `{"leave": {...}}`, `404` si no existe.

## `PUT /api/medical-leaves/<id>`

Acepta subset de campos: `employee_id`, `leave_type`, `start_date`, `end_date`,
`doctor_name`, `document_ref`. `days` se recalcula server-side. `status` no se
modifica por esta vía (usa DELETE). Respuesta `200` con `{"leave": {...}, "warnings": []}`.

## `DELETE /api/medical-leaves/<id>`

Soft delete: `status -> cancelled`. Respuesta `200` con `{"success": true, "message": "incapacidad cancelada", "leave": {...}}`.

## Helper para estadísticos

`MedicalLeaveRepository.get_leave_dates(employee_id, desde, hasta)` devuelve la lista
de fechas ISO con incapacidad **activa** en el rango. Los reportes de ausentismo
injustificado deben usar este helper para **excluir** esos días (una incapacidad no
es una falta).
