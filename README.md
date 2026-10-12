# ZK-Collector

**Reuse your legacy ZKTeco biometric attendance devices with a modern web dashboard. No ZKAccess license. No Windows. Just Python + a Raspberry Pi.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)
[![Python 3.12+](https://img.shields.io/badge/python-3.12+-blue.svg)](https://python.org)
[![Status: Alpha](https://img.shields.io/badge/status-alpha-orange.svg)]()

## 🎯 The Problem

Thousands of Mexican businesses use ZKTeco biometric devices (K40, U160, X628, etc.) for employee attendance. The official software (ZKAccess/ZKBioSecurity) requires:
- Windows-only installation
- Expensive per-device licenses
- Annual maintenance contracts
- Vendor lock-in

Small businesses (10-100 employees) can't justify the cost but **already own the hardware**.

## 💡 The Solution

ZK-Collector is an **open-source bridge** that connects legacy ZKTeco devices to a modern web dashboard:

```
┌──────────────────┐     ┌──────────────────┐     ┌──────────────────┐
│  ZKTeco Device   │────▶│   ZK-Collector   │────▶│   Web Dashboard  │
│  (K40/U160/X628) │     │  (Raspberry Pi)  │     │  (Any Browser)   │
│  192.168.1.101   │     │  Python + SQLite  │     │  Flask + HTMX    │
└──────────────────┘     └──────────────────┘     └──────────────────┘
        ▲                         │
        │                         ▼
        │                  ┌──────────────────┐
        └──────────────────│  Cloud Sync API  │
           (optional)      │  (SaaS Platform) │
                           └──────────────────┘
```

## ✨ Features

- **Zero-config polling** — auto-discovers ZKTeco devices on your LAN
- **Offline-first** — SQLite buffer survives network outages
- **Web dashboard** — real-time device status, attendance logs, reports
- **Multi-device** — manage multiple checkers from one dashboard
- **Export-ready** — CSV/Excel export for payroll systems
- **Cloud sync** — optional HTTPS sync to SaaS platform
- **Runs anywhere** — Raspberry Pi 3/4, Docker, bare Linux

## 🚀 Quickstart

### Docker (Recommended)

```bash
# Quick start with docker-compose (recommended)
cp .env.example .env
# Edit .env to set ZK_ADMIN_PASSWORD and ENCRYPTION_KEY
docker-compose up -d
```

```bash
# Or run directly (requires both ZK_ADMIN_PASSWORD and ENCRYPTION_KEY)
docker run -d \
  --name zk-collector \
  -p 8080:8080 \
  -v zk-data:/app/data \
  -v zk-logs:/app/logs \
  -e ZK_ADMIN_PASSWORD=changeme \
  -e ENCRYPTION_KEY=$(python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())") \
  ghcr.io/nelsonelagunar/zk-collector:latest
```

**Note:** The container now runs both the collector (polls ZKTeco devices) and the web dashboard via supervisord. Both processes are managed with auto-restart policies and health checks.

### Raspberry Pi (Bare Metal)

```bash
# Clone and install
git clone https://github.com/nelsonelagunar/zk-collector.git
cd zk-collector
python3 -m venv venv && source venv/bin/activate
pip install -e .

# Run the collector + web dashboard
zk-collector --config configs/devices.yaml
```

### First Steps

1. Open `http://<pi-ip>:8080` in your browser
2. Login (default: `admin` / set via `ZK_ADMIN_PASSWORD`)
3. Add your ZKTeco device(s) from the dashboard
4. Attendance records start flowing immediately

## 📖 Documentation

- [Installation Guide](docs/installation.md) — Pi, Docker, bare metal
- [Device Compatibility](docs/devices.md) — tested ZKTeco models
- [API Reference](docs/api.md) — REST endpoints
- [Configuration](docs/configuration.md) — all options

## 🏗️ Architecture

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Collector** | Python 3.12 + pyzk | Polls ZKTeco devices via TCP/UDP |
| **Buffer** | SQLite | Offline-first local storage |
| **Web GUI** | Flask 3 + Tailwind CSS | Device management + reports |
| **Sync** | requests + HTTPS | Cloud platform integration |
| **Deploy** | Docker + docker-compose | One-command deployment |

## 📋 Roadmap

| Version | Status | Features |
|---------|--------|----------|
| v2.0 | 🚧 Alpha | Core collector + web dashboard + Docker |
| v2.1 | 📋 Planned | Multi-tenant SaaS + API tokens |
| v2.2 | 📋 Planned | Payroll export (SAT/CFDI Mexico) |
| v3.0 | 💭 Future | Mobile app + push notifications |

See [ROADMAP.md](ROADMAP.md) for the full plan.

## 🤝 Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) to get started.

**We need help with:**
- Testing with ZKTeco models we don't have access to
- Spanish/Mexican localization
- Payroll system integrations

## 📄 License

MIT License — use it, fork it, sell it. Just keep the copyright notice.

## 🙏 Acknowledgments

- [pyzk](https://github.com/fananimi/pyzk) — the ZKTeco protocol library that makes this possible
- Every small business owner who bought a ZKTeco checker and got stuck with expensive software
