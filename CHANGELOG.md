# Changelog

All notable changes to ZK-Collector are documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.1.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [1.0.0] - 2026-10-08

### Added
- Initial public release
- **Collector**: Polling engine for ZKTeco devices (UDP/TCP 4370) via pyzk
- **Buffer**: Offline-first SQLite queue with retry/backoff for attendance records
- **Sync**: HTTPS push to Attendance SaaS platform with Fernet-encrypted config
- **WebGUI** (Flask, port 8080): session auth, device CRUD, live status probes, attendance query/export (CSV), sync status/trigger
- **API docs**: OpenAPI 3.1 spec (`docs/openapi.yaml`) served with Swagger UI at `/api/docs`
- Docker image, Raspberry Pi and bare-metal install paths (see `docs/installation.md`)
- Documentation set: quickstart, configuration reference, device compatibility matrix, architecture overview, security hardening, troubleshooting, contributing guide

### Security
- Device credentials stored Fernet-encrypted; never logged
- Session cookies `HttpOnly` + `SameSite=Lax`
- Documented LAN-only requirement for ZKTeco protocol port 4370 (unencrypted, unauthenticated wire protocol)
