# ADR-001: Modelo RBAC — usuarios, perfiles (roles) y permisos

- **Estado:** Proposed (merge a master vía PR)
- **Fecha:** 2026-10-25
- **Issue:** MYK-406 (padre MYK-403, item 5)
- **Decisores:** architect; revisión: owner + backend-dev

## Contexto

zk-collector hoy autentica con sesión Flask + JWT (Argon2id + PyJWT, `src/webgui/auth.py`),
pero la autorización es prácticamente inexistente:

- `users.role` existe (`migrations/001_initial_schema.sql`, `TEXT DEFAULT 'user'`) pero sin
  CHECK ni catálogo de valores válidos.
- `admin_required` (`src/webgui/middleware/auth.py`) compara `session["role"] == "admin"`
  y **no se usa en ninguna ruta**.
- `api_auth_required` valida el header `Authorization: Bearer` pero tiene un
  `TODO: Validar token con Auth class` — **no verifica la firma del JWT**.
- 13 rutas API (medical_leaves ×5, attendance_stats ×2, alerts ×6) llevan decorador; rutas de UI
  (`/colaboradores`, `/reportes`, `/devices`) y las APIs de employees/devices quedan
  protegidas solo por la verificación ad-hoc de sesión en `/`.

Se necesita RBAC real antes de crecer más surface (usuarios RRHH y supervisores verán datos
de asistencia sensibles).

## Decisión

### 1. Roles fijos (4), un rol por usuario

| Rol | Descripción |
|---|---|
| `admin` | Control total: usuarios, dispositivos, configuración, datos. |
| `rrhh` | Gestión de colaboradores (ABC), incapacidades y reportes. No toca dispositivos ni usuarios. |
| `supervisor` | Lectura de asistencia de su equipo y reportes. Sin escritura de datos maestros. |
| `auditor` | Solo lectura: reportes y logs de asistencia. Sin escritura ninguna. |

`users.role` conserva un solo valor (1:1 usuario↔rol). El valor legacy `user` se trata
como `auditor`-sin-escritura? **No**: en la migración 005 se normaliza
`UPDATE users SET role='auditor' WHERE role NOT IN ('admin','rrhh','supervisor','auditor')`,
y la capa app valida contra `ALLOWED_ROLES` en todo write path (SQLite no soporta
`ALTER TABLE ADD CONSTRAINT`; rebuild de tabla por un CHECK se considera riesgo > beneficio
— alternativa descartada). La normalización vive en la migración 008
(`migrations/008_rbac_roles.sql`), no en la 005 (ese slot ya lo ocupa `005_alerts.sql` en master).

**Alternativa descartada:** N:M `users↔roles↔permissions` con tablas `roles`,
`role_permissions`, `user_roles`. Para un collector self-hosted con 4 perfiles fijados por
producto, agrega 3 tablas, migraciones y UI de administración sin valor: el conjunto de
roles es cerrado y definido por el producto, no por el operador del deploy.

### 2. Permisos `recurso:acción` con mapa role→permisos en código

Permisos como strings gruesos (`employees:read`, `employees:write`,
`medical_leaves:read`, `medical_leaves:write`, `attendance:read`,
`reports:read`, `reports:export`, `devices:read`, `devices:write`,
`devices:sync`, `users:manage`, `settings:manage`, `audit:read`).

El mapa role→permisos vive en **código versionado** (`src/webgui/permissions.py`), no en BD:

| Permiso | admin | rrhh | supervisor | auditor |
|---|:--:|:--:|:--:|:--:|
| devices:read / devices:write / devices:sync | ✅ | ❌ | ❌ | ❌ |
| employees:read / employees:write | ✅ | ✅ | read | read |
| medical_leaves:read / write | ✅ | ✅ | read | read |
| attendance:read | ✅ | ✅ | ✅ | ✅ |
| reports:read / reports:export | ✅ | ✅ | ✅ | ✅ |
| users:manage | ✅ | ❌ | ❌ | ❌ |
| settings:manage | ✅ | ❌ | ❌ | ❌ |
| audit:read | ✅ | ❌ | ❌ | ✅ |

Funciones puras: `ROLES`, `ROLE_PERMISSIONS`, `has_permission(role, perm)`,
`role_permissions(role)`. Testeables sin BD.

