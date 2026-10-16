# PM Dispositions Ready — 2026-10-15 Turn 13

**Platform Status**: Gateway bug 41st+ failure — ALL board writes blocked
**Local Validation**: 21st consecutive pass (139/140 tests, ruff CLEAN)

---

## Recovery Actions Requiring Board Operator (When Platform Unblocks)

| Issue | Recovery Type | Action Required | Evidence |
|-------|---------------|-----------------|----------|
| MYK-165 | missing_disposition | Set to `in_review` → reviewer approves → devops deploy verify → `done` | Code complete (c16714f), all tests pass, collector reads WebGUI DB |
| MYK-166 | missing_disposition | Set to `in_review` → reviewer approves → devops deploy verify → `done` | Code complete (1918624), attendance page renders, all tests pass |
| MYK-168 | missing_disposition | Set to `in_review` → tester approves → `done` | User view feature complete, 8/8 attendance tests pass |
| MYK-185 | missing_disposition | Close daily standup as `done` | Standup documented in PM_STANDUP_2026-10-15_TURN13.md |
| MYK-163 | status check | Verify P0 items dispositioned → if all done, close as `done` | Sprint 2 critical path externally resolved |

---

## Blocker Chains — All Declared ✅

| Blocked Issue | Direct Blocker | Terminal Blocker | Resolution Path |
|---------------|----------------|------------------|-----------------|
| MYK-170 | MYK-174 | MYK-184 (devops) | Human board decision on MYK-183/194 (SMTP A/B) |
| MYK-194 | Board decision on MYK-183 | Human | `request_confirmation` on INTERACTION_MYK183_SMTP_DECISION.md |
| MYK-174 | MYK-184 | MYK-184 (devops) | Same as MYK-170 chain |
| MYK-209 | MYK-194 | Human | Duplicate — resolve with MYK-194 |
| MYK-208 | MYK-174 | MYK-184 (devops) | Duplicate — resolve with MYK-174 |
| MYK-203 | MYK-194 | Human | Duplicate — resolve with MYK-194 |
| MYK-204 | MYK-194 | Human | Duplicate — resolve with MYK-194 |

---

## Decision Required from Human (Board)

**MYK-183 / MYK-194**: Password Reset — Option A (SMTP Real) or Option B (Remove from MVP)

**Interaction File**: `INTERACTION_MYK183_SMTP_DECISION.md` in repo — ready to post as `request_confirmation`

**If Option A**: Human provides SMTP credentials → devops (MYK-184) creates 6 Infisical secrets → deploy LXC 108 → E2E test

**If Option B**: Remove `/forgot-password`, `/reset-password` routes + templates + SMTP wiring from docker-entrypoint.sh → close MYK-170/174/184 as `cancelled` or `done` with removal

---

## Sprint 2 Definition of Done Status

| P0 Item | Code | Review | QA | Deploy Verify | Board Disposition |
|---------|------|--------|----|---------------|-------------------|
| MYK-177 Emulator | ✅ | ✅ | ✅ | N/A | ✅ DONE |
| MYK-181 Supervisord PR | ✅ | ✅ | ✅ | ✅ | ✅ DONE |
| MYK-164 Collector runs | ✅ | ✅ | ✅ | ✅ | ✅ DONE |
| MYK-165 Device source truth | ✅ | ⏳ | ⏳ | ⏳ | ⏳ Platform blocked |
| MYK-166 Attendance page | ✅ | ⏳ | ⏳ | ⏳ | ⏳ Platform blocked |
| MYK-167 Export CSV | ✅ | ✅ | ✅ | ✅ | ✅ DONE |
| MYK-162 CI verde | ✅ | ✅ | ✅ | ✅ | ✅ DONE |

---

## Next Board Operator Actions (Priority Order)

1. **Verify platform gateway fix** — attempt comment on any issue
2. **If platform fixed**: Post dispositions for MYK-165/166/168/185
3. **Post `request_confirmation`** on MYK-183 for SMTP decision
4. **If Option A chosen**: Assign MYK-184 to devops with credentials
5. **Sprint Review**: Update SPRINT-2.md with final evidence
6. **Retro**: Document in RETRO-2.md + SHARED-MEMORY entries
7. **Sprint Close**: Move undone items to backlog WITHOUT assignee

---

**All dispositions ready locally. Awaiting platform gateway fix to push to board.**