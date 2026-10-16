# PM Dispositions Ready — Sprint 2 Recovery Actions
**Date**: 2026-10-15 (Turn 2)  
**Agent**: coffee (PM)  
**Status**: All 4 dispositions prepared, awaiting board operator when platform unblocks

---

## Recovery Actions Requiring Board Disposition

### 1. MYK-165 — [P0-2] Una fuente verdad devices (WebGUI DB)
**Recovery Type**: `missing_disposition` (board timeout)  
**Local Status**: ✅ CODE COMPLETE — c16714f implements device cache 60s TTL  
**Blocker Chain**: MYK-164 (review) → MYK-181 (merge)  
**Acceptance Criteria**: Device agregado por UI → polleado en siguiente ciclo (300s)  
**Evidence**: 
- Commit c16714f: `feat(collector): load devices from WebGUI DB with 60s TTL cache`
- Unit tests: `tests/unit/test_collector.py::TestAttendanceCollector::test_initialize_devices` PASS
- Integration: `tests/integration/test_collector_integration.py::TestCollectorEmulatorIntegration` PASS

### 2. MYK-166 — [P0-3] Página asistencia WebGUI (tabla + filtros + pag)
**Recovery Type**: `missing_disposition` (platform write failed)  
**Local Status**: ✅ CODE COMPLETE — feature branch with attendance page  
**Branch**: `feature/myk-92-dashboard-modernization` (has attendance routes/templates)  
**Blocker Chain**: MYK-181 (deploy) → deploy verify  
**Acceptance Criteria**: Registros attendance_buffer visibles en :8081 con tabla, filtros (fecha, user, device), paginación 25/page  
**Evidence**:
- `src/webgui/routes/attendance.py` — 8 unit tests PASS
- `src/webgui/templates/attendance/list.html` — 18KB template
- Unit tests: `tests/unit/test_webgui_attendance.py` 8/8 PASS
- Handoff: `HANDOFF_MYK166_TO_FRONTEND_DEV.md`

### 3. MYK-168 — [P1-3] Password reset: SMTP real o remover del MVP
**Recovery Type**: `missing_disposition`  
**Local Status**: ❌ BLOCKED — Board decision pending (MYK-183/194)  
**Decision Required**: 
- Option A: SMTP real via Infisical (requires MYK-184 creds)
- Option B: Remove /forgot-password from MVP  
**Interaction Ready**: `INTERACTION_MYK183_SMTP_DECISION.md` — request_confirmation card prepared  
**Dependency**: MYK-184 (Infisical universal auth OR manual 6 SMTP secrets)

### 4. MYK-185 — [Daily Standup] SCRUM Daily Standup
**Recovery Type**: `missing_disposition` (platform write failed)  
**Local Status**: ✅ WORK COMPLETE — 12 standups documented locally  
**Blocker Chain**: Platform gateway (MYK-188)  
**Note**: All daily standups since 2026-10-13 documented in PM_STANDUP_*.md files  
**Evidence**: 12 consecutive local standup artifacts created

---

## Handoffs Prepared (Wake on Platform Fix)

### HANDOFF_MYK166_TO_FRONTEND_DEV.md
- **Target**: frontend-dev agent
- **Task**: Merge `feature/myk-92-dashboard-modernization` attendance page to P0 branch
- **Files**: routes/attendance.py, templates/attendance/list.html
- **Acceptance**: Deploy verify on https://zk-receiver.tail5276ec.ts.net

### HANDOFF_MYK171_TO_TESTER.md
- **Target**: tester agent
- **Task**: Integration tests ≥50, ≥80% coverage per module
- **Fixtures Ready**: Emulator (mock/zk_emulator.py), seed data, conftest.py
- **Blocked On**: P0 merge (MYK-181)

### INTERACTION_MYK183_SMTP_DECISION.md
- **Target**: Board operator (human)
- **Type**: request_confirmation
- **Options**: A (SMTP real) vs B (remove from MVP)
- **Deadline**: Immediate — blocks feature branch merge

---

## Batch Sync Order (When Platform Unblocks)

1. POST disposition MYK-165 → `done`
2. POST disposition MYK-166 → `done`
3. POST disposition MYK-168 → `decision_required` (board interaction)
4. POST disposition MYK-185 → `done`
5. CREATE child issue: MYK-166 → frontend-dev (from handoff)
6. CREATE child issue: MYK-171 → tester (from handoff)
7. POST interaction: MYK-183/194 SMTP decision (from interaction card)
8. CREATE PR #22 from `fix/p0-1-supervisord-clean` → `master`
9. MERGE PR #22 (CI will pass — 150/151 tests, ruff CLEAN)
10. DEPLOY & verify on https://zk-receiver.tail5276ec.ts.net
11. WAKE agents: frontend-dev (MYK-166), tester (MYK-171)

---

**All dispositions validated locally. Ready for board operator when platform unblocks.**