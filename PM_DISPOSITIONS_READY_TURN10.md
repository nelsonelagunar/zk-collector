# PM Dispositions Ready — 2026-10-15 Turn 10

**Agent**: coffee (PM)
**Platform Blocker**: MYK-188 (36th+ failure) — ALL board writes blocked

---

## Board Actions Queued for Batch Sync (When Platform Recovers)

### 1. MYK-165 Disposition (P0-2: Collector reads WebGUI DB)
- **Status**: Code complete (commit c16714f on fix/p0-1-supervisord-clean)
- **Action**: Board operator disposition to done
- **Evidence**: Device DB cache 60s TTL implemented, migration one-shot in docker-entrypoint.sh

### 2. MYK-166 Disposition (P0-3: Attendance page)
- **Status**: Code complete on feature branch
- **Action**: Board operator disposition to done
- **Evidence**: Template + routes + API all implemented, unit tests PASS

### 3. MYK-168 Disposition (P1-3: Password reset board decision)
- **Status**: Missing blocker — needs board operator
- **Action**: Board operator to set blocker (MYK-184 + board decision)

### 4. MYK-185 Disposition (Standup cleanup)
- **Status**: Missing blocker — needs board operator
- **Action**: Board operator to set blocker

### 5. Handoff: MYK-166 → frontend-dev
- **Status**: Ready — blocked on MYK-181 merge + deploy
- **Artifact**: `HANDOFF_MYK166_TO_FRONTEND_DEV.md` in repo
- **Criteria**: Deploy verify attendance page on LXC 108

### 6. Handoff: MYK-171 → tester
- **Status**: Ready — blocked on MYK-181 merge
- **Artifact**: `HANDOFF_MYK171_TO_TESTER.md` in repo
- **Criteria**: ≥50 integration tests, ≥80% coverage per module, P0 chain unblocked

### 7. Board Decision: MYK-183/194 (SMTP Password Reset)
- **Status**: Interaction card ready
- **Artifact**: `INTERACTION_MYK183_SMTP_DECISION.md` in repo
- **Options**:
  - A: SMTP Real (human provides Infisical auth, devops creates 6 secrets, deploy, E2E test)
  - B: Remove from MVP (delete /forgot-password, /reset-password routes, templates, SMTP config)

---

## Sync Order When Platform Fix Verified

1. **Checkout** each issue + post disposition comments
2. **Post handoffs** as comments on parent issues
3. **Post board decision interaction** on MYK-183
4. **Create PR #22** from `fix/p0-1-supervisord-clean` → `master` (or confirm human created it)
5. **Wake agents** with handoffs

---

## Evidence Files in Repo

- `PM_STANDUP_2026-10-15_TURN10.md`
- `UNBLOCK_WATCHDOG_2026-10-15_TURN10.md`
- `LOCAL_VALIDATION_SUMMARY_RUN_FINAL_TURN10.md`
- `PM_DISPOSITIONS_READY_TURN10.md` (this file)
- `PLATFORM_BUG_CONFIRMED_2026-10-15_TURN10.md`
- `HANDOFF_MYK166_TO_FRONTEND_DEV.md`
- `HANDOFF_MYK171_TO_TESTER.md`
- `INTERACTION_MYK183_SMTP_DECISION.md`
- `SPRINT-2.md`
- `BACKLOG.md`

---

**Protocol**: Stop retrying board writes after 2 consecutive failures (36th+ failure documented). All dispositions locally documented and queued.
