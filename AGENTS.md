# AGENTS.md — ZK-Collector Project

## Project Identity
ZK-Collector is an open-source Python application that enables businesses to reuse their existing ZKTeco biometric attendance devices with a modern web dashboard, eliminating the need for expensive proprietary software licenses.

## Stack
- **Language:** Python 3.12+
- **Web Framework:** Flask 3.x + Tailwind CSS + Alpine.js
- **Database:** SQLite (collector) / PostgreSQL (SaaS, future)
- **ZK Protocol:** pyzk library (TCP/UDP port 4370)
- **Auth:** Argon2id + PyJWT
- **Deployment:** Docker (ARM64/x86_64), Raspberry Pi 3/4
- **CI/CD:** GitHub Actions

## Architecture Decisions
1. **Offline-first:** SQLite buffer ensures no data loss during network outages
2. **Polling model:** Collector polls devices at configurable intervals (default 60s)
3. **Sync-on-change:** Only new records get synced to cloud platform
4. **WebGUI bundled:** Flask app runs alongside collector in same process
5. **Device-agnostic:** pyzk abstracts ZKTeco protocol differences

## Hard Rules
1. **NEVER store device passwords in plaintext** — use Fernet encryption (cryptography lib)
2. **NEVER expose the collector port (4370) to the internet** — LAN-only device communication
3. **ALWAYS validate ZKTeco responses** — devices can return malformed data
4. **Test on real hardware before release** — emulators miss protocol edge cases
5. **Respect rate limits** — don't hammer devices; default 60s polling interval

## Repository Conventions
- Branch: `master` (default), features via `feature/<name>`
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- PRs: require CI pass + at least 1 review
- Issues: use templates (bug, feature, device compatibility report)

## Deploy
- **Development:** `pip install -e ".[dev]"` → `zk-collector --dev`
- **Docker:** `docker-compose up -d` (see `docker-compose.yml`)
- **Production (Pi):** systemd service (`deploy/zk-collector.service`)
- **Cloud:** Coolify app pointing at this repo's `master` branch

## Testing
```bash
# Unit tests
pytest tests/unit/ -v

# Integration (requires real device on LAN)
pytest tests/integration/ -v --device-ip=192.168.1.101

# Full suite
pytest --cov=src --cov-report=html
```

## Device Compatibility
Tested models (add to this list as community reports come in):
- ZKTeco K40 ✅
- ZKTeco U160 ✅
- ZKTeco X628 ✅
- ZKTeco iClock 3000 ✅
- ZKTeco SpeedFace V5L ⚠️ (partial — face recognition not supported)

## Key Files
- `src/zk/client.py` — ZKTeco device communication wrapper
- `src/core/collector.py` — Main orchestrator (poll → buffer → sync)
- `src/webgui/server.py` — Flask web dashboard
- `src/webgui/employees.py` — EmployeeRepository (colaboradores, ver `docs/employees.md`)
- `src/buffer/repository.py` — SQLite data access layer
- `src/sync/platform.py` — Cloud sync HTTP client
- `configs/devices.yaml` — Device configuration template

## HR Data Model (Sprint 3, migration 002)

### `employees` (migration 002_employees.sql, MYK-220)
Real collaborator registry — ABC (altas/bajas/cambios) base table.
- `id` PK, `employee_code` UNIQUE NOT NULL, `first_name`/`last_name` NOT NULL
- `email`, `phone`, `department`, `position`, `hire_date`, `notes`
- `status` CHECK IN ('active','inactive') DEFAULT 'active' — soft delete via status
- Indexes: `idx_employees_code(employee_code)`, `idx_employees_status(status)`

### `employee_device_links` (migration 002)
N:M bridge: one collaborador can hold N badges across devices.
- PK (employee_id, device_serial, device_user_id), FK employee_id → employees(id) ON DELETE CASCADE
- Indexes on `device_serial` and `device_user_id` (reverse lookup: device user → employee)

Migration 002 uses `IF NOT EXISTS` (idempotent, safe for re-run). CRUD helpers live in `src/webgui/database.py` (get_employee_by_code/id, get_employees, create/update/delete_employee, link/unlink employee↔device, device/employee lookups).

## Attendance Stats API (MYK-241)

- `GET /api/attendance/stats` (JSON) y `GET /api/attendance/stats/export` (CSV/XLSX) — Bearer auth.
- Filtros: `start_date`/`end_date` (YYYY-MM-DD), `employee_id`, `department`, `group_by=employee|department|company`; export añade `format=csv|xlsx`.
- KPIs sobre días hábiles (Lun–Vie): presentes, ausentes, retardos (primer entrada vs `ATTENDANCE_WORK_START`, default 09:00:00 — computo simple, el motor de reglas completo es MYK-224), incapacidades (`medical_leaves` activas), vacaciones (siempre 0 hasta que exista módulo de vacaciones), puntualidad % y ausentismo %.
- Reglas completas y response shape en `docs/attendance_stats.md`; contrato OpenAPI en `docs/openapi.yaml`.
- El buffer escribe timestamps ISO con `T` (`isoformat()`); el filtrado por fecha usa `substr(timestamp,1,10)` para soportar ambos formatos.
- Servicio puro en `src/webgui/attendance_stats.py` + rutas en `src/webgui/routes/attendance_stats.py`; tests `tests/test_attendance_stats*.py`.

