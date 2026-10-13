# Sprint 2 — ZK-Collector: Hacer que el MVP FUNCIONE (Real + Scope Update)

**Sprint Goal:** Arrancar collector en prod, unificar fuente de verdad de devices, exponer asistencia + export CSV, CI verde, **emulador ZKTeco (P0-0)**  
**Dates:** 2026-10-13 (Mon) → 2026-10-17 (Fri)  
**Cadence:** Weekly sprint | Planning Mon 09:00 | Daily 10:00 | Review+Retro Fri 16:00

> **Scope Update (Dueño 2026-10-13):** No hay reloj físico → Emulador P0-0 habilita TODO lo verificable. P1 se expande a WebUI ABC + Asistencia completa (7 módulos). Verificación SIEMPRE contra deploy + emulador.

---

## Sprint Backlog (P0 — 6 items críticos)

| Order | Issue ID | Task | Priority | Assignee (Agent) | Criterio de Salida (verificable) |
|-------|----------|------|----------|------------------|----------------------------------|
| 0 | **MYK-172** | **P0-0: Emulador ZKTeco (Python TCP :4370)** | Critical | **backend-dev** (lead) + **devops** | Collector conecta a emulador, pollea asistencia sintética, registros aparecen en `/attendance` del deploy |
| 1 | **MYK-164** | **P0-1: Collector arranca en contenedor (supervisord dual)** | Critical | **devops** (lead) + **backend-dev** | `docker logs zk-collector \| grep -E "Polling|Attendance Collector Iniciado"` muestra polling activo cada 300s |
| 2 | **MYK-165** | **P0-2: Una fuente de verdad devices (collector → WebGUI DB)** | Critical | **backend-dev** (lead) | Device agregado vía UI → siguiente poll cycle (≤300s) aparece en logs |
| 3 | **MYK-166** | **P0-3: Página asistencia WebGUI (tabla + filtros + paginación)** | Critical | **frontend-dev** (lead) + **backend-dev** | `curl http://10.0.0.16:8081/attendance` renderiza tabla; filtros fecha/user/device funcionan |
| 4 | **MYK-167** | **P0-4: Export CSV real desde página asistencia** | Critical | **backend-dev** (lead) | `curl -u admin:pass "http://10.0.0.16:8081/attendance/export?format=csv" \| head -1 \| grep "ID,Usuario,Fecha/Hora"` = 1 |
| 5 | **MYK-162** | **P0-5: CI verde (ruff=0 → docker/smoke/compose corren)** | Critical | **devops** (ya asignado) | GitHub Actions: todos los jobs verdes (lint, type-check, unit, integration, coverage, security, docker) |

---

## Definition of Done (Gate — Board Policy)

Una tarea está **Done** SOLO cuando:
- [ ] Código mergeado a `feature/myk-92-dashboard-modernization` (o `master` post-merge)
- [ ] **Todos los jobs CI pasan** (lint, type-check, unit, integration, coverage-check, security-scan, build-and-test-docker)
- [ ] Code review aprobado por ≥1 reviewer
- [ ] QA verificado (tester sign-off en escenarios de integración)
- [ ] Si afecta deploy: **devops verificado** docker-compose / imagen docker en target platform (LXC 108 / Coolify)
- [ ] **Evidencia reproducible**: (1) commit SHA, (2) output CI/PR, (3) verificación contra `http://10.0.0.16:8081` o `https://zk-receiver.tail5276ec.ts.net`

---

## Capacidad y Riesgos