**Alternativa descartada:** tabla `permissions` + `role_permissions` en SQLite. Config-in-DB
para un catálogo cerrado solo agrega superficie de migración/UI y riesgo de drift entre
nodos; el mapa en código es revisable en PR y testeable unitariamente. Si el producto
alguna vez exige roles custom por operador, se promueve a BD en un ADR-002 (el decorador
y la API no cambian).

### 3. Aplicación en rutas Flask: decorador `require`

`src/webgui/middleware/auth.py` gana:

- `require(*perms)` — rutas de UI (sesión). Verifica sesión; falta de permiso → flash +
  redirect a `/` (403 visual vía template). Anida con `login_required`.
- `api_require(*perms)` — rutas API (JWT). Reemplaza a `api_auth_required`: extrae el
  Bearer token, **verifica firma/expiración con `Auth.verify_access_token`** (cierra el
  TODO actual), lee `role` del payload (claim ya emitido por `generate_tokens`), resuelve
  permisos con `has_permission`. 401 sin token válido, 403 con token válido sin permiso.

Semántica: múltiples permisos = AND (todos requeridos). El rol se toma del token/session
claim, no se re-consulta la BD por request (evita un query por llamada); costo aceptado:
un cambio de rol aplica en la sesión tras re-login y en la API al expirar el access token
(30 min). Documentado en `docs/security.md`.

**Alternativa descartada:** `before_app_request` con tabla ruta→permiso central. Centraliza
pero es frágil con blueprints y dinámicas (`/colaboradores/<id>`); el decorador junto a la
ruta es el patrón Flask idiomático y visible en el diff del PR.

### 4. Token y sesión

- `Auth.generate_tokens` ya emite `role` en el access token: sin cambio de formato.
- Al login, `session["role"]` ya se setea (`routes/auth.py`): sin cambio.
- `admin_required` se deprecates en favor de `require("users:manage" | "settings:manage")`;
  se elimina cuando ninguna ruta lo referencie (hoy: cero usos).

### 5. Matriz de aplicación por blueprint (para los issues de implementación)

| Ruta/Blueprint | Permiso |
|---|---|
| `/` dashboard | login (cualquier rol) |
| `/auth/*` login/logout/forgot/reset | público |
| `/devices` UI + `/devices/*` | `devices:read`; crear/editar/sync → `devices:write` / `devices:sync` |
| `/api/devices/*` | igual que UI devices |
| `/colaboradores` UI | `employees:read`; write → `employees:write` |
| `/api/employees/*` | igual que UI employees |
| `/api/medical-leaves/*` | `medical_leaves:read`; write → `medical_leaves:write` |
| `/api/alerts/*` | `alerts:read` (lectura: auditor, rrhh; admin implícito); write (leer/resolver, preferencias) → `alerts:write` |
| `/attendance` UI, `/api/attendance/stats`, `/reportes*` | `reports:read`; `/export` → `reports:export` |
| `/health` | público |
| `/api` apidocs | login (cualquier rol) |
| CRUD usuarios (nuevo) | `users:manage` |
| Config SMTP/system (nuevo) | `settings:manage` |

## Consecuencias

- Positivas: autorización real y auditable; JWT finalmente verificado; matriz explícita y
  testeable; cero tablas nuevas (solo migración 008 de normalización de roles).
- Negativas: tocar todas las rutas existentes en un PR de backend (riesgo de 500 por
  decorador mal aplicado → mitigado con tests de matriz por rol y CI).
- El mapa en código hace que agregar un permiso exija PR (aceptado: es decisión de producto).

## Plan de verificación

- Unit tests del mapa de permisos (4 roles × permisos).
- Tests de ruta: por cada rol, request representativo de cada blueprint → 200/403/401
  esperados (parametrizado).
- Token inválido/expirado → 401 en todas las APIs protegidas.
- Regression: suite existente `pytest tests/unit/ -v` verde.

## Issues de implementación

Creados como issues hijos de MYK-406 (ver comentario en el issue): backend-dev
(migración+permissions, middleware, aplicación por blueprint, API usuarios+OpenAPI) y
frontend-dev (UI administración usuarios, gating de menús, 403).
