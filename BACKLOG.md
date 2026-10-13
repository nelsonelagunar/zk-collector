# ZK-Collector Backlog — Sprint Planning Source (REAL, auditado — Scope actualizado por dueño)

**Status:** Post-diagnóstico MYK-163 + Scope Update (dueño) — **NO es MVP**  
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
| **P0-0** | **Emulador ZKTeco (Python TCP :4370)** | Servidor mock que implementa subset protocolo pyzk: connect/enable, get_time, get_users, get_attendance (historial configurable), desconexiones/tiempos para retry. Entregable: `mock/` en repo + docker-compose profile "mock" + fixture tests integración. | Collector conecta al emulador, pollea asistencia sintética, registros aparecen en página asistencia del deploy. ESO es el E2E verificable sin hardware. | **backend-dev** (lead) + **devops** (docker-compose mock profile) |
| **P0-1** | Collector arranca en contenedor junto a WebGUI | `supervisord` gestiona ambos procesos: `zk-collector` (src/main.py) + `zk-webgui` (gunicorn). `docker-entrypoint.sh` valida env vars. | `docker logs zk-collector | grep -E "Polling|Attendance Collector Iniciado"` muestra polling activo cada 300s | **devops** (Dockerfile, supervisord, entrypoint) + **backend-dev** (collector integra con buffer) |
| **P0-2** | Una fuente de verdad de devices | Collector lee devices de la DB del WebGUI (`webgui/devices` table), NO de `configs/collector.yaml`. UI "Add Device" → siguiente poll cycle lo recoge. | 1. Agregar device vía UI → 2. `docker logs` muestra polling a esa IP en siguiente ciclo (≤300s) | **backend-dev** (collector → webgui DB) + **frontend-dev** (UI device CRUD ya existe) |
| **P0-3** | Página de asistencia en WebGUI | Tabla con filtros (fecha inicio/fin, user_id, device_ip) + paginación + ordenamiento. Consume `/api/attendance` (ya existe en `attendance.py` pero no registrado). | `curl -s http://10.0.0.16:8081/attendance | grep -c "tabla\|table\|asistencia"` > 0 y filtros funcionan | **frontend-dev** (template + wiring) + **backend-dev** (registrar blueprint, exponer buffer_repo) |
| **P0-4** | Export CSV real desde página asistencia | Botón "Exportar CSV" en página asistencia → descarga CSV con registros filtrados (UTF-8 BOM para Excel). Endpoint `/attendance/export?format=csv` ya existe en `attendance.py` pero no registrado. | `curl -s -u admin:pass "http://10.0.0.16:8081/attendance/export?format=csv" | head -1 | grep -c "ID,Usuario,Fecha/Hora"` = 1 | **backend-dev** (registrar blueprint attendance, wiring buffer_repo) |
| **P0-5** | CI verde: ruff = 0 (desbloquea docker/smoke/compose) | `ruff check src/ tests/` = 0 errores. Jobs `build-and-test-docker`, `integration-tests` corren y pasan. | GitHub Actions CI: todos los jobs verdes (lint, type-check, unit, integration, coverage, security, docker) | **devops** (ya asignado en MYK-162) |

### P1 — MVP Completo (WebUI con ABC + manejo completo de asistencia)

**NOTA:** El P1 se EXPANDE significativamente per scope update del dueño. Cada módulo se descompone en issues hijos con criterio verificable contra deploy + emulador.

