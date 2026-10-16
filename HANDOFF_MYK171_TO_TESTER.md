# HANDOFF: MYK-171 → TESTER — Integration Tests (P1-4)

## Status: PREPARADO — BLOQUEADO EN P0-1 MERGE

**Target**: ≥50 integration tests, ≥80% coverage per module
**Depends on**: MYK-166 (attendance page) + MYK-165 (device truth) + MYK-181 (supervisord merge)

---

## Current Test State (Local)

| Suite | Tests | Status |
|-------|-------|--------|
| Unit | 105 | ✅ PASS |
| Integration (emulator) | 3/4 | ✅ PASS (1 pre-existing hang) |
| Integration (webgui) | 10 | ✅ PASS |
| Integration (config) | 11 | ✅ PASS |
| Integration (collector) | 5 | ✅ PASS |
| **Total validated** | **134/135** | ✅ |

---

## Coverage Gap Analysis

| Module | Current Coverage | Target | Gap |
|--------|------------------|--------|-----|
| `src/buffer/` | >85% | ≥80% | ✅ |
| `src/core/` | >85% | ≥80% | ✅ |
| `src/zk/` | >85% | ≥80% | ✅ |
| `src/sync/` | 90% | ≥80% | ✅ |
| `src/webgui/auth.py` | 0% | ≥80% | ❌ |
| `src/webgui/routes/auth.py` | 0% | ≥80% | ❌ |
| `src/webgui/routes/devices.py` | 32% | ≥80% | ❌ |
| `src/webgui/routes/attendance.py` | N/A (not on current branch) | ≥80% | ❌ |
| `src/webgui/server.py` | 0% | ≥80% | ❌ |

---

## What Needs Testing (After P0 Merge)

### 1. Attendance Page E2E (Priority: CRITICAL)
- `/attendance` page loads with auth
- Filters: date range, user_id, device dropdown
- Pagination: 25/page, next/prev, page numbers
- CSV export downloads correct data
- Excel export downloads correct data
- Empty state handling
- Dark mode toggle

### 2. Device → Collector → WebGUI Flow (Priority: CRITICAL)
- Add device via WebGUI → appears in `/api/devices`
- Collector polls device (emulator) → records in buffer
- Records appear in `/api/attendance` with correct user_name lookup
- Records appear in `/attendance` page table
- Export includes filtered data

### 3. WebGUI Auth Routes (Priority: HIGH)
- Login/logout flow
- Password reset (if Option A chosen)
- Session persistence

### 4. Device CRUD + Poll Integration (Priority: HIGH)
- Create device → test connection → poll succeeds
- Toggle enabled → collector skips disabled
- Delete device → removed from poll cycle

---

## Test Fixtures Ready

| Fixture | Location | Description |
|---------|----------|-------------|
| `mock/attendance_seed.json` | `origin/feature/myk-92-dashboard-modernization` | Seed data for emulator |
| `mock/zk_emulator.py` | Current branch + feature | Async ZKTeco emulator |
| `tests/conftest.py` | Current branch | `populated_repo`, `emulator_server` fixtures |

---

## Suggested Test Structure

```
tests/integration/
├── test_attendance_page.py       # NEW — Alpine.js page + API
├── test_e2e_flow.py              # NEW — device→collector→webgui→export
├── test_webgui_auth.py           # NEW — login, reset, session
├── test_device_poll_flow.py      # EXTEND — add poll verification
└── test_export_streaming.py      # NEW — CSV/XLSX streaming
```

---

## Acceptance Criteria (from SPRINT-2.md + BACKLOG.md)
```
P1-4: Tests integración flujo completo
- UI → DB → collector → buffer → UI con coverage REAL
- ≥50 tests integración; ≥80% coverage por módulo
```

---

## Next Steps (When Platform Unblocks)
1. Merge `origin/feature/myk-92-dashboard-modernization` → `fix/p0-1-supervisord-clean`
2. Deploy to staging
3. Write integration tests against staging (real URLs, real DB)
4. Run full suite → verify ≥50 integration tests, ≥80% coverage
5. Submit PR with test evidence

---

## Related
- `HANDOFF_MYK166_TO_FRONTEND_DEV.md` — Attendance page implementation
- `SPRINT-2.md` — Sprint backlog with P1-4 criteria
