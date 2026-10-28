# API Inventory — Bearer Auth Endpoints (MYK-407)

Generado: 2026-10-28 | Ref: feature/myk-407-api-tokens-endpoints (9ac8f18)

## Resumen

| Tag | Endpoint | Método | Auth | Scopes | Descripción |
|-----|----------|--------|------|--------|-------------|
| tokens | `/auth/api/tokens` | GET | Bearer (PAT/JWT) | read | Lista PATs del usuario (admin ve todos) |
| tokens | `/auth/api/tokens` | POST | Bearer (PAT/JWT) | write (admin session) | Crea PAT (token plano devuelto 1 vez) |
| tokens | `/auth/api/tokens/{id}` | DELETE | Bearer (PAT/JWT) | write | Revoca PAT por id |
| devices | `/api/devices` | GET | Bearer (PAT/JWT) | read | Estado de dispositivos (summary online/offline) |
| devices | `/api/devices/{id}` | GET | Bearer (PAT/JWT) | read | Estado de un dispositivo por id |
| devices | `/api/employees` | GET | Bearer (PAT/JWT) | read | Lista paginada de colaboradores |
| devices | `/api/employees` | POST | Bearer (PAT/JWT) | write | Crea colaborador |
| devices | `/api/employees/{id}` | GET | Bearer (PAT/JWT) | read | Obtiene colaborador por id |
| devices | `/api/employees/{id}` | PUT | Bearer (PAT/JWT) | write | Actualiza colaborador (parcial) |
| devices | `/api/employees/{id}` | DELETE | Bearer (PAT/JWT) | write | Baja lógica (status=inactive) |
| devices | `/api/employees/{id}/device-links` | GET | Bearer (PAT/JWT) | read | Lista device_links del colaborador |
| devices | `/api/employees/{id}/device-links` | POST | Bearer (PAT/JWT) | write | Crea device_link |
| devices | `/api/employees/{id}/device-links` | DELETE | Bearer (PAT/JWT) | write | Elimina device_link |
| attendance | `/api/attendance` | GET | Bearer (PAT/JWT) | read | Registros de asistencia paginados/filtrados |
| attendance | `/api/attendance/stats` | GET | Bearer (PAT/JWT) | read | KPIs asistencia (MYK-241) |
| attendance | `/api/attendance/stats/export` | GET | Bearer (PAT/JWT) | read | Export CSV/XLSX KPIs (MYK-241) |
| buffer | `/api/buffer/retention` | GET | Bearer (PAT/JWT) | read | Retención efectiva para QA (MYK-505) |
| medical-leaves | `/api/medical-leaves` | GET | Bearer (PAT/JWT) | — | Lista incapacidades |
| medical-leaves | `/api/medical-leaves` | POST | Bearer (PAT/JWT) | — | Crea incapacidad |
| medical-leaves | `/api/medical-leaves/{id}` | GET | Bearer (PAT/JWT) | — | Obtiene incapacidad |
| medical-leaves | `/api/medical-leaves/{id}` | PUT | Bearer (PAT/JWT) | — | Actualiza incapacidad |
| medical-leaves | `/api/medical-leaves/{id}` | DELETE | Bearer (PAT/JWT) | — | Elimina incapacidad |
| alerts | `/api/alerts` | GET | Bearer (PAT/JWT) | — | Lista alertas HR-6 |
| alerts | `/api/alerts` | POST | Bearer (PAT/JWT) | — | Crea alerta |
| alerts | `/api/alerts/{id}` | GET | Bearer (PAT/JWT) | — | Obtiene alerta |
| alerts | `/api/alerts/{id}` | PUT | Bearer (PAT/JWT) | — | Actualiza alerta |
| alerts | `/api/alerts/{id}` | DELETE | Bearer (PAT/JWT) | — | Elimina alerta |
| alerts | `/api/alerts/{id}/evaluate` | POST | Bearer (PAT/JWT) | — | Evalúa alerta manual |
| alerts | `/api/alerts/{id}/acknowledge` | POST | Bearer (PAT/JWT) | — | Acknowledge alerta |

## Endpoints Legacy (WebGUI session cookie, sin Bearer)

