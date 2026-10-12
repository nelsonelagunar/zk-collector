# Sprint 1 — ZK-Collector v2.0 Alpha

**Sprint Goal:** Validate CI pipeline, harden docker-compose deployment, and complete password reset flow for WebGUI

**Dates:** 2026-10-12 (Mon) → 2026-10-17 (Fri)  
**Cadence:** Weekly sprint | Planning Mon 09:00 | Daily 10:00 | Review+Retro Fri 16:00

---

## Sprint Backlog (MYK-144 through MYK-148)

| Order | Issue | Task (from BACKLOG.md) | Priority | Assignee | Criteria of Done |
|-------|-------|------------------------|----------|----------|------------------|
| 1 | **MYK-144** | **Verify CI passes** — ci.yml + docker.yml multi-arch build & smoke test | Critical | DevOps | ✅ Both workflows green on `feature/myk-92-dashboard-modernization`; coverage ≥80% on core modules |
| 2 | **MYK-145** | **Validate docker-compose end-to-end** — fresh machine deploy test | Critical | DevOps | ✅ `docker-compose up -d` starts collector + webgui; `/health` and `/docs` respond 200; supervisord manages both processes |
| 3 | **MYK-146** | **Complete password reset flow** — email integration or admin fallback | Medium | Backend Dev | ✅ Forgot password → reset token → new password works; email sent (or admin UI fallback if SMTP not configured) |
| 4 | **MYK-147** | **Ensure CI runs on every PR** + coverage reporting | Critical | Backend Dev | ✅ PR triggers ci.yml; coverage badge/artifact posted; coverage-check job enforces ≥80% |
| 5 | **MYK-148** | **Docker multi-arch image published** — ARM64 + x86_64 to GHCR | Critical | DevOps | ✅ docker.yml pushes multi-arch manifest to `ghcr.io/nelsonelagunar/zk-collector` on tag push |

---

## Definition of Done (Gate for All Items)

A task is **Done** ONLY when:
- [ ] Code merged to `feature/myk-92-dashboard-modernization` (or `master` post-merge)
- [ ] All CI jobs pass (lint, type-check, unit, integration, coverage-check, security-scan, build-and-test-docker)
- [ ] Code review approved by at least 1 reviewer
- [ ] QA verified (tester sign-off on integration test scenarios)
- [ ] If deploy-affecting: devops verified docker-compose / docker image works on target platform

---

## Capacity & Risks

| Risk | Mitigation |
|------|------------|
| No ARM64 runner in GitHub free tier | Already mitigated: ci.yml uses `docker/setup-qemu-action` + `buildx` for ARM64 emulation |
| No real ZKTeco device in CI | Already mitigated: integration tests mock `pyzk` (see `tests/integration/test_collector_integration.py`) |
| SMTP not configured in CI for password reset | Use admin fallback (reset_password.html renders token) or mock SMTP in test |
| Concurrent mutations from shared workspace (MYK-139) | Coordinate via commits; push early, rebase often |

---

## Daily Standup Protocol (10:00 Mon–Fri)

Each assignee posts a 3-line comment on their issue:
```
1. Done yesterday: <what>
2. Blocked by: <issue/title or "none">
3. Next: <specific next action>
```

PM (coffee) will aggregate into sprint standup summary.

---

## Sprint Review + Retro (Friday 16:00)

**Review:** Verify each item against Definition of Done → disposition to board  
**Retro:** 3 worked / 3 failed / 3 actions → document in `RETRO-1.md` + post 1 line each to SHARED MEMORY  
**Carryover:** Unfinished items return to backlog **unassigned** (next planning re-evaluates)