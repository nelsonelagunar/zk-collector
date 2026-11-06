# API Inventory — Bearer Auth Endpoints (MYK-407)

Generado: 2026-10-28 | Ref: feature/myk-407-api-tokens

## Resumen

| Tag | Endpoint | Método | Auth | Scopes | Descripción |
|-----|----------|--------|------|--------|-------------|
| tokens | `/auth/api/tokens` | GET | Bearer (PAT/JWT) | read | Lista PATs del usuario (admin ve todos) |
| tokens | `/auth/api/tokens` | POST | Bearer (PAT/JWT) | write (sesión admin) | Crea PAT (token plano devuelto 1 vez) |
| tokens | `/auth/api/tokens/{id}` | DELETE | Bearer (PAT/JWT) | write | Revoca PAT por id |

## Endpoints existentes ya protegidos con Bearer (previos a MYK-407)

| Tag | Endpoint | Método | Auth | Descripción |
|-----|----------|--------|------|-------------|
| attendance | `/api/attendance/stats` | GET | bearerAuth | KPIs asistencia (MYK-241) |
| attendance | `/api/attendance/stats/export` | GET | bearerAuth | Export CSV/XLSX KPIs (MYK-241) |
| attendance | `/api/employees` | GET | bearerAuth | Lista paginada de colaboradores (MYK-221) |
| attendance | `/api/employees` | POST | bearerAuth | Crea colaborador (MYK-221) |
| attendance | `/api/employees/{id}` | GET | bearerAuth | Obtiene colaborador por id |
| attendance | `/api/employees/{id}` | PUT | bearerAuth | Actualiza colaborador (parcial) |
| attendance | `/api/employees/{id}` | DELETE | bearerAuth | Baja lógica (status=inactive) |
| attendance | `/api/employees/{id}/device-links` | GET | bearerAuth | Lista device_links |
| attendance | `/api/employees/{id}/device-links` | POST | bearerAuth | Crea device_link |
| attendance | `/api/employees/{id}/device-links` | DELETE | bearerAuth | Elimina device_link |
| devices | `/devices/api/devices` | GET | bearerAuth | Lista dispositivos configurados |
| devices | `/devices/api/devices` | POST | bearerAuth | Registra dispositivo |
| devices | `/devices/api/devices/{id}` | GET/PUT/DELETE | bearerAuth | CRUD dispositivo |
| devices | `/devices/api/devices/test` | POST | bearerAuth | Test conectividad |
| devices | `/devices/api/devices/{id}/toggle` | POST | bearerAuth | Enable/disable polling |
| devices | `/devices/api/devices/{id}/status` | GET | bearerAuth | Status real-time |

## Endpoints Legacy (WebGUI session cookie, sin Bearer)

| Tag | Endpoint | Método | Auth | Notas |
|-----|----------|--------|------|-------|
| auth | `/auth/login` | POST | none | Login form |
| auth | `/auth/logout` | GET | sessionCookie | Logout |
| auth | `/auth/forgot-password` | GET/POST | none | Password reset request |
| auth | `/auth/reset-password` | GET/POST | none | Password reset form |
| auth | `/auth/api/forgot-password` | POST | none | API password reset request |
| auth | `/auth/api/reset-password` | POST | none | API password reset |
| buffer | `/api/buffer/retention` | GET | bearerAuth | Retención efectiva para QA (MYK-505, ya en master via #121) |

## Esquema de Tokens (PAT)

- **Emisión**: `POST /auth/api/tokens` (requiere sesión admin)
- **Token opaco**: `secrets.token_urlsafe(32)` → hash SHA-256 en DB (`api_tokens.token_hash`)
- **Scopes**: `read`, `write` (write ⇒ read implícito)
- **Expiración**: configurable 1–365 días (default 90), `NULL` = sin expiración
- **Revocación**: `DELETE /auth/api/tokens/{id}` → `revoked_at` timestamp
- **Rate limit**: 60 req/min por token (in-memory sliding window, `src/webgui/middleware/auth.py`)
- **Verificación**: `ApiTokenService.verify_token(token)` valida hash, expiración, revocación y scope

## Autenticación Bearer

`api_require(*perms)` en `src/webgui/middleware/auth.py` acepta:
1. Sesión WebGUI activa (`user_id` en session)
2. Bearer JWT (`Auth.verify_access_token`)
3. Personal Access Token (PAT) verificado contra `api_tokens` (hash SHA-256, scopes, revocación)

Cuando se envía `Authorization: Bearer <token>`, el token se valida primero (PAT o JWT); la sesión no lo sustituye.

## Pruebas (CI gate)

```bash
pytest tests/test_api_tokens.py -v
# Suite completa
pytest --cov=src --cov-fail-under=80
ruff check src/
```

## OpenAPI

Spec actualizada en `docs/openapi.yaml` con:
- Tag `tokens` añadido
- Path `/auth/api/tokens` (GET/POST/DELETE) con `bearerAuth`
- Componente `ApiToken` añadido
- `bearerAuth` documentado como JWT o PAT opaco
