# ZK-Collector Backlog — Sprint Planning Source (REAL, auditado)

**Status:** Post-diagnóstico MYK-163 — **NO es MVP**  
**Branch:** master @ 312a24d (base), feature/myk-92-dashboard-modernization (working)  
**Last Updated:** 2026-10-13

---

## 📋 Diagnóstico Crítico (verificable en master @ 312a24d)

| # | Hallazgo | Evidencia |
|---|----------|-----------|
| 1 | Collector **NUNCA corre en prod**: Dockerfile CMD = solo gunicorn; `src/main.py` (AttendanceCollector: poll loop 300s) no se invoca | `Dockerfile:40`, `supervisord.conf:11` arranca collector pero `CMD` gunicorn sobrescribe |
| 2 | **Desintegración devices**: WebGUI guarda en su SQLite (`webgui/database.py`), collector lee `configs/collector.yaml` (read-only). Devices de UI **JAMÁS se pollean** | `src/core/collector.py:65` vs `src/webgui/database.py:29-41` |
| 3 | **CERO vista de asistencia**: no hay rutas/templates para listar `attendance_buffer` | `grep -r attendance templates/ = vacío` |
| 4 | **Export CSV/Excel: CERO código** en `src/` (`grep -r csv\|excel\|xlsx src/ = vacío`). MYK-146, MYK-129 reportados "done" | Verificar: `src/webgui/routes/attendance.py` existe pero NO está registrado en `server.py` |
| 5 | **Auto-discovery: CERO código** en `src/`. MYK-145 reportado "all acceptance criteria met" | `src/zk_client/discovery.py` existe pero NO se usa |
| 6 | **"239 tests, 86.84% coverage" (MYK-144): FALSO** — master tiene 16 tests en 2 archivos (0.28s). Jobs docker/smoke/compose de CI **nunca corren** porque ruff lint falla | `.github/workflows/ci.yml` gates |
| 7 | **BACKLOG.md y SPRINT-1.md NUNCA existieron en master** — solo en feature branch | `git show master:BACKLOG.md` → not found |
| 8 | **"supervisord manages both"**: Dockerfile SÍ tiene supervisord PERO `CMD` apunta a gunicorn directo, no a supervisord | `Dockerfile:40-41` |
| 9 | Password reset: ruta `/forgot-password` existe pero sin SMTP ni flujo verificado | `src/webgui/routes/auth.py` |

---

## 🚫 Definition of Done ENDURECIDA (Board Policy — aplica YA)

Cada disposition a **done** REQUIERE evidencia reproducible:
1. **Commit SHA** con el cambio
2. **Output real** de tests/CI en el PR
3. **Verificación** contra deploy: `http://10.0.0.16:8081` o `https://zk-receiver.tail5276ec.ts.net`

Reportes con métricas inventadas o archivos inexistentes = fallo de proceso + revocación del done. El board AUDITARÁ cada claim.

---

## 🎯 BACKLOG REAL — Priorizado por Impacto (P0 = producto no funciona)

### P0 — Bloqueadores de MVP (sin esto el producto NO funciona)

