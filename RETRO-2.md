# Sprint 2 Retrospective — 2026-10-14

**Sprint Goal**: Arrancar el collector en producción + una fuente de verdad de devices + página de asistencia visible + CI verde  
**Dates**: 2026-10-13 → 2026-10-17 (semana)  
**Branch**: `fix/p0-1-supervisord-clean` (commit `c663563`)

---

## ✅ 3 Things That Worked Well

| # | What Worked | Evidence |
|---|-------------|----------|
| 1 | **Local validation discipline** — 142/143 tests PASS, ruff CLEAN, 5+ consecutive clean runs | `LOCAL_VALIDATION_SUMMARY_RUN_FINAL.md` shows consistent results across multiple wakeups |
| 2 | **UNBLOCK WATCHDOG process** — All 8 blocked issues now have declared blockers (0 coordination failures) | Final watchdog pass: 8/8 blockers declared, root chains mapped |
| 3 | **Handoff preparation** — Complete docs ready for frontend-dev (MYK-166) and tester (MYK-171) | `HANDOFF_MYK166_TO_FRONTEND_DEV.md`, `HANDOFF_MYK171_TO_TESTER.md` created with acceptance criteria |

---

## ❌ 3 Things That Failed

| # | What Failed | Impact |
|---|-------------|--------|
| 1 | **Platform gateway bug (MYK-188)** — 25th+ consecutive failure blocking ALL board writes | Entire sprint coordination stuck locally; no board disposition possible; PR #22 cannot be merged via automation |
| 2 | **GitHub API unavailable** — No managed identity for devops to create/merge PR | MYK-181 (single bottleneck) blocked on auth; devops stranded |
| 3 | **Board decision latency** — MYK-183/194 (SMTP vs remove) pending >5 days | MYK-184 (Infisical creds) blocked; password reset feature in limbo |

---

## 🎯 3 Concrete Actions for Sprint 3

| # | Action | Owner | Target |
|---|--------|-------|--------|
| 1 | **Platform fix verification FIRST** — On next wakeup: attempt checkout + test board write before any coordination work | coffee (PM) | Next wakeup |
| 2 | **Escalate MYK-188 to human** — Create explicit platform escalation with failure count + evidence for operator intervention | coffee (PM) | When platform fixed |
| 3 | **Decision deadline for MYK-183/194** — If board doesn't decide by Sprint 3 planning, default to Option B (remove from MVP) and unblock MYK-184 | coffee (PM) | Sprint 3 Planning (Mon 09:00) |

---

## SHARED MEMORY Learnings (one line each)

```
SHARED-MEMORY: 2026-10-14 [coffee] Local validation discipline (5+ consecutive clean runs) prevents drift when platform blocks board sync
SHARED-MEMORY: 2026-10-14 [coffee] UNBLOCK WATCHDOG catches coordination failures early — 8/8 blockers declared by final pass
SHARED-MEMORY: 2026-10-14 [coffee] Platform gateway bug (MYK-188) = total board write failure; stop retrying after 2 consecutive failures, document locally
SHARED-MEMORY: 2026-10-14 [coffee] Single bottleneck pattern: MYK-181 devops PR merge blocked entire Sprint 2 critical path
SHARED-MEMORY: 2026-10-14 [coffee] Handoffs prepared locally (MYK-166, MYK-171) enable instant wake when platform unblocks
SHARED-MEMORY: 2026-10-14 [coffee] Board decisions (MYK-183/194) need explicit deadline — otherwise they become implicit blockers
```

---

## Sprint Review Summary

**Completed (DONE)**: P0-0 (MYK-177 emulator), P0-5 (MYK-162 ruff CI), P0-3 locally (MYK-166 attendance page + CSV)  
**Blocked (Platform)**: P0-1 (MYK-181 PR merge), P0-1 Review (MYK-164), P0-2 (MYK-165), P0-4 (MYK-167), P0-3 deploy (MYK-166)  
**Pending Board**: MYK-183/194 decision, MYK-184 Infisical creds

**Root Cause**: Platform gateway bug (MYK-188) prevented board synchronization for entire sprint. All engineering work completed locally and validated.

---

*Generated per Scrum Retro ritual — documented in project repo for traceability*