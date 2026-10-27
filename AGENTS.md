# AGENTS.md — zk-collector Contexto Operativo

## Quick-ref

- **Repo:** `https://github.com/nelsonelagunar/zk-collector` (master = deploy target, branch `fix/p0-1-supervisord` = dual supervisord WIP)
- **WebGUI live:** `http://10.0.0.16:8081` (login `demo.admin` / `demo1234` — cualquier rol)
- **Collector live:** `lxc108-zk` (10.0.0.16) con `docker-entrypoint.sh` (supervisord) + WebGUI Gunicorn
- **Emulador ZKTeco:** TCP :4370 (`mock/zk_emulator.py`), fixtures `mock/attendance_seed.json` (120 emp × 22 días L-V, 5.280 marcajes)
- **Coolify:** `http://10.0.0.12:8000` (apps `mmbpwzjn1bt1q639zua9fxrn` zk-collector, `sj5d7uobcnunrlylus0ivcbj` 9to9technews)
- **Board API:** `http://10.0.0.13:3100/api` (token en `/root/create-rest.sh`), company `c1c6aa82-3f9f-4f39-b1f9-4d9aa94f5d08`
- **GitHub token (admin `nelsonelagunar`):** `gho_********` en workspaces backend-dev, frontend-dev, dba, main repo
- **9to9technews:** `https://9to9technews.mykeepper.app` (sources `config/sources.json`, ElHacker `blog.elhacker.net/rss.xml`)
- **Paperclip agents:** coffee `6ac9e0a8...`, backend-dev `051c0b6e...`, frontend-dev `d9be0232...`, dba `17007906...`, architect `91c8a663...` (idle), reviewer `91c8a663...` (running), integrations `7a03a801...`
- **Comentar issue = wake run** del agente asignado; cerrar al final con PATCH `status=done`
- **Coolify webhook secret:** `i13aV7ZRrvG9AnfJ0k16Qj8gaBzbg8xtqz7yOKuU`; auto-deploy polling desconocido; usar `restart` con `git_commit_sha: "HEAD"`

## Principios de trabajo

- **No inventes.** Lee el código y los archivos antes de actuar. `AGENTS.md` es fuente de verdad viva; si algo no está aquí, no existe.
- **PR = merge gate.** Mínimo 1 approval + CI verde (`clean`). Owner autoriza merge: "hazlo, autorizo los PRs".
- **Compliance MX 2027** en marcha (MYK-410, 426–438); registro electrónico de jornada (NOM-035, LFT, CST, SAT).
- **Demo asistencias poblada:** 5.280 marcajes (120×22×2), seed `mock/attendance_seed.json`, backup `.bak-20261024205307`.
- **Health check:** `http://10.0.0.16:8081/health` → 200.
- **Guard `cross_issue_influence_run_context_required`:** NO SE TOCA (control intencional, documentado 2026-10-02). Solución: dar contexto de issue a runs de coffee (wake por asignación).

## Lecciones de MYK-227 (5 runs perdidos)

- Idempotente por guards de llave natural (employee_code/username UNIQUE, links PK, devices por address). Tests: `tests/test_demo_seed.py`, `tests/test_nav_routing.py`.

## RBAC (ADR-001, MYK-412, migration 008)

- Roles fijos (catalogo cerrado): `admin`, `rrhh`, `supervisor`, `auditor` en `users.role`.
- `src/webgui/permissions.py`: `ALLOWED_ROLES`, `ROLE_PERMISSIONS` (matriz exacta del ADR-001) y funciones puras `has_permission(role, perm)` / `role_permissions(role)` — deny por defecto para roles desconocidos. Testeable sin BD (`tests/test_permissions.py`).
- `migrations/008_rbac_roles.sql`: normaliza roles legacy (`user`, NULL, otros) a `auditor`. Idempotente (solo UPDATE). NOTA: el ADR-001 dice "migracion 005", pero `005_alerts.sql` ya ocupaba el slot en master; la numeracion fisica manda (008).
- Validacion de rol es capa app (SQLite no soporta ADD CONSTRAINT): todo write path de `users` debe validar contra `ALLOWED_ROLES` (`/users/new` ya lo hace).
- Decoradores `require()`/`api_require()` y aplicacion por blueprint: issues hijos de MYK-406 (middleware, blueprint application, API usuarios) — NO implementados en MYK-412.

## Middleware RBAC (MYK-413)

- `require(*perms)` — rutas UI (sesión): sesión verificada como `login_required` y `has_permission(session["role"], perm)` para TODOS los permisos (AND). Sin sesión -> redirect al login; sin permiso -> flash + redirect a `/`. Roles desconocidos deniegan.
- `api_require(*perms)` — APIs: sesión WebGUI (`user_id`) O Bearer JWT verificado con `Auth.verify_access_token` (HS256, `type=access`, fail-closed sin `app.auth`). Rol desde `session["role"]` o claim `role` del payload. 401 credencial ausente/inválida/expirada, 403 `{"error": "Insufficient permissions"}` sin permiso (JSON). Multi-permiso = AND.
- `g.api_user` SOLO se setea en el path JWT: handlers decorados que atienden también sesión NO deben leerlo directo (usar `getattr(g, "api_user", None)` o el rol de sesión).
- `api_auth_required` es alias deprecated de `api_require()` sin permisos (mismo comportamiento byte a byte que MYK-443); se elimina tras migrar usos (MYK-414).
- `admin_required` deprecated en favor de `require("users:manage"|"settings:manage")`.
- Aplicación por blueprint: MYK-414; API CRUD usuarios + OpenAPI: MYK-415.
- Tests: `tests/test_rbac_middleware.py` (33, parametrizados por rol).

