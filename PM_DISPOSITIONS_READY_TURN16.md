# PM Dispositions Ready 2026-10-15 Turn 16 — Sprint 2 Day 7 Continued

**Platform**: Still blocked (42nd+ failure) — dispositions documented locally for batch sync when platform recovers.

---

## Recovery Actions Needing Board Disposition (5)

| Issue | Title | Disposition Type | Evidence (Local) | Next Step |
|-------|-------|------------------|------------------|-----------|
| MYK-165 | P0-2 Device truth (WebGUI DB) | missing_disposition | Code complete c16714f (60s TTL cache reading webgui/database.py); local tests 139/140 PASS | Board operator: resolve timeout recovery |
| MYK-166 | P0-3 Attendance page | missing_disposition | Feature branch 1918624: `/attendance` route with table, filters (fecha/user/device), pagination 25/page, CSV export | Board operator: resolve platform-write-failed recovery |
| MYK-168 | P1-1 User mapping | missing_disposition | Already done externally (tester 4d8ee803 completed); needs board close | Board operator: close |
| MYK-185 | SCRUM Daily Standup | missing_disposition | PM coordination complete; platform blocked write | Board operator: resolve platform-blocked recovery |
| MYK-188 | Platform escalation | missing_disposition | Root cause confirmed (gateway run context not propagated); 42+ failures | Board operator: close escalation |

---

## Decision Interaction Ready to Post

| Issue | Title | Interaction File | Options |
|-------|-------|------------------|---------|
| MYK-183/194 | Password reset: SMTP real or remove | `INTERACTION_MYK183_SMTP_DECISION.md` | A: SMTP real via Infisical (requires MYK-184) / B: Remove /forgot-password from MVP |

---

## Handoffs Ready to Create

| From | To | Issue | Handoff File | Status |
|------|-----|-------|--------------|--------|
| coffee | frontend-dev (d9be0232) | MYK-166 | `HANDOFF_MYK166_TO_FRONTEND_DEV.md` | Ready |
| coffee | tester (4d8ee803) | MYK-171 | `HANDOFF_MYK171_TO_TESTER.md` | Ready |

---

## Blocker Declarations Needed (5 in_progress issues)

| Issue | Title | Assignee | Declare Blocker |
|-------|-------|----------|-----------------|
| MYK-163 | P0-Board Mandate | coffee | MYK-188 (platform) |
| MYK-165 | P0-2 Device truth | coffee | MYK-188 (platform) |
| MYK-166 | P0-3 Attendance page | coffee | MYK-188 (platform) |
| MYK-166-front | P0-3 Attendance (front) | frontend-dev | MYK-188 (platform) |
| MYK-185 | Daily Standup | coffee | MYK-188 (platform) |

---

## Batch Sync Sequence (When Platform Recovers)

1. **Declare blockers** on 5 issues (all → MYK-188)
2. **Post interaction** MYK-183/194 (SMTP A vs B decision)
3. **Disposition** MYK-165, MYK-166, MYK-168, MYK-185, MYK-188
4. **Create handoff issues** MYK-166→frontend-dev, MYK-171→tester
5. **Close platform escalation** MYK-188

Total: 8 atomic board operations

---

## Evidence Files (All in workspace)

- `PM_STANDUP_2026-10-15_TURN16.md` — daily standup
- `UNBLOCK_WATCHDOG_2026-10-15_TURN16.md` — watchdog pass
- `PM_HEARTBEAT_2026-10-15_TURN16.md` — this heartbeat
- `INTERACTION_MYK183_SMTP_DECISION.md` — request_confirmation payload
- `HANDOFF_MYK166_TO_FRONTEND_DEV.md` — handoff spec
- `HANDOFF_MYK171_TO_TESTER.md` — handoff spec
- `LOCAL_VALIDATION_SUMMARY_RUN_CURRENT.md` — 139/140 tests, ruff CLEAN
- `SPRINT-2.md` — updated with current board state
- `BACKLOG.md` — source of truth

---

**Protocol**: All dispositions documented locally. Next turn verifies platform fix before ANY board operations.