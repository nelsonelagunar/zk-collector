# PM Dispositions Ready for Batch Sync — Current Turn (Run 20)

## Board Actions Queued (8)

### 1. MYK-201 Status Update (P0-2 Unblock)
**Status**: MYK-181 is now `done` on board, so P0-2 collector reads WebGUI DB is unblocked
**Action**: PATCH status to `done` when platform recovers
**Criteria**: MYK-181 merged → MYK-164 done → MYK-201 unblocked

### 2. MYK-165 Disposition (P0-2 Device Truth)
**Status**: Code complete (commit c16714f), blocked on MYK-181 merge (now done)
**Action**: Post disposition comment when platform recovers
**Criteria**: MYK-181 merged → unblock MYK-165 → reviewer assignment

### 3. MYK-166 Disposition (P0-3 Attendance Page)
**Status**: Feature branch `feature/p0-3-attendance-page` ready (commit 1918624), blocked on MYK-181 deploy
**Action**: Post disposition comment when platform recovers
**Criteria**: MYK-181 merged → deploy verify → handoff to frontend-dev

### 4. MYK-168 Disposition (P1-1 User Mapping)
**Status**: DONE locally, handoff to frontend-dev complete
**Action**: Post disposition comment when platform recovers
**Criteria**: Code review approved + frontend-dev handoff acknowledged

### 5. MYK-185 Disposition (Daily Standup)
**Status**: in_progress, blocked on platform
**Action**: Post disposition comment when platform recovers
**Criteria**: Platform fix verified → close daily standup issue

### 6. MYK-166 → frontend-dev Handoff
**Status**: Ready, blocked on MYK-181 merge (now done)
**Action**: Create handoff comment/issue when platform recovers
**Target**: frontend-dev agent (d9be0232-0306-4b59-9323-747997bad616)
**Criteria**: Attendance page feature branch ready for integration

### 7. MYK-171 → tester Handoff
**Status**: Ready, blocked on MYK-181 merge (now done)
**Action**: Create handoff comment/issue when platform recovers
**Target**: tester agent
**Criteria**: Integration test fixtures complete (≥50 tests, ≥80% coverage)

### 8. MYK-183/194 SMTP Decision Interaction
**Status**: Board decision pending (Option A vs B)
**Action**: Create `ask_user_questions` interaction when platform recovers
**Options**:
- A: Real SMTP via Infisical (requires MYK-184 complete)
- B: Remove from MVP (commit 3b70125 already removed SMTP wiring)

---

## Batch Sync Protocol

When platform fix verified (checkout + comment success):
1. Execute all 8 actions in sequence
2. Verify each write succeeds before next
3. Update local tracking to reflect board state
4. Close turn with board confirmation

---

## Evidence Files

All dispositions documented in:
- `PM_FINAL_2026-10-15_TURN20.md`
- `PM_STANDUP_2026-10-15_CURRENT.md`
- `UNBLOCK_WATCHDOG_2026-10-15_CURRENT.md`
- `LOCAL_VALIDATION_SUMMARY_RUN_CURRENT.md`
- `PLATFORM_VERIFICATION_2026-10-15_CURRENT.md`
- `HANDOFF_MYK166_TO_FRONTEND_DEV.md`
- `HANDOFF_MYK171_TO_TESTER.md`
- `INTERACTION_MYK183_SMTP_DECISION.md`
