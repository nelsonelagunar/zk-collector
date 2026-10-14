# ZK-Collector BACKLOG.md — Sprint 2 Planning (Real)

**Fuente**: ROADMAP.md v2.0 + MYK-163 hallazgos críticos + Definition of Done endurecida
**Estado**: Basado en master @ 312a24d + branch fix/p0-1-supervisord-clean (78d1bfe)

---

## P0 — Sin esto el producto NO funciona (Sprint 2 scope)

| ID | Título | Descripción | Criterio de Aceptación (Verificable) | Asignado (Routing Map) |
|----|--------|-------------|--------------------------------------|------------------------|
| P0-0 | Emulador ZKTeco TCP :4370 | Emulador completo para CI/tests sin hardware real | `pytest tests/integration/test_emulator_integration.py -k "not full_cycle"` PASS; seed attendance_seed.json | **DONE** ✅ (MYK-177) |
| **P0-1** | **Collector arranca en contenedor (supervisord dual)** | Dockerfile usa supervisord para gunicorn + collector.main | `docker logs <container>` muestra "polling activo" cada 300s; src/main.py se invoca | **devops + backend-dev** (MYK-181 PR ready, blocked on GitHub auth) |
| **P0-2** | **Una fuente verdad devices: collector lee WebGUI DB** | Collector lee devices de webgui/database.py (SQLite) con cache 60s TTL | Device agregado por UI → polleado en siguiente ciclo (300s) | **backend-dev** (MYK-165, blocked by P0-1 merge) |
| **P0-3** | **Página asistencia WebGUI: tabla + filtros + paginación** | Ruta `/attendance` con tabla, filtros (fecha, user, device), paginación 25/page | Registros attendance_buffer visibles y navegables en :8081 | **frontend-dev** (MYK-166, DONE locally, blocked on P0-1 merge) |
| **P0-4** | **Export CSV real desde página asistencia** | Botón "Exportar CSV" descarga registros filtrados | CSV con columnas: user_id, name, device, timestamp, status, punch | **backend-dev** (MYK-167, blocked by P0-2) |
| **P0-5** | **CI verde: ruff=0 (gatea docker/smoke/compose)** | Ruff 0 errors en src/ tests/; jobs docker/smoke/compose corren | `ruff check src/ tests/` → 0; GitHub Actions CI verde | **DONE** ✅ (MYK-162) |

---

## P1 — MVP Completo (Post-Sprint 2 / Sprint 3)

| ID | Título | Descripción | Criterio de Aceptación | Asignado |
|----|--------|-------------|------------------------|----------|
| P1-1 | Vista usuarios del device | Mapear user_id del reloj con nombre en WebGUI | Device detail muestra lista usuarios del reloj | backend-dev |
| P1-2 | E2E con reloj ZKTeco REAL LAN | Flujo completo verificado con hardware real (IP indicada por humano) | Poll → buffer → UI → export funciona contra reloj físico | devops + tester |
| P1-3 | Password reset: SMTP real o remover del MVP | Decidir con board: implementar SMTP real (Infisical) o eliminar /forgot-password | Board decision recorded; implemented or removed | **board decision pending** (MYK-183/194) |
| P1-4 | Tests integración flujo completo | UI → DB → collector → buffer → UI con coverage REAL | ≥50 tests integración; ≥80% coverage por módulo | tester (MYK-171 handoff ready) |

---

## P2 — Post-MVP (Planear después)

| ID | Título |
|----|--------|
| P2-1 | Auto-discovery LAN (UDP broadcast) |
| P2-2 | Dashboard con gráficas (Chart.js) |
| P2-3 | Reportes por rango de fechas |
| P2-4 | Multi-device hardening (concurrencia, retry, backoff) |
| P2-5 | Docker image ARM64 + x86_64 |
| P2-6 | docker-compose single-command deploy |

---

## Hallazgos Críticos de MYK-163 (Auditables en 78d1bfe)

1. **Collector NUNCA corre en prod**: Dockerfile CMD = solo gunicorn → FIX: supervisord dual en branch fix/p0-1-supervisord-clean
2. **Devices desintegrados**: WebGUI guarda en SQLite, collector lee collector.yaml read-only → FIX: P0-2 (c16714f cache 60s TTL)
3. **Cero vista asistencia**: 0 rutas/templates para attendance_buffer → FIX: P0-3 (MYK-166 DONE locally)
4. **Export CSV: CERO código** → FIX: P0-4
5. **Auto-discovery: CERO código** → P2-1
6. **"239 tests, 86.84% coverage" FALSO**: Master tiene 16 tests; CI jobs no corren por ruff → FIX: P0-5 DONE + P1-4
7. **BACKLOG.md y SPRINT-1.md NUNCA existieron en git** → ESTE ARCHIVO + SPRINT-2.md
8. **"supervisord manages both" FALSO**: Dockerfile no usa supervisord → FIX: P0-1 branch
9. **Password reset sin SMTP ni flujo verificado** → P1-3 (board decision pending)

---

## Definition of Done (Endurecida — Aplica YA)

Cada disposition a `done` REQUIERE evidencia reproducible:
1. **Commit SHA** con el cambio
2. **Output real** de tests/CI en el PR
3. **Verificación contra deploy**: http://10.0.0.16:8081 o https://zk-receiver.tail5276ec.ts.net

Reportes con métricas inventadas o archivos inexistentes = fallo de proceso + revocación del done. El board AUDITARÁ cada claim.