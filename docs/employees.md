# Módulo Colaboradores — modelo de datos

Base de datos del módulo HR "Colaboradores ABC" (Sprint 3). La tabla `device_users`
solo mapea `user_id → nombre` leído del reloj; no modela un colaborador real.
`employees` es la fuente de verdad de un colaborador y la base para vacaciones,
incapacidades, retardos y estadísticos.

## Tablas

### `employees`

| Columna        | Tipo      | Restricciones                          |
|----------------|-----------|----------------------------------------|
| id             | INTEGER   | PK autoincremental                     |
| employee_code  | TEXT      | UNIQUE NOT NULL                        |
| first_name     | TEXT      |                                        |
| last_name      | TEXT      |                                        |
| email          | TEXT      |                                        |
| phone          | TEXT      |                                        |
| department     | TEXT      |                                        |
| position       | TEXT      |                                        |
| hire_date      | DATE      |                                        |
| status         | TEXT      | `active` / `inactive` (CHECK), default `active` |
| notes          | TEXT      |                                        |
| curp           | TEXT      | opcional; CHECK length=18 (mig. 011)   |
| rfc            | TEXT      | opcional; CHECK length 12/13 (mig. 011)|
| nss            | TEXT      | opcional; CHECK length=11 (mig. 011)   |
| imss_numero_seguro | TEXT | opcional; CHECK length=11 (mig. 011)   |
| tipo_jornada   | TEXT      | opcional; CHECK IN `diurna`/`mixta`/`nocturna` (mig. 011) |
| turno          | TEXT      | opcional, texto libre (mig. 011)       |
| created_at     | DATETIME  | default `CURRENT_TIMESTAMP`            |
| updated_at     | DATETIME  | default `CURRENT_TIMESTAMP`            |

### `employee_device_links`

Vincula un colaborador con sus badges/dispositivos (1 colaborador → N enlaces).

| Columna        | Tipo      | Restricciones                                   |
|----------------|-----------|-------------------------------------------------|
| id             | INTEGER   | PK autoincremental                              |
| employee_id    | INTEGER   | FK → `employees(id)` `ON DELETE CASCADE`        |
| device_serial  | TEXT      | NOT NULL                                        |
| device_user_id | TEXT      | NOT NULL                                        |
| created_at     | DATETIME  | default `CURRENT_TIMESTAMP`                     |
| updated_at     | DATETIME  | default `CURRENT_TIMESTAMP`                     |

- `UNIQUE(device_serial, device_user_id)`: un badge solo puede estar vinculado
  a un colaborador.

## Índices

| Índice                                     | Justificación                                                     |
|--------------------------------------------|-------------------------------------------------------------------|
| `employees(employee_code)` (UNIQUE implícito) | Lookup por código en `get_by_code` y altas/bajas.              |
| `idx_employees_status`                     | Filtro `WHERE status = 'active'` en el listado ABC y reportes HR. |
| `idx_employee_device_links_employee_id`    | Lookup de los enlaces de un colaborador (`list_links`) y cascade. |

`EXPLAIN QUERY PLAN SELECT * FROM employees WHERE status = 'active'` → usa
`idx_employees_status` (índice) en lugar de full scan.

## Datos laborales del empleado (MYK-423, migración 011)

Columnas opcionales de identidad y jornada (compliance jornada 2027,
`docs/compliance_nomina_2027.md` §4 item 5): `curp`, `rfc`, `nss`,
`imss_numero_seguro`, `tipo_jornada`, `turno`. Todas aceptan NULL
("no capturado"); el CHECK SQL cubre longitud/enum y la validación de
FORMATO completa vive en `src/webgui/validators.py` (aplicada por la API
`/api/employees` y por `EmployeeRepository`):

- **CURP**: 18 caracteres con estructura RENAPO (4 letras, fecha YYMMDD,
  sexo H/M, clave de entidad federativa del catálogo oficial, 3 consonantes
  interiores, homoclave alfanumérica, dígito verificador). Se normaliza a
  mayúsculas. No se recalcula el dígito verificador (validación de
  estructura, no de padrón).
- **RFC**: 12 caracteres (persona moral: 3 letras + fecha + homoclave) o
  13 (persona física: 4 letras + fecha + homoclave), estructura SAT.
  Se normaliza a mayúsculas.
- **NSS / imss_numero_seguro**: 11 dígitos (formato IMSS).
- **tipo_jornada**: enum LFT 58-60 (`diurna`, `mixta`, `nocturna`).
- **turno**: texto libre (matutino/vespertino/rotativo/…).

Sin índices ni UNIQUE nuevos en la 011: no existe query shape que filtre
por CURP/RFC (revisar con EXPLAIN cuando EX-1 los junte en el export legal),
y los registros legados pueden cargar duplicados pendientes de depurar.

**Export**: `GET /api/employees/export` (CSV, mismos filtros status/
department/search que el listado) incluye todas las columnas laborales,
con `curp` y `rfc` en cada fila.

## Capa de acceso (contrato para backend-dev)

`src/webgui/employees.py` — `EmployeeRepository(db)` (recibe la instancia
`Database` de webgui):

- `create(data) -> int` — requiere `employee_code`; valida `status` y formato
  de los campos laborales (CURP/RFC/NSS/tipo_jornada, MYK-423).
- `get(id)` / `get_by_code(code)` — devuelve `dict | None`.
- `list_employees(status=None, search=None) -> list[dict]` — filtro por status y búsqueda libre.
- `update(id, data) -> int` — no modifica `employee_code` ni `created_at`;
  valida los campos laborales presentes (los ausentes no se limpian).
- `set_status(id, status) -> int` — alta/baja lógica.
- `delete(id) -> int` — borrado físico (limpia links explícitamente).
- `link_device(id, device_serial, device_user_id) -> int` — idempotente (`OR IGNORE`).
- `unlink_device(id, device_serial, device_user_id) -> int`.
- `list_links(id) -> list[dict]`.

El endpoint HTTP `/api/employees` lo implementa backend-dev (MYK-221) sobre
este repositorio.

## Integridad referencial (nota SQLite)

Las FK se declaran en la migración `002_employees.sql`, pero SQLite desactiva
`PRAGMA foreign_keys` por defecto en cada conexión. El `ON DELETE CASCADE` se
verifica en tests con `PRAGMA foreign_keys = ON`; a nivel de runtime
`EmployeeRepository.delete()` limpia los links explícitamente para no depender
del pragma.