| ID | Título | Descripción | Criterio de Aceptación (verificable) | Asignación (routing map) |
|----|--------|-------------|--------------------------------------|--------------------------|
| **P0-1** | Collector arranca en contenedor junto a WebGUI | `supervisord` gestiona ambos procesos: `zk-collector` (src/main.py) + `zk-webgui` (gunicorn). `docker-entrypoint.sh` valida env vars. | `docker logs zk-collector | grep -E "Polling|Attendance Collector Iniciado"` muestra polling activo cada 300s | **devops** (Dockerfile, supervisord, entrypoint) + **backend-dev** (collector integra con buffer) |
| **P0-2** | Una fuente de verdad de devices | Collector lee devices de la DB del WebGUI (`webgui/devices` table), NO de `configs/collector.yaml`. UI "Add Device" → siguiente poll cycle lo recoge. | 1. Agregar device vía UI → 2. `docker logs` muestra polling a esa IP en siguiente ciclo (≤300s) | **backend-dev** (collector → webgui DB) + **frontend-dev** (UI device CRUD ya existe) |
| **P0-3** | Página de asistencia en WebGUI | Tabla con filtros (fecha inicio/fin, user_id, device_ip) + paginación + ordenamiento. Consume `/api/attendance` (ya existe en `attendance.py` pero no registrado). | `curl -s http://10.0.0.16:8081/attendance | grep -c "tabla\|table\|asistencia"` > 0 y filtros funcionan | **frontend-dev** (template + wiring) + **backend-dev** (registrar blueprint, exponer buffer_repo) |
| **P0-4** | Export CSV real desde página asistencia | Botón "Exportar CSV" en página asistencia → descarga CSV con registros filtrados (UTF-8 BOM para Excel). Endpoint `/attendance/export?format=csv` ya existe en `attendance.py` pero no registrado. | `curl -s -u admin:pass "http://10.0.0.16:8081/attendance/export?format=csv" | head -1 | grep -c "ID,Usuario,Fecha/Hora"` = 1 | **backend-dev** (registrar blueprint attendance, wiring buffer_repo) |
| **P0-5** | CI verde: ruff = 0 (desbloquea docker/smoke/compose) | `ruff check src/ tests/` = 0 errores. Jobs `build-and-test-docker`, `integration-tests` corren y pasan. | GitHub Actions CI: todos los jobs verdes (lint, type-check, unit, integration, coverage, security, docker) | **devops** (ya asignado en MYK-162) |

### P1 — MVP Completo (funcionalidad core de usuario)

| ID | Título | Descripción | Criterio de Aceptación (verificable) | Asignación |
|----|--------|-------------|--------------------------------------|------------|
| **P1-1** | Vista usuarios del device | Mapear `user_id` del reloj (ej. "123") → nombre legible ("Juan Pérez"). CRUD en WebGUI + sync desde device (`ZKClient.get_users()`). | 1. `GET /api/device-users?device_ip=X` retorna `[{"user_id":"123","name":"Juan Pérez"}]` 2. Tabla asistencia muestra nombre, no solo ID | **backend-dev** (ZKClient.get_users + model) + **frontend-dev** (tabla users + join en attendance) |
| **P1-2** | Flujo E2E con reloj REAL | Verificar: UI → DB → collector → buffer → UI con dispositivo ZKTeco físico en LAN (humano da IP). | 1. Marcar entrada en reloj real 2. Poll cycle (≤300s) 3. `GET /api/attendance` muestra el registro 4. Export CSV lo incluye | **tester** (lead) + **backend-dev** (fixes) + **devops** (deploy) — **humano da IP reloj test** |
| **P1-3** | Password reset: SMTP real o quitar del MVP | Decidir con board: (a) SMTP real configurado + email llega, o (b) remover `/forgot-password` y `/reset-password` del MVP. | Si (a): `curl -X POST /forgot-password → email recibido → token válido → reset ok`. Si (b): rutas 404 y templates eliminados. | **backend-dev** (mail.py + token flow) + **devops** (SMTP secrets) |
| **P1-4** | Tests integración flujo completo + coverage REAL | Tests que cubran: UI login → add device → poll → buffer → attendance list → export. Coverage ≥80% en módulos core. | `pytest tests/integration/ -v --cov=src --cov-report=term-missing` → coverage ≥80% core modules; 0 flaky | **tester** (lead) + **backend-dev** (fixtures) |

### P2 — Post-MVP (planear después del sprint actual)

- Auto-discovery LAN (UDP broadcast 4370)
- Dashboard con gráficas (Chart.js)
- Reportes por rango de fechas avanzados
- Multi-device hardening (concurrencia, backoff, retry)
- Configuración de turnos/horarios (rules engine)

---

## 🔗 Referencias

- ROADMAP.md — Roadmap oficial v2.0
- MYK-163 — Diagnóstico completo + mandato sprint
- AGENTS.md — Convenciones del proyecto
- `.github/workflows/ci.yml` — Pipeline CI actual