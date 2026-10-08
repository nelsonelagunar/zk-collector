# Architecture Overview

ZK-Collector follows a modular, offline-first architecture designed for reliability on resource-constrained hardware (Raspberry Pi).

---

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                            ZK-COLLECTOR PROCESS                               │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐  ┌──────────────┐    │
│  │   Collector  │──│    Buffer    │──│    Sync      │──│  Platform    │    │
│  │  (poller)    │  │  (SQLite)    │  │  (HTTPS)     │  │  (SaaS)      │    │
│  └──────┬───────┘  └──────┬───────┘  └──────┬───────┘  └──────────────┘    │
│         │                 │                 │                                │
│         ▼                 ▼                 ▼                                │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        WebGUI (Flask)                                │    │
│  │  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐  ┌─────────┐   │    │
│  │  │ Auth    │  │Devices  │  │Attendance│  │ Sync    │  │ Health  │   │    │
│  │  └─────────┘  └─────────┘  └─────────┘  └─────────┘  └─────────┘   │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
│                                                                             │
│  ┌─────────────────────────────────────────────────────────────────────┐    │
│  │                        Shared Components                             │    │
│  │  Config  •  Logging  •  Encryption  •  Health Monitor              │    │
│  └─────────────────────────────────────────────────────────────────────┘    │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Component Details

### 1. Collector (`src/core/collector.py`)

**Role:** Main orchestrator coordinating all components.

**Responsibilities:**
- Initialize and manage device connections
- Run polling loop at configured intervals
- Coordinate buffer and sync operations
- Manage health monitoring

**Key Methods:**
- `poll_devices()` - Iterate all devices, fetch attendance
- `sync_to_platform()` - Push unsynced records to cloud
- `run()` - Main event loop

**Configuration:**
```python
poll_interval = config.get('poll_interval_seconds', 300)  # 5 min default
sync_interval = config.get('sync_interval_seconds', 60)   # 1 min default
```

---

### 2. ZK Client (`src/zk/client.py`)

**Role:** Wrapper around `pyzk` library for ZKTeco device communication.

**Responsibilities:**
- TCP/UDP connection management with retries
- Device authentication (comm key)
- Attendance record retrieval
- Device info queries (firmware, serial, platform)
- Connection lifecycle (enable/disable device during read)

**Key Methods:**
- `connect(max_retries=3, retry_delay=2.0)`
- `get_attendance(clear_after_read=False, disable_device=True)`
- `get_firmware_version()`, `get_serialnumber()`, `get_platform()`
- `disconnect()`

**Protocol Details:**
- Port: 4370 (TCP default, UDP optional)
- Default password: 0
- Timeout: 5 seconds (configurable)

---

### 3. Buffer (`src/buffer/repository.py`)

**Role:** SQLite-based offline-first storage for attendance records.

**Schema:**
```sql
CREATE TABLE attendance_buffer (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    device_id INTEGER NOT NULL,
    user_id TEXT NOT NULL,
    timestamp DATETIME NOT NULL,
    punch_type TEXT NOT NULL,      -- check_in, check_out, etc.
    verified INTEGER DEFAULT 1,    -- 1=verified, 0=unverified
    synced INTEGER DEFAULT 0,      -- 0=pending, 1=synced, 2=failed
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    synced_at DATETIME
);

CREATE TABLE sync_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    records_synced INTEGER DEFAULT 0,
    records_failed INTEGER DEFAULT 0,
    status TEXT NOT NULL,          -- success, failed, partial
    error_message TEXT,
    duration_seconds REAL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

**Key Features:**
- **Offline-first:** Records stored locally immediately
- **Deduplication:** Unique constraint on (device_id, user_id, timestamp)
- **Sync tracking:** `synced` column tracks platform sync status
- **Cleanup:** Automatic removal of old synced records (`cleanup_days`)
- **Capacity limit:** `max_records` prevents unbounded growth

**Key Methods:**
- `add_records(attendances)` - Bulk insert with deduplication
- `get_unsynced_records(limit=1000)` - Fetch pending for sync
- `mark_as_synced(record_ids)` - Update sync status
- `mark_sync_failed(record_ids)` - Mark for retry
- `log_sync(...)` - Record sync attempt in log table
- `cleanup_old_records()` - Remove synced records older than N days

---

### 4. Platform Sync (`src/sync/platform.py`)

**Role:** HTTPS client for cloud platform integration.

**Responsibilities:**
- Authenticate with platform (API key + tenant ID)
- Batch sync attendance records
- Handle retries with exponential backoff
- Report sync status

**Configuration:**
```yaml
platform:
  url: "https://api.example.com"    # Base API URL
  api_key: "sk_live_..."            # Bearer token
  tenant_id: "tenant-001"           # Multi-tenant identifier
  timeout: 30                       # Request timeout (seconds)
  retry_attempts: 3                 # Retry count