| Tag | Endpoint | Método | Auth | Notas |
|-----|----------|--------|------|-------|
| devices | `/devices/api/devices` | GET | sessionCookie | UI: lista dispositivos configurados |
| devices | `/devices/api/devices` | POST | sessionCookie | UI: registra dispositivo |
| devices | `/devices/api/devices/{id}` | GET/PUT/DELETE | sessionCookie | UI: CRUD dispositivo |
| devices | `/devices/api/devices/test` | POST | sessionCookie | UI: test conectividad |
| devices | `/devices/api/devices/{id}/toggle` | POST | sessionCookie | UI: enable/disable polling |
| devices | `/devices/api/devices/{id}/status` | GET | sessionCookie | UI: status real-time |
| devices | `/devices/api/attendance` | GET | sessionCookie | UI: registros buffer |
| devices | `/devices/api/attendance/stats` | GET | sessionCookie | UI: stats buffer |
| devices | `/devices/api/attendance/export` | GET | sessionCookie | UI: export CSV |
| devices | `/devices/api/sync/status` | GET | sessionCookie | UI: sync status |
| devices | `/devices/api/sync/trigger` | POST | sessionCookie | UI: force sync |
| auth | `/auth/login` | POST | none | Login form |
| auth | `/auth/logout` | GET | sessionCookie | Logout |
| auth | `/auth/forgot-password` | GET/POST | none | Password reset request |
| auth | `/auth/reset-password` | GET/POST | none | Password reset form |
| auth | `/auth/api/forgot-password` | POST | none | API password reset request |
| auth | `/auth/api/reset-password` | POST | none | API password reset |

## Esquema de Tokens (PAT)

- **Emisión**: `POST /auth/api/tokens` (requiere sesión admin, scope `write` implícito en middleware)
- **Token opaco**: `secrets.token_urlsafe(32)` → hash SHA-256 en DB (`api_tokens.token_hash`)
- **Scopes**: `read`, `write` (write ⇒ read implícito)
- **Expiración**: configurable 1–365 días (default 90), `NULL` = sin expiración
- **Revocación**: `DELETE /auth/api/tokens/{id}` → `revoked_at` timestamp
- **Rate limit**: 60 req/min por token (in-memory sliding window, `src/webgui/middleware/auth.py:12-31`)
- **Verificación**: `ApiTokenService.verify_token(token, required_scope)` actualiza `last_used_at`

## Fallback JWT de Sesión

`api_auth_required` acepta también JWT de sesión WebGUI (`Authorization: Bearer <jwt>`) para compatibilidad con código existente. Los JWT tienen acceso completo (sin scope check). Ver `src/webgui/middleware/auth.py:89-137`.

## Gap Respecto a MYK-403 (Item 6 - Scope de este Issue)

| Faltante | Endpoint | Estado |
|----------|----------|--------|
| Razones sociales | `/api/companies/` (GET/POST) | En branch `feature/myk-411-razon-social-api-ui` (MYK-411) |
| Razones sociales | `/api/companies/{id}` (GET/PUT/DELETE) | En branch `feature/myk-411-razon-social-api-ui` (MYK-411) |
| Razones sociales | `/api/companies/{id}/devices` (GET/POST) | En branch `feature/myk-411-razon-social-api-ui` (MYK-411) |
| Password reset API | `/auth/api/forgot-password`, `/auth/api/reset-password` | Ya en master (MYK-303) — sin Bearer, sin scope |

## Pruebas (CI gate)

```bash
pytest tests/test_api_tokens.py -v
pytest tests/test_employees_routes.py -v
pytest tests/test_attendance_stats_routes.py -v
pytest tests/test_devices_test_route.py -v
# Suite completa
pytest --cov=src --cov-fail-under=80
ruff check src/
mypy src/
```

## OpenAPI

Spec actualizada en `docs/openapi.yaml` con:
- Tag `tokens` añadido
- Paths `/auth/api/tokens`, `/api/devices`, `/api/employees`, `/api/attendance`
- Security scheme `bearerAuth` (HTTP Bearer)
- Componentes `ApiToken`, `Employee` añadidos
- Responses `Unauthorized` estandarizada

## Próximos Pasos (Tracking)

1. Merge PR #?? (feature/myk-407-api-tokens-endpoints → master)
2. MYK-411: `/api/companies/*` endpoints (razon social CRUD + vinculación dispositivos)
3. Documentar en `docs/api.md` la sección "Bearer Token Authentication"
4. ✅ `/api/buffer/retention` read-only (MYK-505, zk-collector) — DONE