| ID | Módulo | Descripción | Criterio de Aceptación (verificable macro) | Asignación |
|----|--------|-------------|--------------------------------------------|------------|
| **P1-1** | **Colaboradores (ABC)** | CRUD completo: nombre, ID, puesto, departamento, horario esperado, estado (activo/inactivo). Vinculación colaborador ↔ user_id del reloj (emulador devuelve users sintéticos). | 1. `POST /api/employees` crea colaborador con campos requeridos 2. `GET /api/employees` lista con paginación/filtros 3. `PUT /api/employees/:id/user_id` vincula a user_id de reloj 4. UI muestra tabla + modal create/edit/delete | **backend-dev** (model, API, validación) + **frontend-dev** (UI CRUD) |
| **P1-2** | **Gestión de Ausencias** | Vacaciones (rango fechas, aprobación, calendario), Incapacidades (tipo/días/evidencia archivo), Permisos/justificaciones. Excepciones alimentan motor de reglas (falta justificada ≠ falta injustificada). | 1. `POST /api/absences` crea ausencia con tipo/rango/evidencia 2. `GET /api/absences?employee_id=X` lista con estado aprobación 3. Aprobación/rechazo cambia estado 4. Motor de reglas consume ausencias para clasificar marcas | **backend-dev** (model, API, workflow aprobación) + **frontend-dev** (calendario, formularios, evidencia upload) |
| **P1-3** | **Motor de Reglas de Asistencia** | Turnos: hora entrada/salida esperada por colaborador, tolerancia retardo configurable. Clasificación automática: puntual / retardo / retardo grave / falta / salida temprana. **Revisión estricta**: detectar entrada sin salida, salida sin entrada, marcas duplicadas, marcas fuera de horario → bandeja de revisión con corrección manual + audit trail. | 1. Config turnos por colaborador (`PUT /api/employees/:id/shift`) 2. Job nocturno clasifica marcas del día anterior → `attendance_classified` 3. `GET /api/attendance/review` retorna marcas anómalas pendientes 4. `POST /api/attendance/review/:id/resolve` corrige con audit trail | **backend-dev** (lead: motor reglas, clasificación, job) + **frontend-dev** (bandeja revisión UI) |
| **P1-4** | **Estadísticas / Dashboard** | Dashboard: asistencia por periodo (día/semana/mes), por colaborador, por departamento. KPIs: % asistencia, retardos acumulados, minutos perdidos, faltas, ausentismo por colaborador. Export CSV/Excel de TODO reporte. | 1. `GET /api/stats/dashboard?period=week&dept=X` → KPIs + series temporales 2. `GET /api/stats/employee/:id?period=month` → detalle colaborador 3. Botones export CSV/Excel en cada vista 4. Charts (Chart.js) renderizan en dashboard | **frontend-dev** (lead: dashboard UI, charts) + **backend-dev** (API stats, agregaciones SQL) |
| **P1-5** | **Alertas de Comportamiento Erático** | Reglas configurables: N retardos en periodo móvil, tendencia llegadas cada vez más tarde, ausentismo creciente, marcas sospechosas (intervalos exactos idénticos = buddy punching), actividad horarios inusuales. Alertas visibles en dashboard + log de alertas. | 1. `POST /api/alerts/rules` crea regla (tipo, umbral, periodo) 2. Job evalúa reglas → `alerts_log` 3. `GET /api/alerts` lista con severidad/estado 4. Dashboard muestra badge alertas activas | **backend-dev** (motor evaluación reglas, job) + **frontend-dev** (alertas en dashboard, log UI) |
| **P1-6** | **Password reset: SMTP real o quitar del MVP** | Decidir con board: (a) SMTP real + email llega, o (b) remover `/forgot-password` y `/reset-password`. | Si (a): flujo completo funciona. Si (b): rutas 404, templates eliminados. | **backend-dev** (mail.py + token flow) + **devops** (SMTP secrets) — **requiere decisión board** |
| **P1-7** | **Tests integración flujo completo + coverage REAL** | Tests: UI login → add device → poll (emulador) → buffer → attendance list → export → ABC colaboradores → ausencias → motor reglas → stats → alerts. Coverage ≥80% core modules. | `pytest tests/ -v --cov=src --cov-report=term-missing` → coverage ≥80% core/buffer/sync/config/zk_client/webgui; 0 flaky; CI all green | **tester** (lead) + **backend-dev** (fixtures, mocks) |

### P2 — Post-MVP (planear después del sprint actual)

- Auto-discovery LAN (UDP broadcast 4370)
- Dashboard con gráficas avanzadas (ya en P1-4 base)
- Reportes por rango de fechas avanzados (ya en P1-4 base)
- Multi-device hardening (concurrencia, backoff, retry)
- Configuración de turnos/horarios (ya en P1-3 base)
- Multi-tenant SaaS (v2.1 roadmap)
- Payroll export México (v2.2 roadmap)

---

## 🔗 Referencias

- ROADMAP.md — Roadmap oficial v2.0 (alcance histórico, NO refleja scope actual)
- MYK-163 — Diagnóstico completo + mandato sprint + scope update dueño
- AGENTS.md — Convenciones del proyecto
- `.github/workflows/ci.yml` — Pipeline CI actual

---

## 📌 Notas de Scope Update (Dueño — 2026-10-13)

1. **No hay reloj físico** → Emulador P0-0 habilita TODO lo verificable (reemplaza P1-2 original)
2. **Alcance real = WebUI ABC + Asistencia completa** (no solo "ver registros")
3. **P1 se expande** a 7 módulos mayores (P1-1 a P1-7) — cada uno se descompone en issues hijos en sprint planning
4. **Verificación SIEMPRE contra deploy + emulador** — criterios usan emulador como device sintético