## Reportes WebGUI (MYK-242)

- `GET /reportes` — dashboard de estadísticos de asistencia con filtros por rango de fechas,
  colaborador, departamento y `group_by` (employee|department|company), KPIs y graficas (CSS/SVG
  puro, sin librerias JS externas).
- Los numeros provienen de la misma implementacion de MYK-241
  (`routes/attendance_stats.compute_report`): el dashboard y `/api/attendance/stats` devuelven
  cifras identicas por construccion; `tests/test_attendance_stats_ui.py` compara las respuestas
  del dashboard contra la API punto a punto.
- Soporte JSON `/reportes/api/stats` y export CSV/XLSX `/reportes/export` con los mismos filtros
  que la API de MYK-241.

## Entorno de ejecucion Paperclip (workspaces)

Lecciones de MYK-227 (5 runs perdidos). Aplican a CUALQUIER agente:

- El clon del **proyecto** (`/home/paperclip/repos/<repo>`) puede estar montado **read-only** durante el run. No concluyas "el repo es read-only": revisa tu workspace.
- Trabaja en el clon del **workspace del agente**: `pwd`, o `~/.paperclip/instances/default/workspaces/<agent-id>/<repo>`. Verifica con `touch .wtest && rm .wtest` antes de editar.
- **Nunca** escribas codigo en `/tmp` scratch: se borra al terminar el run y el trabajo se pierde (fue la causa de 5 runs sin PR).
- Push: el clon del workspace trae credenciales **repo-local** en `origin`. Si `PAPERCLIP_GIT_TOKEN` viene vacio, **no reescribas la URL** con ese valor vacio (rompe el push); usa `git push` normal y verifica con `git ls-remote origin <rama>`.
- Flujo: `git fetch origin && git checkout -b feature/myk-<n>-<slug> origin/master` → implementa → tests (`ruff`, `mypy`, `pytest`) → commit → push → PR contra `master`.
- No dejes el cierre en un comentario: el issue solo pasa a `done` cuando el PR esta mergeado y el deploy verificado.

## Dashboard WebGUI (MYK-365)

- `GET /` autenticado (`index()` en `src/webgui/server.py`): stats vienen de DOS DBs —
  `devices_total`/`devices_online` de webgui.db (migrations), `pending_records` de buffer.db
  vía `app.buffer_repo.get_stats()["pending_sync"]` (tabla `attendance_records`).
- NUNCA consultar `attendance_buffer` en webgui.db: esa tabla NO existe en migrations 001-004
  (bug MYK-363, misma clase que MYK-250 — esquema vs DB del deploy).
- Tests: `tests/test_dashboard_index.py` — login válido → dashboard 200 con webgui.db creada
  solo desde migrations/ (layout Docker reproducido con tmp_path); CI rojo si vuelve a faltar.

## Password Reset (MYK-303, migration 004)

- Flujo forgot/reset vive SOLO en master desde MYK-303 — cualquier hotfix en vivo (templates/rutas editadas en el artifact) se pierde en el siguiente redeploy desde master: fix va SIEMPRE por PR a master primero.
- Rutas en `src/webgui/routes/auth.py` (blueprint `/auth`): `GET/POST /auth/forgot-password` (form), `GET/POST /auth/reset-password?token=...` Y `/auth/reset-password/{token}` (el form del template POSTea al path variant), `POST /auth/api/forgot-password` y `POST /auth/api/reset-password` (JSON).
- Tokens: SHA256 del token plano en `password_reset_tokens` (migration `004_password_reset_tokens.sql`), expiran en 1h, single-use, los previos se invalidan al pedir uno nuevo; comparación en tiempo constante (`Auth.verify_reset_token`). Contrato OpenAPI actualizado en el mismo PR.
- Email: `src/webgui/mail.py` `Mailer.from_config(smtp_*)` lee `system_config` (defaults `smtp_*` INSERT OR IGNORE en migration 004); sin SMTP configurado hace fallback a flash/log del enlace — el endpoint NUNCA revela si el email existe (anti-enumeración).
- Rate limit in-memory por email: 3 requests/hora (`reset_rate_limit_store()` para tests). Tests: `tests/test_password_reset_routes.py` (24 casos; en master sin fix fallan todos).
- Coverage config omite `src/webgui/routes/auth.py` del requisito — no bajar `fail_under=80` para cubrirlo con tests de integración triviales.

## Secciones WebGUI y Seed Demo (MYK-377)

- Todas las secciones del navbar (`/`, `/attendance`, `/reportes`, `/colaboradores`,
  `/devices`, `/users`, `/settings`, `/profile`) estan registradas en `create_app`
  (`src/webgui/server.py`). Las rutas indice usan `strict_slashes=False`:
  `/seccion` y `/seccion/` responden 200 directo (sin 308 del proxy).