```

**Sync Flow:**
```
1. GET unsynced records from buffer (max 1000)
2. POST /api/v1/attendance/batch with records
3. On 2xx: mark records synced in buffer
4. On error: mark failed, log error, retry next cycle
```

---

### 5. WebGUI (`src/webgui/`)

**Role:** Flask-based web dashboard for device management and monitoring.

**Routes:**
```
/                           Dashboard (stats, quick actions)
/auth/login                 Login page
/auth/logout                Logout
/auth/setup                 First-run admin creation
/devices                    Device management UI
/devices/api/devices        REST: CRUD devices
/devices/api/devices/test   REST: Test device connection
/devices/api/attendance     REST: Query attendance
/devices/api/attendance/stats REST: Attendance statistics
/devices/api/attendance/export REST: CSV export
/devices/api/sync/status    REST: Sync status
/devices/api/sync/trigger   REST: Manual sync
/health                     Health check (no auth)
```

**Architecture:**
- **Blueprint-based:** Modular route registration
- **Session auth:** Flask-Login with secure cookies
- **Database:** Separate SQLite (`webgui.db`) for users/devices config
- **Templates:** Jinja2 with Tailwind CSS + Alpine.js
- **Static assets:** Served by Flask (dev) or reverse proxy (prod)

---

### 6. Health Monitor (`src/monitoring/health.py`)

**Role:** Background thread for system health checks and heartbeats.

**Checks:**
- Platform connectivity (HTTP HEAD to platform URL)
- Buffer size (alert if > 80% capacity)
- Device connectivity (last successful poll)
- Disk space (data directory)
- Memory usage

**Heartbeat:** Periodic POST to platform `/health` endpoint with:
```json
{
  "collector_id": "zk-collector-001",
  "status": "healthy",
  "devices_online": 3,
  "devices_total": 4,
  "pending_records": 42,
  "buffer_usage_pct": 15,
  "timestamp": "2026-01-15T10:30:00Z"
}
```

---

## Data Flow

### Polling Cycle

```
┌─────────────┐
│  Scheduler  │  (every poll_interval_seconds)
└──────┬──────┘
       ▼
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ For each    │────▶│  ZKClient    │────▶│  pyzk      │
│ device:     │     │  connect()   │     │  protocol  │
└─────────────┘     └──────────────┘     └────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ get_        │◀────│  ZKClient    │◀────│  Device    │
│ attendance()│     │  returns     │     │  returns   │
└──────┬──────┘     │  records[]   │     │  raw data  │
       │            └──────────────┘     └────────────┘
       ▼
┌─────────────┐
│ Buffer.     │
│ add_records │
└─────────────┘
```

### Sync Cycle

```
┌─────────────┐
│  Scheduler  │  (every sync_interval_seconds)
└──────┬──────┘
       ▼
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ Buffer.     │────▶│  Platform    │────▶│  Platform  │
│ get_unsynced│     │  Sync POST   │     │  API       │
└─────────────┘     └──────────────┘     └────────────┘
       │                    │                    │
       ▼                    ▼                    ▼
┌─────────────┐     ┌──────────────┐     ┌────────────┐
│ mark_       │◀────│  Response    │◀────│  Returns   │
│ _synced()   │     │  2xx/5xx     │     │  200 OK    │
└─────────────┘     └──────────────┘     └────────────┘
```

---

## Concurrency Model

```
Main Thread (Collector)
├── Polling Loop (every 300s)
│   └── Sequential device polling (one at a time)
├── Sync Loop (every 60s)
│   └── Single batch sync to platform
└── Signal handling (SIGINT/SIGTERM)

Background Thread (HealthMonitor)
└── Heartbeat + health checks (every 300s)

