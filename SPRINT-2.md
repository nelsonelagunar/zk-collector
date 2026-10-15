# SPRINT-2.md — ZK-Collector Sprint 2

**Sprint Goal**: Arrancar el collector en producción + una fuente de verdad de devices + página de asistencia visible + CI verde
**Fechas**: 2026-10-13 → 2026-10-17 (semana)
**Branch base**: `fix/p0-1-supervisord-clean` (78d1bfe) — validado localmente 134/135 tests, ruff CLEAN

---

## Sprint Backlog (6 items P0) — Estado actualizado 2026-10-15 (board read)

| # | Issue ID | Título | Asignado | Estado | Criterio de Salida |
|---|----------|--------|----------|--------|-------------------|
| 1 | MYK-177 | [P0-0] Emulador ZKTeco TCP :4370 | tester | **DONE** ✅ | `pytest tests/integration/test_emulator_integration.py -k "not full_cycle"` PASS |
| 2 | MYK-181 | [P0-1] DevOps: fix/p0-1-supervisord PR + merge | devops | **DONE** ✅ (merged en prod) | PR #22 created & merged; docker logs muestra polling activo |
| 3 | MYK-164 | [P0-1] Collector arranca (supervisord dual) | devops+backend-dev | **DONE** ✅ (prod) | Reviewer approval on PR #22; docker logs polling activo |
| 4 | MYK-165 | [P0-2] Una fuente verdad devices (WebGUI DB) | backend-dev | **DONE board** ✅ — deploy verify pendiente (platform blocked) | Device agregado por UI → polleado en siguiente ciclo (300s) |
| 5 | MYK-166 | [P0-3] Página asistencia (tabla + filtros + pag) | frontend-dev | **DONE local** (1918624) — pendiente deploy verify en :8081 (platform blocked) | Registros attendance_buffer visibles en :8081 |
| 6 | MYK-167 | [P0-4] Export CSV real | backend-dev | **DONE** ✅ (prod) | CSV descargado con registros filtrados |
| 7 | MYK-162 | [P0-5] CI verde ruff=0 | devops | **DONE** ✅ | `ruff check src/ tests/` = 0; CI verde |

---

## Critical Path (Single Bottleneck) — **RESUELTO EXTERNAMENTE**

```
MYK-181 (devops PR merge) ──✅ UNBLOCKED──► MYK-164 ✅ DONE ──unblocks──► MYK-165 (code complete) ──unblocks──► MYK-167 ✅ DONE
         │                                    │
         └────────────────────────────────────┴───────────── unblocks MYK-166 ✅ DONE local
```

**MYK-181 bottleneck RESUELTO**: PR #22 merged en producción. Collector polling activo en logs. MYK-164 y MYK-167 también DONE externamente.
**Bottleneck actual**: Solo platform gateway (MYK-188) impide board dispositions + deploy verification.

---

## Dependencies & Blockers

| Issue | Bloqueado por | Acción para desbloquear |
|-------|---------------|-------------------------|
| MYK-165 | Platform (MYK-188) + deploy verify | Platform fix OR manual disposition by board operator |
| MYK-166 | Platform (MYK-188) + deploy verify | Deploy feature branch + verify /attendance en :8081 |
| MYK-183/194 | Board decision (A vs B) | Board: decidir SMTP real o remover del MVP |
| MYK-184 | MYK-183 decision + Infisical auth | Board decision + Infisical universal auth |

---

## Decisions Required from Board (This Sprint)

1. **MYK-183 / MYK-194**: Password reset — `DECISIÓN: A|B` + `JUSTIFICACIÓN`
   - Opción A: SMTP real via Infisical (requiere credenciales MYK-184)
   - Opción B: Remover /forgot-password del MVP
   - Interaction card prepared: `INTERACTION_MYK183_SMTP_DECISION.md`

2. **MYK-184**: Infisical universal auth credentials OR manual creation of 6 SMTP secrets
   - Required if board chooses Option A above

---

## Recovery Actions (Board Operator Required)

| Issue | Recovery Type | Status |
|-------|---------------|--------|
| MYK-165 | missing_disposition (timeout) | Active |
| MYK-166 | missing_disposition (platform write failed) | Active |
| MYK-168 | missing_disposition | Active |
| MYK-185 (Daily Standup) | missing_disposition | Active |

---

## Definition of Done (Sprint 2)

Cada item `done` SOLO cuando:
- [ ] Código mergeado a master
- [ ] Tests pasando (CI verde)
- [ ] Code review de reviewer (PR aprobado)
- [ ] QA de tester (verificación en deploy)
- [ ] Verificación contra https://zk-receiver.tail5276ec.ts.net

---

## Daily Standup Ritual (10:00 lun-vie)

| Día | Foco |
|-----|------|
| Lun | Sprint Planning (este doc) + kickoff |
| Mar | MYK-181 unblock + MYK-164 review |
| Mié | MYK-165 implementation + MYK-166 deploy verify |
| Jue | MYK-167 implementation + MYK-171 test kickoff |
| Vie | Sprint Review + Retro → SPRINT-3 planning |

---

## Sprint Review + Retro (Viernes 16:00)

**Review**: Verificar done REAL contra DoD arriba. Solicitar dispositions al board para items completados. Actualizar este doc con evidencia de cierre.

**Retro**: 3 cosas que funcionaron / 3 que fallaron / 3 acciones concretas → documentar en `RETRO-2.md` + 1 línea por aprendizaje al SHARED MEMORY.

**Cierre**: Lo no-terminado vuelve al backlog SIN asignar — nunca hereda asignación al sprint siguiente sin pasar por planning.

---

## Handoffs Prepared (Local Files)

1. `HANDOFF_MYK166_TO_FRONTEND_DEV.md` — Attendance page UI, blocked on P0 merge
2. `HANDOFF_MYK171_TO_TESTER.md` — Integration tests (≥50, ≥80% coverage), blocked on P0 merge
3. `INTERACTION_MYK183_SMTP_DECISION.md` — request_confirmation ready for board

---

## Evidence (Local Validation - 2026-10-15 Final)

**Branch**: `fix/p0-1-supervisord-clean` (commit `1918624` — feat P0-3 attendance page)
**Lint**: `ruff check src/ tests/` → CLEAN ✅

**Test Suite Results (20th Consecutive Pass)**:
```
Unit Tests:                    113/113 PASS ✅
Integration (webgui):          10/10 PASS ✅
Integration (config):          11/11 PASS ✅
Integration (collector):        5/5 PASS ✅
Integration (emulator):         3/4 PASS ✅ (1 hangs - pre-existing)
Attendance unit tests:          8/8 PASS ✅
Total Validated:              139/140 PASS (1 pre-existing hang)
```

**Coverage** (excl. webgui auth/routes - no tests yet): 70% overall, core modules >85%

---

**Platform Blocker**: MYK-188 (escalation:platform) — Gateway run context not propagated (41st+ consecutive failure, since 2026-10-11). All PM coordination documented locally. Checkout binds but all write operations rejected (`gateway_token_action_denied` / `cross_issue_influence_run_context_required`). Next wakeup: verify platform fix before attempting board writes.

**Turn 13 Update (2026-10-15)**: Sprint 2 critical path externally resolved — 5/7 P0 items DONE in production (MYK-177, 181, 164, 167, 162). MYK-165 DONE on board (deploy verify pending). MYK-166 code complete locally (deploy verify pending). UNBLOCK WATCHDOG: all 7 blocked issues have declared blockers; SMTP decision chain (MYK-170/174→184) awaits human board decision. 5 recovery actions queued in PM_DISPOSITIONS_READY_TURN13.md.