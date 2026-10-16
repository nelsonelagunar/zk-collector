# AGENTS.md — ZK-Collector Project

## Project Identity
ZK-Collector is an open-source Python application that enables businesses to reuse their existing ZKTeco biometric attendance devices with a modern web dashboard, eliminating the need for expensive proprietary software licenses.

## Stack
- **Language:** Python 3.12+
- **Web Framework:** Flask 3.x + Tailwind CSS + Alpine.js
- **Database:** SQLite (collector) / PostgreSQL (SaaS, future)
- **ZK Protocol:** pyzk library (TCP/UDP port 4370)
- **Auth:** Argon2id + PyJWT
- **Deployment:** Docker (ARM64/x86_64), Raspberry Pi 3/4
- **CI/CD:** GitHub Actions

## Architecture Decisions
1. **Offline-first:** SQLite buffer ensures no data loss during network outages
2. **Polling model:** Collector polls devices at configurable intervals (default 60s)
3. **Sync-on-change:** Only new records get synced to cloud platform
4. **WebGUI bundled:** Flask app runs alongside collector in same process
5. **Device-agnostic:** pyzk abstracts ZKTeco protocol differences

## Hard Rules
1. **NEVER store device passwords in plaintext** — use Fernet encryption (cryptography lib)
2. **NEVER expose the collector port (4370) to the internet** — LAN-only device communication
3. **ALWAYS validate ZKTeco responses** — devices can return malformed data
4. **Test on real hardware before release** — emulators miss protocol edge cases
5. **Respect rate limits** — don't hammer devices; default 60s polling interval

## Repository Conventions
- Branch: `master` (default), features via `feature/<name>`
- Commits: conventional commits (`feat:`, `fix:`, `docs:`, `refactor:`)
- PRs: require CI pass + at least 1 review
- Issues: use templates (bug, feature, device compatibility report)

## Deploy
- **Development:** `pip install -e ".[dev]"` → `zk-collector --dev`
- **Docker:** `docker-compose up -d` (see `docker-compose.yml`)
- **Production (Pi):** systemd service (`deploy/zk-collector.service`)
- **Cloud:** Coolify app pointing at this repo's `master` branch

## Testing
```bash
# Unit tests
pytest tests/unit/ -v

# Integration (requires real device on LAN)
pytest tests/integration/ -v --device-ip=192.168.1.101

# Full suite
pytest --cov=src --cov-report=html
```

## Device Compatibility
Tested models (add to this list as community reports come in):
- ZKTeco K40 ✅
- ZKTeco U160 ✅
- ZKTeco X628 ✅
- ZKTeco iClock 3000 ✅
- ZKTeco SpeedFace V5L ⚠️ (partial — face recognition not supported)

## Key Files
- `src/zk/client.py` — ZKTeco device communication wrapper
- `src/core/collector.py` — Main orchestrator (poll → buffer → sync)
- `src/webgui/server.py` — Flask web dashboard
- `src/buffer/repository.py` — SQLite data access layer
- `src/sync/platform.py` — Cloud sync HTTP client
- `configs/devices.yaml` — Device configuration template

## Hard-won lessons (deploy)
- WebGUI DB schema has ONE truth: `migrations/001_initial_schema.sql` → devices use `address`/`is_enabled` (never `ip`/`enabled`). Any SQL touching `devices` must match it.
- The Docker image MUST `COPY migrations/ migrations/`: `src/webgui/database.py` only logs a warning when the migrations dir is missing → webgui.db silently has NO tables → every `current_app.db` endpoint 500s while `/health` and buffer endpoints stay 200.
- DB paths: everything reads `WEBGUI_DB_PATH` (default `/app/data/webgui.db`) — server.py, collector (`_load_devices_from_webgui_db`) and docker-entrypoint.sh. Don't reintroduce divergent env names.
- Lint-only commits are dangerous here: 57cd695 (ruff pass) silently deleted `_load_devices_from_webgui_db` (MYK-172/210 feature) — review behavior diffs, not just style, on "lint" PRs.