| Riesgo | Mitigación |
|--------|------------|
| Collector y WebGUI comparten SQLite (buffer + webgui DB) | Usar BD separadas: `/app/data/buffer.db` (collector) y `/app/data/webgui.db` (WebGUI) — ya están separadas en código |
| Ruff lint falla y bloquea CI completo | Fix ruff PRIMERO (MYK-162) — desbloquea todo lo demás |
| No hay reloj ZKTeco real | **Emulador P0-0** (mock/zk_mock) + fixture tests integración — reemplaza device real |
| Device passwords en DB WebGUI deben encriptarse | `src/webgui/database.py` ya usa Fernet via `src.security.encryption` |
| Cambio de `configs/collector.yaml` → WebGUI DB requiere migración | Script one-shot en `docker-entrypoint.sh` para migrar devices existentes |
| Emulador debe implementar subset pyzk real | `mock/zk_emulator.py` — connect, get_time, get_users, get_attendance, disconnect, timeouts |

---

## Daily Standup Protocol (10:00 Mon–Fri)

Cada assignee posta comentario de 3 líneas en su issue:
```
1. Done ayer: <qué>
2. Bloqueado por: <issue/título o "none">
3. Siguiente: <acción concreta>
```
PM (coffee) agrega resumen en issue de coordinación del sprint.

---

## Sprint Review + Retro (Friday 16:00)

**Review:** Verificar cada item contra Definition of Done → disposition al board con evidencia  
**Retro:** 3 funcionaron / 3 fallaron / 3 acciones concretas → documentar en `RETRO-2.md` + post 1 línea c/u a SHARED MEMORY  
**Carryover:** Items no terminados vuelven al backlog **SIN asignar** (next planning re-evalúa)

---

## Asignaciones por Routing Map

| Issue | Especialista | Área |
|-------|--------------|------|
| MYK-172 (P0-0) | backend-dev (emulador TCP, protocolo pyzk subset) + devops (docker-compose mock profile) | Backend + Infra |
| MYK-164 (P0-1) | devops (Dockerfile, supervisord, entrypoint) + backend-dev (collector init) | Infra + Core |
| MYK-165 (P0-2) | backend-dev (collector.read_devices_from_webgui_db) | Backend |
| MYK-166 (P0-3) | frontend-dev (template attendance/list.html + JS) + backend-dev (registrar blueprint, buffer_repo) | Frontend + Backend |
| MYK-167 (P0-4) | backend-dev (registrar blueprint attendance, wiring export) | Backend |
| MYK-162 (P0-5) | devops (ya asignado) | DevOps |

---

## Entregables del Sprint (commit + verificación)

| Issue | Commit SHA (pendiente) | CI Run (pendiente) | Deploy Verification (pendiente) |
|-------|------------------------|--------------------|----------------------------------|
| MYK-172 | — | — | Collector → emulador → `/attendance` muestra registros sintéticos |
| MYK-164 | — | — | `docker logs zk-collector \| grep "Polling"` |
| MYK-165 | — | — | UI add device → logs show polling |
| MYK-166 | — | — | `curl /attendance` → tabla HTML |
| MYK-167 | — | — | `curl /attendance/export?format=csv` → CSV válido |
| MYK-162 | — | — | GitHub Actions all green |

---

## Notas de Implementación Clave

### MYK-172 (P0-0): Emulador ZKTeco
- **Ubicación**: `mock/zk_emulator.py` (nuevo) — servidor TCP :4370
- **Protocolo subset pyzk**: `connect()`, `enable_device()`, `get_time()`, `get_users()`, `get_attendance()`, `disconnect()`
- **Historial configurable**: `MOCK_ATTENDANCE_RECORDS` env var o archivo JSON con marcas sintéticas
- **Fixtures**: `tests/fixtures/mock_device.py` para tests de integración
- **Docker-compose**: profile `"mock"` levanta `zk-emulator` en puerto 4370, collector apunta a `zk-emulator:4370`
- **Criterio**: Collector en contenedor conecta a `zk-emulator:4370`, pollea, guarda en buffer, `/attendance` muestra datos

