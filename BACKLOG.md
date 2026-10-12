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
| **11** | **Docker image (ARM64 + x86_64 multi-arch)** | Critical | In Progress | `Dockerfile` exists; needs multi-arch build via GitHub Actions / buildx |
| **12** | **docker-compose for single-command deploy** | Critical | In Progress | `docker-compose.yml` exists; needs env var validation, healthcheck tuning |
| **13** | **Auto-discovery of ZKTeco devices on LAN** | High | Done | UDP broadcast on port 4370; integrated into WebGUI "Add Device" flow |
| **14** | **CSV/Excel attendance export** | High | TODO | Endpoint in WebGUI; stream large datasets; add date range filters |
| **15** | **Password reset flow** | Medium | TODO | Email token or admin reset via WebGUI; secure token generation |
| **16** | **Comprehensive test suite** | Critical | Partial | Unit tests exist (`tests/test_buffer.py`, `tests/test_zk_client.py`); need integration + e2e |

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
| 1 | **11** | Configure GitHub Actions multi-arch Docker build (ARM64 + x86_64) | DevOps |
| 2 | **12** | Validate docker-compose.yml: env vars, healthcheck, volumes | DevOps |
| 3 | **16** | Add integration tests (mock ZK device) + GitHub Actions CI | Backend Dev |
| 4 | **13** | Implement LAN auto-discovery (UDP broadcast) + WebGUI integration | Backend Dev |
| 5 | **14** | Add CSV/Excel export endpoint to WebGUI | Frontend Dev |
| 6 | **15** | Implement password reset flow (email or admin) | Backend Dev |

---

## 📌 Blockers / Risks

| Task | Blocker | Mitigation |
|------|---------|------------|
| 11 | No ARM64 runner in GitHub Actions free tier | Use `docker/buildx` with QEMU emulation or self-hosted runner |
| 13 | ZKTeco discovery protocol undocumented | Reverse-engineer from pyzk / wireshark captures |
| 16 | No real device in CI | Mock pyzk in unit tests; document manual integration test process |

---

## 🔗 Related Issues / References

- ROADMAP.md — Full roadmap
- CHANGELOG.md — v1.0.0 release notes
- AGENTS.md — Project conventions
- Current branch: `feature/myk-92-dashboard-modernization` (theme toggle + config refactor)