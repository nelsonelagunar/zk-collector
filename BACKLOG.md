# ZK-Collector Backlog — Ordered Release Plan

**Status:** v2.0 Alpha (current branch: feature/myk-92-dashboard-modernization)  
**Target:** Q4 2026  
**Last Updated:** 2026-10-12

---

## ✅ Phase 1 — Foundation Complete (Done in v1.0.0)
These were completed in the initial release (commit 706016d through a872c85):

| # | Task | Evidence |
|---|------|----------|
| 1 | Core ZKTeco collector (pyzk integration) | `src/zk/client.py` |
| 2 | SQLite offline buffer | `src/buffer/repository.py` |
| 3 | Web GUI (Flask + Tailwind CSS) | `src/webgui/server.py`, `templates/` |
| 4 | Device CRUD from dashboard | `src/webgui/routes/devices.py` |
| 5 | Connection testing | `src/zk/client.py:is_online()` |
| 6 | Health monitoring + heartbeat | `src/monitoring/health.py` |
| 7 | HTTPS cloud sync client | `src/sync/platform.py` |
| 8 | OpenAPI 3.1 spec + Swagger UI | `docs/openapi.yaml`, `src/webgui/routes/apidocs.py` |
| 9 | Full documentation set | `docs/*.md` |
| 10 | Dockerfile (basic) | `Dockerfile` |

---

## 🚧 Phase 2 — v2.0 Alpha Remaining (In Progress / To Do)

| # | Task | Priority | Status | Notes |
|---|------|----------|--------|-------|
| **11** | **Docker image (ARM64 + x86_64 multi-arch)** | Critical | In Progress | GitHub Actions workflows exist (ci.yml, docker.yml); needs CI validation |
| **12** | **docker-compose for single-command deploy** | Critical | In Progress | `docker-compose.yml` updated with env validation, healthchecks, volumes; docker-entrypoint.sh validates required vars |
| **13** | **Auto-discovery of ZKTeco devices on LAN** | High | Done | `src/zk/discovery.py` implemented; UDP broadcast on port 4370; integrates with WebGUI "Add Device" |
| **14** | **CSV/Excel attendance export** | High | Done | `src/webgui/routes/attendance.py` + `templates/attendance/list.html`; streaming CSV/Excel with filters |
| **15** | **Password reset flow** | Medium | In Progress | Templates (`forgot_password.html`, `reset_password.html`) + routes in `auth.py`; needs email integration |
| **16** | **Comprehensive test suite** | Critical | In Progress | Unit tests (buffer, zk_client, config, collector); integration tests with mocked ZK device; CI pipeline exists |

---

## 🔧 Phase 3 — Code Quality & Hardening (From current branch changes)

| # | Task | Priority | Status | Notes |
|---|------|----------|--------|-------|
| **17** | **Config encryption CLI (`zk-encrypt`)** | High | Done | Added in `src/security/encryption.py:main()`, exposed in `pyproject.toml` |
| **18** | **Config validation CLI (`--validate-config`)** | High | Done | Added in `src/main.py:parse_args()` |
| **19** | **Structured logging (JSON/text)** | Medium | Done | `src/utils/logging.py`, config `logging.format` |
| **20** | **Device password as string + Fernet encryption** | High | Done | `src/core/config.py`, `src/zk/client.py` |
| **21** | **Config defaults for all sections** | Medium | Done | `buffer.db_path`, `logging.format`, list-item defaults |
| **22** | **Constants centralization** | Low | Done | `src/core/constants.py` used by main, collector, webgui |
| **23** | **Theme toggle (dark/light)** | Low | Done | Commit 6496d63; UI enhancement |

---

## 📋 Phase 4 — v2.1 SaaS Platform (Planned Q1 2027)

| # | Task | Priority | Status | Notes |
|---|------|----------|--------|-------|
| **24** | Multi-tenant backend (Go + PostgreSQL) | Critical | Planned | New repo/service |
| **25** | API token authentication | Critical | Planned | JWT-based |
| **26** | Organization → Branch → Device hierarchy | High | Planned | Data model |
| **27** | Employee management (CRUD + biometric sync) | High | Planned | |
| **28** | Attendance rules engine (shifts, grace, overtime) | High | Planned | |
| **29** | Email/WhatsApp notifications for anomalies | Medium | Planned | |
| **30** | Stripe/PayPal billing integration | Medium | Planned | |

---

## 📋 Phase 5 — v2.2 Payroll Ready (Planned Q2 2027)

| # | Task | Priority | Status | Notes |
|---|------|----------|--------|-------|
| **31** | Mexican payroll export (SUA/IDSE compatible) | Critical | Planned | |
| **32** | CFDI attendance complement (SAT) | Critical | Planned | |
| **33** | Integration with Aspel, CONTPAQi | High | Planned | |
| **34** | Custom report builder | Medium | Planned | |
| **35** | Audit trail with digital signatures | Medium | Planned | |

---

## 📋 Phase 6 — v3.0 Mobile + Intelligence (Planned Q4 2027)

| # | Task | Priority | Status | Notes |
|---|------|----------|--------|-------|
| **36** | Flutter mobile app (employee self-service) | High | Planned | |
| **37** | Push notifications (late arrivals, absences) | High | Planned | |
| **38** | AI-powered attendance anomaly detection | Medium | Planned | |
| **39** | Multi-country support (LATAM expansion) | Medium | Planned | |
| **40** | Hardware bundle partnerships | Low | Planned | |

---

## 🎯 Immediate Next Actions (This Sprint)

| Order | Task ID | Action | Owner |
|-------|---------|--------|-------|
| 1 | **11** | **Verify CI passes** (ci.yml + docker.yml multi-arch build & smoke test) | DevOps |
| 2 | **12** | Validate docker-compose.yml works end-to-end on fresh machine | DevOps |
| 3 | **15** | Complete password reset flow: email integration or admin fallback | Backend Dev |
| 4 | **16** | Ensure CI runs on every PR + coverage reporting | Backend Dev |

---

## 📌 Blockers / Risks

| Task | Blocker | Mitigation |
|------|---------|------------|
| 11 | No ARM64 runner in GitHub Actions free tier | **Mitigated**: ci.yml uses docker/setup-qemu-action + buildx for ARM64 emulation |
| 13 | ZKTeco discovery protocol undocumented | **Mitigated**: Implemented in `src/zk/discovery.py` based on pyzk reverse-engineering |
| 15 | No email SMTP configured in CI | Use admin fallback (reset_password.html) or test with mock SMTP |
| 16 | No real device in CI | **Mitigated**: Mock pyzk in integration tests (test_collector_integration.py) |

---

## 🔗 Related Issues / References

- ROADMAP.md — Full roadmap
- CHANGELOG.md — v1.0.0 release notes
- AGENTS.md — Project conventions
- Current branch: `feature/myk-92-dashboard-modernization` (theme toggle + config refactor)