- `/users`, `/settings` y `/profile` viven en `src/webgui/routes/{users_ui,settings_ui,profile_ui}.py`
  con templates que extienden `base.html` (siempre dentro del layout con menus).
  Paginas: `login_required`; mutaciones (alta/toggle usuario, update config): `admin_required`.
  `smtp_password` es write-only: nunca se muestra en `/settings`.
- `company_name` (system_config) se carga en `app.config["COMPANY_NAME"]` al arrancar;
  lo consume `/api/attendance/stats` (`group_by=company`) via `DEFAULT_COMPANY` fallback.
- Seed demo: `migrations/007_demo_seed.sql` — 120 colaboradores, 3 dispositivos,
  40 usuarios de reloj, 40 vinculos colaborador-reloj, 5 usuarios WebGUI demo
  (password `demo1234`, hash Argon2id precomputado) y empresa en system_config.
  OPT-IN: migraciones `*_demo_seed*.sql` solo aplican con `ZK_DEMO_SEED=1`
  (`Database._run_migrations`); el Dockerfile la deja ON, pytest/dev quedan sin seed.
  Idempotente por guards de llave natural (employee_code/username UNIQUE, links PK,
  devices por address). Tests: `tests/test_demo_seed.py`, `tests/test_nav_routing.py`.

## RBAC (ADR-001, MYK-412, migration 008)

- Roles fijos (catalogo cerrado): `admin`, `rrhh`, `supervisor`, `auditor` en `users.role`.
- `src/webgui/permissions.py`: `ALLOWED_ROLES`, `ROLE_PERMISSIONS` (matriz exacta del ADR-001)
  y funciones puras `has_permission(role, perm)` / `role_permissions(role)` — deny por defecto
  para roles desconocidos. Testeable sin BD (`tests/test_permissions.py`).
- `migrations/008_rbac_roles.sql`: normaliza roles legacy (`'user'`, NULL, otros) a `'auditor'`.
  Idempotente (solo UPDATE). NOTA: el ADR-001 dice "migracion 005", pero `005_alerts.sql` ya
  ocupaba el slot en master; la numeracion fisica manda (008).
- Validacion de rol es capa app (SQLite no soporta ADD CONSTRAINT): todo write path de
  `users` debe validar contra `ALLOWED_ROLES` (`/users/new` ya lo hace).
- Decoradores `require()`/`api_require()` y aplicacion por blueprint: issues hijos de
  MYK-406 (middleware, blueprint application, API usuarios) — NO implementados en MYK-412.

## Middleware RBAC (MYK-413)

- `require(*perms)` — rutas UI (sesión): sesión verificada como `login_required` y
  `has_permission(session["role"], perm)` para TODOS los permisos (AND). Sin sesión ->
  redirect al login; sin permiso -> flash + redirect a `/`. Roles desconocidos deniegan.
- `api_require(*perms)` — APIs: sesión WebGUI (`user_id`) O Bearer JWT verificado con
  `Auth.verify_access_token` (HS256, `type=access`, fail-closed sin `app.auth`). Rol desde
  `session["role"]` o claim `role` del payload. 401 credencial ausente/inválida/expirada,
  403 `{"error": "Insufficient permissions"}` sin permiso (JSON). Multi-permiso = AND.
- `g.api_user` SOLO se setea en el path JWT: handlers decorados que atienden también
  sesión NO deben leerlo directo (usar `getattr(g, "api_user", None)` o el rol de sesión).
- `api_auth_required` es alias deprecated de `api_require()` sin permisos (mismo
  comportamiento byte a byte que MYK-443); se elimina tras migrar usos (MYK-414).
  `admin_required` deprecated en favor de `require("users:manage"|"settings:manage")`.
- Aplicación por blueprint: MYK-414; API CRUD usuarios + OpenAPI: MYK-415.
  Tests: `tests/test_rbac_middleware.py` (33, parametrizados por rol).

## API Auth (MYK-443)

- `api_auth_required` (`src/webgui/middleware/auth.py`) valida de verdad desde MYK-443:
  sesión WebGUI activa (`user_id` en session, para los fetch same-origin del dashboard)
  O Bearer JWT firmado con `WEBGUI_SECRET_KEY` via `Auth.verify_access_token`
  (`type=access`, HS256). Todo lo demas responde 401 `{"error": ...}` (shape intacto).
  Fail-closed si la app no tiene `app.auth` (create_app siempre lo setea, server.py:70).
- Todos los blueprints API usan el decorador: `/api/employees` (anadido en MYK-443,
  antes estaba SIN decorador), `/api/medical-leaves`, `/api/attendance/stats`,
  `/api/alerts`. Los templates NUNCA mandan token falso: la cookie de sesión autentica.
- NO existe endpoint de emisión de JWT (login es solo sesión); mint externo =
  `Auth(secret).generate_tokens(user_id, username, role)`. Refresh tokens no sirven
  como access. Tests: `tests/test_api_auth_middleware.py` (401/200 por blueprint).
- Los endpoints JSON internos de UI (`/devices/api/*`, `/attendance/api/*`,
  `/colaboradores/api/*`, `/reportes/api/*`) quedaron SIN auth — seguimiento aparte.