## API Auth (MYK-443)

- `api_auth_required` (`src/webgui/middleware/auth.py`) valida de verdad desde MYK-443: sesión WebGUI activa (`user_id` en session, para los fetch same-origin del dashboard) O Bearer JWT firmado con `WEBGUI_SECRET_KEY` via `Auth.verify_access_token` (`type=access`, HS256). Todo lo demas responde 401 `{"error": ...}` (shape intacto). Fail-closed si la app no tiene `app.auth` (create_app siempre lo setea, server.py:70).
- Todos los blueprints API usan el decorador: `/api/employees` (anadido en MYK-443, antes estaba SIN decorador), `/api/medical-leaves`, `/api/attendance/stats`, `/api/alerts`. Los templates NUNCA mandan token falso: la cookie de sesión autentica.
- NO existe endpoint de emisión de JWT (login es solo sesión); mint externo = `Auth(secret).generate_tokens(user_id, username, role)`. Refresh tokens no sirven como access. Tests: `tests/test_api_auth_middleware.py` (401/200 por blueprint).
- Los endpoints JSON internos de UI (`/devices/api/*`, `/attendance/api/*`, `/colaboradores/api/*`, `/reportes/api/*`) quedaron SIN auth — seguimiento aparte.

## Razón Social API + WebGUI (MYK-411)

- API REST Bearer `/api/companies` (routes/companies.py): CRUD + link/unlink de relojes; DELETE es baja lógica; POST devices valida serial contra `devices` y transfiere propiedad (upsert 1:N). Contrato en `docs/openapi.yaml` tag `companies`.
- Sección WebGUI `/configuracion/razon-social` (routes/companies_ui.py + templates/companies/index.html), navbar "Razón Social". El form consume la API con `Authorization: Bearer webgui` (patrón expediente colaboradores). Soporte `/configuracion/razon-social/api/devices` (login_required) devuelve relojes + dueño.
- Tests: tests/test_companies_routes.py (API 30 casos), tests/test_companies_ui.py (UI+flujo), test_nav_routing.py actualizado con la nueva sección.

## MCP Server (MYK-408)

- `src/mcp_server/` → `zk-collector-mcp` (entry point). Transporte stdio (default, sin puertos) u HTTP opt-in `ZK_COLLECTOR_MCP_HTTP=1` bind 127.0.0.1:9248. Solo lectura: `attendance_stats`, `list_punches`, `list_devices`, `list_employees` via Bearer a WebGUI. Token en `ZK_COLLECTOR_API_TOKEN`. Tests: `tests/test_mcp_server.py`.

## Hash Chain (MYK-422)

- `src/buffer/integrity.py`: `compute_hash_chain(prev_hash, record) -> sha256`. `buffer_attendance_hashchain` tabla + trigger en migracion `buffer/010_attendance_integrity.sql`. Endpoint `/api/attendance/integrity` verifica cadena completa. Tests: `tests/test_attendance_integrity.py`.

## Retención Legal (MYK-419/428)

- `configs/collector.yaml.example` + `configs/collector.schema.json`: `retention_days` (default 790 = 26 meses, min 730 validado en `_validate`). Borrado SOLO manual (opt-in) con exportación JSON previa verificada (`export_path`) y bitácora `retention_audit` (con `export_path`).
- MYK-428 archive-and-purge: overflow NO borra — archiva synced viejos en `attendance_archive` (consultables via `get_archived_records`, audit `archive_overflow`); purga conformante = `purge_archived_older_than` (solo archivados, export primero). `mark_sync_failed` tras 5 intentos marca `sync_failed=1` (NUNCA `synced=1`): quedan fuera de la cola y se revisan con `get_failed_records`; nunca archivados/purgados.
- Tests: `tests/test_buffer.py`, `tests/integration/test_e2e_flow.py` (RT-1), `tests/test_config.py`.

## Timestamps TZ (MYK-420)

- `/api/attendance/stats` y `/attendance/api/attendance` devuelven ISO-8601 con offset (`America/Mexico_City` default). Collector guarda UTC; WebGUI convierte a zona configurada. Tests: `tests/test_attendance_stats.py`.

## Reportes Full-Width (MYK-404 items 1-2)

- Todas las secciones de reportes usan ancho completo + responsive. CSS en `templates/reports/stats.html`. Tests: `tests/test_nav_routing.py` incluye checks de layout.

## Password Reset (MYK-145/170)

- SMTP removido del MVP (Option B). `/forgot-password` y `/reset-password` existen en `auth.py` y templates, wiring SMTP comentado en `docker-entrypoint.sh` (MYK-216). Board decision MYK-218: continue sprint.

## Emulador en Deploy (MYK-219/228)

- `docker-compose.yml` profile `mock` levanta emulador TCP :4370 + collector. Collector en live pollea emulador; registros sintéticos visibles en `/attendance`. `mock/zk_emulator.py` + `mock/attendance_seed.json`.

## Nómina Digital SAT (MYK-439)

- Monitor de readiness + schema export por trabajador/periodo. Doc: `docs/nomina_digital_readiness.md`, `docs/openapi.yaml` tag `nomina`.

## Compliance 2027 (MYK-410)

- Research canónico: `docs/compliance_nomina_2027.md`. Registro electrónico de jornada MX (NOM-035, LFT, CST, SAT). Backlog MYK-426–438.

---

*Actualizado con cada merge a master. Source of truth para agents.*