WebGUI (Flask/Gunicorn - separate process in Docker)
├── Worker 1 (request handling)
├── Worker 2 (request handling)
└── Shared: webgui.db (SQLite, WAL mode for concurrency)
```

**Note:** Collector and WebGUI run in separate processes. They share:
- `devices.yaml` config (read-only for WebGUI)
- Buffer database (WebGUI reads, Collector writes)

---

## Deployment Architectures

### 1. Single Node (Raspberry Pi / Docker)

```
┌──────────────────────────────────────┐
│         Raspberry Pi / Server         │
│  ┌──────────┐  ┌──────────────────┐  │
│  │ Collector│  │    WebGUI        │  │
│  │ Process  │  │  (Gunicorn)      │  │
│  └────┬─────┘  └────────┬─────────┘  │
│       │                 │            │
│       └────────┬────────┘            │
│                ▼                     │
│         ┌──────────────┐             │
│         │   SQLite     │             │
│         │  (buffer.db, │             │
│         │   webgui.db) │             │
│         └──────────────┘             │
└──────────────────────────────────────┘
```

### 2. Docker Compose

```
┌──────────────────────────────────────┐
│         Docker Host                   │
│  ┌────────────────────────────────┐  │
│  │ zk-collector container          │  │
│  │  - Collector + WebGUI (gunicorn)│  │
│  │  - Volume: /app/data            │  │
│  └────────────────────────────────┘  │
│                │                      │
│                ▼                      │
│         ┌──────────────┐             │
│         │ zk-data vol  │             │
│         │ (SQLite dbs) │             │
│         └──────────────┘             │
└──────────────────────────────────────┘
```

### 3. Multi-Collector (Future)

```
┌─────────────┐   ┌─────────────┐   ┌─────────────┐
│ Collector A │   │ Collector B │   │ Collector C │
│ Site 1      │   │ Site 2      │   │ Site 3      │
└──────┬──────┘   └──────┬──────┘   └──────┬──────┘
       │                 │                 │
       └─────────────────┼─────────────────┘
                         ▼
              ┌─────────────────────┐
              │   SaaS Platform     │
              │  (Multi-tenant)     │
              └─────────────────────┘
```

---

## Security Boundaries

```
INTERNET
    │
    ▼
┌─────────────────────────────────────┐
│  Reverse Proxy (nginx/Caddy)        │  ← TLS termination
│  - HTTPS                            │
│  - Rate limiting                    │
│  - Auth (optional)                  │
└──────────────┬──────────────────────┘
               │
               ▼
┌─────────────────────────────────────┐
│  ZK-Collector (LAN ONLY)            │
│  - Port 8080 (HTTP)                 │
│  - NO direct internet exposure      │
└──────────────┬──────────────────────┘
               │
       ┌───────┴───────┐
       ▼               ▼
   Port 4370       Port 443
   (ZKTeco)        (Platform)
   LAN ONLY        OUTBOUND
```

**Key Principle:** Port 4370 **never** exposed to internet. ZKTeco devices have no encryption/auth on this port.

---

## Failure Modes & Resilience

| Failure | Detection | Recovery |
|---------|-----------|----------|
| Device unreachable | Poll timeout/error | Retry next cycle, alert if persistent |
| Network partition | Sync fails | Buffer stores locally, sync when restored |
| Platform down | HTTP 5xx/timeout | Exponential backoff, max retries |
| Disk full | Health monitor alert | Auto-cleanup old synced records |
| Collector crash | systemd/docker restart | Auto-restart, resume from buffer |
| Power loss | N/A | SQLite WAL ensures consistency |

---

## Scaling Considerations

| Metric | Limit | Mitigation |
|--------|-------|------------|
| Devices per collector | ~20 | Deploy multiple collectors |
| Records in buffer | 10,000 (configurable) | Increase `max_records`, faster sync |
| Poll interval | ≥60s | Don't go below (device limits) |
| Sync batch size | 1000 records | Configurable, platform-dependent |

---

## Technology Stack Summary

| Layer | Technology | Version |
|-------|------------|---------|
| Language | Python | 3.12+ |
| Device Protocol | pyzk | 0.9.0+ |
| Web Framework | Flask | 3.1+ |
| Auth | Flask-Login + Argon2id | 0.6.3+ |
| Database | SQLite | 3.x (WAL mode) |
| HTTP Client | requests | 2.32+ |
| Encryption | cryptography (Fernet) | 44.0+ |
| Process Manager | Gunicorn | 23.0+ |
| Container | Docker | 24+ |
| Orchestration | docker-compose | v3.8 |

---

*Last updated: 2026-01-15*
*Version: 1.0.0*
