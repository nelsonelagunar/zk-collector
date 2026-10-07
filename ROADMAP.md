# ZK-Collector Roadmap

## Vision
Every business that owns a ZKTeco attendance device should be able to use it without paying for proprietary software licenses.

## v2.0 — Foundation (Current)
**Target: Q4 2026 | Status: Alpha**

- [x] Core ZKTeco collector (pyzk integration)
- [x] SQLite offline buffer
- [x] Web GUI (Flask + Tailwind CSS)
- [x] Device CRUD from dashboard
- [x] Connection testing
- [x] Health monitoring + heartbeat
- [x] HTTPS cloud sync client
- [ ] Docker image (ARM64 + x86_64)
- [ ] docker-compose for single-command deploy
- [ ] Auto-discovery of ZKTeco devices on LAN
- [ ] CSV/Excel attendance export
- [ ] Password reset flow
- [ ] Comprehensive test suite

## v2.1 — SaaS Platform
**Target: Q1 2027**

- [ ] Multi-tenant backend (Go + PostgreSQL)
- [ ] API token authentication
- [ ] Organization → Branch → Device hierarchy
- [ ] Employee management (CRUD + biometric sync)
- [ ] Attendance rules engine (shifts, grace periods, overtime)
- [ ] Email/WhatsApp notifications for anomalies
- [ ] Stripe/PayPal billing integration

## v2.2 — Payroll Ready
**Target: Q2 2027**

- [ ] Mexican payroll export (SUA/IDSE compatible)
- [ ] CFDI attendance complement (SAT)
- [ ] Integration with popular payroll systems (Aspel, CONTPAQi)
- [ ] Custom report builder
- [ ] Audit trail with digital signatures

## v3.0 — Mobile + Intelligence
**Target: Q4 2027**

- [ ] Flutter mobile app (employee self-service)
- [ ] Push notifications (late arrivals, absences)
- [ ] AI-powered attendance anomaly detection
- [ ] Multi-country support (LATAM expansion)
- [ ] Hardware bundle partnerships (device + software)

## Business Model

| Tier | Price (MXN/mo) | Target |
|------|----------------|--------|
| **Free/OSS** | $0 | 1 device, local only |
| **Starter** | $499 | Cloud sync, 3 devices, reports |
| **Business** | $999 | Unlimited devices, payroll export, API |
| **Enterprise** | $2,999 | Multi-branch, SSO, custom integrations |
