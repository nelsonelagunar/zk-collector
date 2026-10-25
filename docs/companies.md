# Razón social (empresas) — modelo de datos

Módulo de razones sociales y su vinculación con relojes checadores (MYK-405,
MYK-403 items 3-4). Migration **008** — no 005 como en el issue original: en master
ya existen `005_alerts` (MYK-227), `006_alert_default_rules` y `007_demo_seed`.

## Tablas

### `companies`

| Columna                  | Tipo      | Restricciones                                     |
|--------------------------|-----------|---------------------------------------------------|
| id                       | INTEGER   | PK autoincremental                                |
| razon_social             | TEXT      | NOT NULL                                          |
| rfc                      | TEXT      | opcional; único parcial cuando no vacío           |
| imss_registro_patronal   | TEXT      | opcional                                          |
| domicilio_fiscal         | TEXT      | opcional                                          |
| status                   | TEXT      | `active` / `inactive` (CHECK), default `active`   |
| created_at / updated_at  | DATETIME  | default `CURRENT_TIMESTAMP`                       |

Soft delete vía `status`, igual que `employees` (migration 002).

### `company_devices`

Puente empresa ↔ reloj checador (1:N: una empresa → N relojes; un reloj → 1 empresa).

| Columna        | Tipo      | Restricciones                                |
|----------------|-----------|----------------------------------------------|
| id             | INTEGER   | PK autoincremental                           |
| company_id     | INTEGER   | NOT NULL, FK → `companies(id)` ON DELETE CASCADE |
| device_serial  | TEXT      | NOT NULL **UNIQUE** — un reloj, una empresa  |
| created_at / updated_at | DATETIME | default `CURRENT_TIMESTAMP`        |

## Decisiones de diseño (el "por qué")

### Puente `company_devices` vs columna `company_id` en `devices`

Elegimos tabla puente porque:
- `ALTER TABLE ADD COLUMN` no existe de forma idempotente en SQLite (no hay
  `IF NOT EXISTS` para columnas): rompería la garantía de re-ejecución del patrón
  migration 002.
- Simetría con `employee_device_links` (migration 002), que ya referencia los
  relojes por `device_serial` TEXT — `devices.serial_number` es nullable y sin
  índice único, no es llave confiable.
- El UNIQUE sobre `device_serial` codifica el 1:N de hoy; relajar a N:M
  (p. ej. reloj compartido entre co-patrocinadores) es una migration futura que
  solo recrea el índice, sin DDL sobre tablas existentes.

### `employees` NO gana `company_id` (aún)

- Mismo problema de idempotencia de `ALTER TABLE` en SQLite.
- Sin consumidor hoy: `group_by=company` en `/api/attendance/stats` usa
  `system_config.company_name` (ver `docs/attendance_stats.md`); una columna
  nullable sin writers/lectores es esquema muerto que se desincroniza.
- La ruta de derivación ya existe: empleado → `employee_device_links.device_serial`
  → `company_devices.company_id`.
- Cuando llegue el multitenancy real (SaaS, PostgreSQL), una migration dedicada
  agrega la columna con backfill desde esa ruta de derivación.

### RFC único parcial

`idx_companies_rfc` es `UNIQUE ... WHERE rfc IS NOT NULL AND rfc <> ''`: RFC es
opcional, y NULL/'' repetibles no deben chocar; dos empresas con el mismo RFC
sí son un error de captura.

## Índices

| Índice                                       | Justificación                                          |
|----------------------------------------------|--------------------------------------------------------|
| `idx_companies_status`                       | Filtro `status='active'` en listados CRUD (`get_companies`). |
| `idx_companies_rfc` (UNIQUE parcial)         | Lookup por RFC + anti-duplicados de captura.           |
| `idx_company_devices_company_id`             | Lookup de relojes de una empresa (`get_devices_for_company`). |
| `company_devices(device_serial)` (UNIQUE implícito) | Resuelve `get_company_for_device` y aplica el 1:N. |

## Backfill

Migration 008 materializa UNA empresa desde `system_config.company_name` si ese
key existe (p.ej. seed demo 007) y `companies` está vacía; si no, no-op. Renombrar
después en CRUD no se revierte.

## Capa de acceso

CRUD en `src/webgui/database.py` (métodos de `Database`):
`get_company_by_id/by_rfc`, `get_companies(status)`, `create/update/delete_company`
(soft delete), `link_device_to_company` (upsert: re-vincular transfiere propiedad),
`unlink_device_from_company(device_serial)`, `get_devices_for_company`,
`get_company_for_device`. Tests: `tests/test_companies.py`.
