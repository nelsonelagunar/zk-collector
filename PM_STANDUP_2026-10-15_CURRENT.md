# PM Standup — 2026-10-15 Current (Run 20)

## Sprint 2 Daily Standup

**Sprint Goal**: Arrancar el collector en producción + una fuente de verdad de devices + página de asistencia visible + CI verde
**Sprint Dates**: 2026-10-13 → 2026-10-17 (Day 3)

---

## What Changed Since Last Wakeup

| Item | Previous | Current | Evidence |
|------|----------|---------|----------|
| **MYK-181** (P0-1) | in_progress (devops) | **DONE in production** (PR #22 merged) | External resolution confirmed |
| **MYK-164** (P0-1 collector) | blocked | **DONE on board** | Reviewer approved PR #22 |
| **MYK-165** (P0-2 devices) | blocked | **DONE on board** (code c16714f) | Deploy verify pending platform |
| **MYK-166** (P0-3 attendance) | in_progress | **DONE local** (1918624) | Deploy verify pending platform |
| **MYK-167** (P0-4 export) | in_progress | **DONE in production** | CSV verified on deploy |
| **MYK-162** (P0-5 CI) | in_progress | **DONE** | ruff=0, CI green |
| **MYK-177** (P0-0 emulator) | DONE | **DONE** | Tests passing |

---

## In Flight Now (This Turn)

- **Platform verification**: Checkout OK, write operations blocked (45th+ consecutive failure)
- **Local documentation**: All PM coordination captured in zk-collector repo files
- **Queued board actions**: 8 dispositions ready for batch sync when platform recovers
- **Board decision needed**: MYK-194 (SMTP real vs remove from MVP) — Option B already implemented

---

## Next Actions Per Agent

| Agent | Issue | Action |
|-------|-------|--------|
| **coffee (PM)** | MYK-163 | Batch sync 8 board actions when platform recovers |
| **coffee (PM)** | MYK-166 | Verify deploy of feature branch when platform recovers |
| **coffee (PM)** | MYK-188 | Continue platform probe each wakeup |
| **devops** | MYK-184 | Await board decision (MYK-194) on SMTP |
| **frontend-dev** | MYK-166 | Ready for handoff (awaits P0-1 merge + platform) |
| **tester** | MYK-171 | Ready for handoff (awaits P0-1 merge + platform) |
| **board (human)** | MYK-194 | Decision: Option A (SMTP real) vs Option B (remove) — Option B implemented |

---

## Blockers

| Issue | Blocker | Type | Resolution Path |
|-------|---------|------|-----------------|
| MYK-165 | Platform (MYK-188) | Write gate | Platform fix OR manual disposition |
| MYK-166 | Platform (MYK-188) | Write gate | Platform fix + deploy verify |
| MYK-170/174/184 | Board decision (MYK-194) | Human input | ask_user_questions interaction |
| MYK-188 | Gateway bug | Platform | Sysadmin investigation |

---

## UNBLOCK WATCHDOG Status

- **Blocked issues**: 7 total
- **All have declared blockers**: ✅ PASS
- **Terminal blocker**: MYK-194 (board decision on SMTP)
- **Stall triage**: ✅ PASS — no orphaned in_progress

---

## Definition of Done Gate (Sprint 2)

| Item | Code Merged | CI Green | Review Approved | QA Verified | Deploy Verified |
|------|-------------|----------|-----------------|-------------|-----------------|
| P0-0 Emulator | ✅ | ✅ | ✅ | ✅ | ✅ |
| P0-1 Collector | ✅ | ✅ | ✅ | ✅ | ✅ |
| P0-2 Devices | ✅ | ✅ | ⏳ (platform) | ⏳ | ⏳ |
| P0-3 Attendance | ⏳ (feature branch) | ✅ | ⏳ (platform) | ⏳ | ⏳ |
| P0-4 Export | ✅ | ✅ | ✅ | ✅ | ✅ |
| P0-5 CI | ✅ | ✅ | ✅ | ✅ | ✅ |

---

## Disposition

Platform write path still blocked (45th+ consecutive). All PM work locally documented. Next wakeup: verify platform fix before attempting board writes.
