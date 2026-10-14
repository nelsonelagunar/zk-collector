# SPRINT-2.md — ZK-Collector Sprint 2

**Sprint Goal**: Arrancar el collector en producción + una fuente de verdad de devices + página de asistencia visible + CI verde
**Fechas**: 2026-10-13 → 2026-10-17 (semana)
**Branch base**: `fix/p0-1-supervisord-clean` (78d1bfe) — validado localmente 134/135 tests, ruff CLEAN

---

## Sprint Backlog (6 items P0)

| # | Issue ID | Título | Asignado | Estado | Criterio de Salida |
|---|----------|--------|----------|--------|-------------------|
| 1 | MYK-177 | [P0-0] Emulador ZKTeco TCP :4370 | tester | **DONE** ✅ | `pytest tests/integration/test_emulator_integration.py -k "not full_cycle"` PASS |
| 2 | MYK-181 | [P0-1] DevOps: fix/p0-1-supervisord PR + merge | devops | **BLOCKED** | PR #22 created & merged; docker logs muestra polling activo |
| 3 | MYK-164 | [P0-1] Collector arranca (supervisord dual) | devops+backend-dev | **IN_REVIEW** | Reviewer approval on PR #22; docker logs polling activo |
| 4 | MYK-165 | [P0-2] Una fuente verdad devices (WebGUI DB) | backend-dev | **BLOCKED** | Device agregado por UI → polleado en siguiente ciclo (300s) |
| 5 | MYK-166 | [P0-3] Página asistencia (tabla + filtros + pag) | frontend-dev | **DONE** local | Registros attendance_buffer visibles en :8081 |
| 6 | MYK-167 | [P0-4] Export CSV real | backend-dev | **BLOCKED** | CSV descargado con registros filtrados |
| 7 | MYK-162 | [P0-5] CI verde ruff=0 | devops | **DONE** ✅ | `ruff check src/ tests/` = 0; CI verde |

---

## Critical Path (Single Bottleneck)

```
MYK-181 (devops PR merge) ──unblocks──► MYK-164 ──unblocks──► MYK-165 ──unblocks──► MYK-167
         │                                    │
         └────────────────────────────────────┴───────────── unblocks MYK-166 (local DONE)
```

**MYK-181 es el ÚNICO bottleneck**: branch `fix/p0-1-supervisord-clean` listo en origin con commit `78d1bfe` (134/135 tests PASS, ruff CLEAN). Bloqueado en GitHub API auth (platform issue MYK-188).

---

## Dependencies & Blockers

| Issue | Bloqueado por | Acción para desbloquear |
|-------|---------------|-------------------------|
| MYK-181 | GitHub API auth (MYK-188) | Platform fix OR manual PR creation by human |
| MYK-164 | MYK-181 merge | Reviewer approve PR #22 once merged |
| MYK-165 | MYK-164 + board disposition | Board operator: resolve `missing_disposition` recovery |
| MYK-166 | MYK-181 merge | Deploy P0-1 branch to verify |
| MYK-167 | MYK-164 + MYK-165 | Implement after P0-2 merged |

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

## Evidence (Local Validation - 2026-10-14)

**Branch**: `fix/p0-1-supervisord-clean` (commit `78d1bfe`)
**Lint**: `ruff check src/ tests/` → CLEAN ✅

**Test Suite Results**:
```
Unit Tests:                    105/105 PASS ✅
Integration (webgui):          10/10 PASS ✅
Integration (config):          11/11 PASS ✅
Integration (collector):        5/5 PASS ✅
Integration (emulator):         3/4 PASS ✅ (1 hangs - pre-existing)
Total Validated:              134/135 PASS (1 pre-existing hang)
```

**Coverage** (excl. webgui auth/routes - no tests yet): 70% overall, core modules >85%

---

**Platform Blocker**: MYK-188 (escalation:platform) — Gateway bearer token denied for ALL board writes (21st+ consecutive failure). All PM coordination documented locally. Next wakeup: verify platform fix before attempting board writes.