### MYK-164 (P0-1): Collector en contenedor
- **Dockerfile**: `CMD ["/usr/bin/supervisord", "-c", "/etc/supervisor/conf.d/supervisord.conf"]` (ya está)
- **supervisord.conf**: Dos programas `zk-collector` + `zk-webgui` (ya están)
- **docker-entrypoint.sh**: Validar env vars `ZK_ADMIN_PASSWORD`, `ENCRYPTION_KEY` (ya está)
- **GAP**: `zk-collector` command usa `--config /app/configs/collector.yaml` pero debe leer devices de WebGUI DB (ver MYK-165)

### MYK-165 (P0-2): Una fuente de verdad
- **Opción A (recomendada)**: Collector lee `webgui.db` tabla `devices` cada poll cycle (caché 60s)
- **Opción B**: WebGUI escribe `configs/collector.yaml` (mounted read-only → no viable)
- **Implementación**: `AttendanceCollector._initialize_devices()` → query `webgui.devices` WHERE enabled=1

### MYK-166 (P0-3): Página asistencia
- Blueprint `attendance_bp` ya existe en `src/webgui/routes/attendance.py` con `/attendance` y `/api/attendance`
- **Falta**: Registrar blueprint en `src/webgui/server.py` + inyectar `buffer_repo` en `current_app`
- **Template**: `templates/attendance/list.html` — crear con Tailwind + Alpine.js (tabla, filtros, paginación)

### MYK-167 (P0-4): Export CSV
- Endpoint `/attendance/export` ya existe en `attendance.py` con streaming CSV + UTF-8 BOM
- **Falta**: Registrar blueprint + botón en template `list.html`

### MYK-162 (P0-5): CI verde
- `ruff check src/ tests/` = 0 → desbloquea `build-and-test-docker`, `integration-tests`, `coverage-check`
- Verificar coverage ≥80% en core modules (ya configurado en `ci.yml:coverage-check`)

---

## P1 Expandido — Backlog para Sprint 3+ (Scope Update Dueño)

| Módulo | Issues Hijos (a crear en Sprint 3 Planning) | Verificación (Deploy + Emulador) |
|--------|---------------------------------------------|----------------------------------|
| **P1-1: Colaboradores (ABC)** | MYK-173: Model/API empleados, MYK-174: UI CRUD empleados, MYK-175: Vinculación user_id reloj | `POST /api/employees` + UI CRUD + vinculación a emulador `get_users()` |
| **P1-2: Gestión Ausencias** | MYK-176: Model/API ausencias, MYK-177: Workflow aprobación, MYK-178: UI calendario + evidencia | `POST /api/absences` + aprobación + motor reglas consume |
| **P1-3: Motor Reglas Asistencia** | MYK-179: Config turnos, MYK-180: Job clasificación nocturna, MYK-181: Bandeja revisión + audit trail | Job clasifica → `GET /api/attendance/review` → `POST /resolve` con audit |
| **P1-4: Estadísticas/Dashboard** | MYK-182: API stats/KPIs, MYK-183: Dashboard UI + Chart.js, MYK-184: Export TODO reporte | Dashboard renderiza KPIs + charts + botones export CSV/Excel |
| **P1-5: Alertas Eráticas** | MYK-185: Motor reglas alertas, MYK-186: Job evaluación, MYK-187: UI alertas dashboard + log | `POST /api/alerts/rules` → job evalúa → dashboard badge alertas |
| **P1-6: Password Reset** | MYK-170 (existente): SMTP real o remover | Decisión board → flujo completo o 404 |
| **P1-7: Tests Integración + Coverage** | MYK-171 (existente): Tests E2E flujo completo | `pytest` coverage ≥80% core modules, CI all green |

---

## Próximos Pasos (post Sprint 2 → Sprint 3 Planning)

Si P0 completado con evidencia:
1. **Sprint 3 Planning**: Descomponer P1-1 a P1-7 en issues hijos con criterios verificables
2. **MYK-173 a MYK-187**: Crear issues hijos por módulo (ver tabla arriba)
3. **Mantener P0-0 emulador** como base de verificación para todos los P1