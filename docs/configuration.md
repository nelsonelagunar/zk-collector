# Configuration Reference

ZK-Collector is configured via environment variables and YAML files. This document covers all available options.

## Environment Variables

### Required

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `ZK_ADMIN_PASSWORD` | Initial admin password for web dashboard | `SecurePass123!` | *(none — must be set)* |

### Optional

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `CONFIG_PATH` | Path to devices YAML config file | `/app/configs/devices.yaml` | `/etc/attendance/collector.yaml` |
| `DATA_DIR` | SQLite database directory | `/app/data` | `/opt/attendance/data` |
| `LOG_DIR` | Log file directory | `/var/log/attendance` | `/var/log/attendance` |
| `WEBGUI_SECRET_KEY` | Flask session secret key | `your-32-char-hex-string` | Random hex (auto-generated) |
| `FERNET_KEY` | Encryption key for sensitive config values | `gAAAAAB...` | *(none — plain text in YAML)* |
| `DEBUG` | Enable debug mode | `true` / `false` | `false` |
| `LOG_LEVEL` | Logging verbosity | `DEBUG` / `INFO` / `WARNING` / `ERROR` | `INFO` |

### Platform Integration (Optional)

| Variable | Description | Example | Default |
|----------|-------------|---------|---------|
| `PLATFORM_URL` | Cloud sync API endpoint | `https://api.example.com` | *(none)* |
| `PLATFORM_API_KEY` | API key for cloud platform | `your-api-key` | *(none — plain text in YAML)* |
| `TENANT_ID` | Tenant identifier for multi-tenant sync | `tenant-001` | *(none)* |
| `SYNC_INTERVAL` | Seconds between sync attempts | `60` | `60` |

---

## Configuration Files

### devices.yaml

Device configuration file. Path set via `CONFIG_PATH` environment variable.

#### Complete Example with All Options

```yaml
# ZK-Collector Device Configuration
# Location: (as set by CONFIG_PATH, default /etc/attendance/collector.yaml)

# --- Platform Integration (Optional) ---
platform:
  url: "https://api.example.com"           # Cloud platform API URL
  api_key: "your-api-key-here"             # API key (or use env var PLATFORM_API_KEY)
  tenant_id: "tenant-001"                  # Multi-tenant identifier
  timeout: 30                              # API timeout in seconds
  retry_attempts: 3                        # Number of retry attempts

# --- Devices (Required) ---
devices:
  # Device 1: Main Entrance (K40)
  - ip: "192.168.1.101"                    # Device IP address
    port: 4370                             # Device port (4370 default)
    timeout: 5                             # Connection timeout (seconds)
    password: 0                            # Device comm key (usually 0)
    name: "Main Entrance"                  # Human-readable name
    location: "Building A - Lobby"         # Physical location (optional)
    zone: "Zone A"                         # Logical zone (optional)
    protocol: "tcp"                        # tcp or udp
    enabled: true                          # Enable/disable polling

  # Device 2: Emergency Exit (U160)
  - ip: "192.168.1.102"
    port: 4370
    timeout: 5
    password: 0
    name: "Emergency Exit"
    location: "Building A - Emergency"
    zone: "Zone A"
    protocol: "tcp"
    enabled: true

  # Device 3: Warehouse (Disabled temporarily)
  - ip: "192.168.1.103"
    port: 4370
    timeout: 5
    password: 0
    name: "Warehouse"
    location: "Building B"
    zone: "Zone B"
    protocol: "udp"                        # UDP for this one
    enabled: false                         # Currently disabled

# --- Collector Settings ---
poll_interval_seconds: 300                 # Device poll interval (60-3600)
sync_interval_seconds: 60                  # Cloud sync interval (10-600)

# --- Buffer Settings ---/buffer
buffer:
  max_records: 10000                       # Max records in SQLite buffer (min 100)
  cleanup_days: 30                         # Delete synced records older than X days

# --- Logging Settings ---
logging:
  level: "INFO"                            # DEBUG, INFO, WARNING, ERROR
  max_size_mb: 10                          # Max log file size in MB
  backup_count: 5                          # Number of rotated log files to keep

```

#### Field Reference

##### platform (Optional)

| Field | Type | Required | Description | Example |
|-------|------|----------|-------------|---------|
| `url` | string | ⚠️ if using sync | Platform API URL | `https://api.mycompany.com` |
| `api_key` | string | ⚠️ if using sync | API authentication key | `sk_live_123abc` |
| `tenant_id` | string | ⚠️ if using sync | Tenant identifier | `tenant-123` |
| `timeout` | integer | ❌ | API request timeout (seconds) | `30` |
| `retry_attempts` | integer | ❌ | Failed request retry count | `3` |

##### devices (Required)

Each device in the array supports these fields:

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `ip` | string | ✅ | — | Device IP address (IPv4) |
| `port` | integer | ❌ | `4370` | Device TCP/UDP port |
| `timeout` | integer | ❌ | `5` | Connection timeout in seconds |
| `password` | integer | ❌ | `0` | Device comm key (usually 0) |
| `name` | string | ✅ | — | Human-readable device name |
| `location` | string | ❌ | `""` | Physical location of device |
| `zone` | string | ❌ | `""` | Logical zone/group |
| `protocol` | string | ❌ | `"tcp"` | `tcp` or `udp` |
| `enabled` | boolean | ❌ | `true` | Enable/disable polling |

##### poll_interval_seconds

| Type | Range | Default |
|------|-------|---------|
| integer | 60-3600 | 300 |

Time between polls of each device. Shorter = more responsive, more network traffic.

##### sync_interval_seconds

| Type | Range | Default |
|------|-------|---------|
| integer | 10-600 | 60 |

Time between cloud sync attempts. Only applies if `platform.url` is configured.

##### buffer

| Field | Type | Default |
|-------|------|---------|
| `max_records` | integer | 10000 |
| `cleanup_days` | integer | 30 |

Controls SQLite buffer retention. Old synced records are deleted after `cleanup_days`.

##### logging

| Field | Type | Default | Allowed Values |
|-------|------|---------|----------------|
| `level` | string | `INFO` | `DEBUG`, `INFO`, `WARNING`, `ERROR` |
| `max_size_mb` | integer | 10 | — |
| `backup_count` | integer | 5 | — |

---

## Examples

### Minimal Configuration (Docker)

```yaml
devices:
  - ip: "192.168.1.101"
    port: 4370
    name: "Main Door"
```

Set admin password via environment variable:
```bash
docker run -d -p 8080:8080 -v zk-data:/app/data \
  -e ZK_ADMIN_PASSWORD=mysecret \
  ghcr.io/nelsonelagunar/zk-collector:latest
```

### High-Traffic Configuration (Short Polling)

```yaml
devices:
  - ip: "192.168.1.101"
    name: "Main Entrance"
    timeout: 10
  - ip: "192.168.1.102"
    name: "Side Entrance"
    timeout: 10

poll_interval_seconds: 60        # Fast polling
sync_interval_seconds: 30        # Fast sync
buffer:
  max_records: 50000             # Larger buffer
logging:
  level: "DEBUG"                 # More logging for debugging
```

### Multi-Site Configuration

```yaml
devices:
  # Site A
  - ip: "10.0.1.101"
    name: "Site A - Front Desk"
    location: "HQ Building"
    zone: "Site A"
  - ip: "10.0.1.102"
    name: "Site A - Server Room"
    location: "HQ Building"
    zone: "Site A"
  
  # Site B
  - ip: "10.0.2.101"
    name: "Site B - Main"
    location: "Branch Office"
    zone: "Site B"
    protocol: "udp"              # Different protocol for this site

platform:
  url: "https://central.hq.com/api"
  api_key: "<<encrypted-api-key>>"
  tenant_id: "multi-site-001"

sync_interval_seconds: 120       # Longer interval for multi-site
```

---

## Validation Schema

Configuration is validated against `configs/collector.schema.json`. Common validation errors:

| Error | Cause | Solution |
|-------|-------|----------|
| `platform.url debe ser una URL válida` | Malformed URL | Use `http://` or `https://` prefix |
| `platform.api_key is required` | Missing API key with platform configured | Add `api_key` to platform section |
| `Al menos un dispositivo debe estar configurado` | No devices configured | Add at least one `devices:` entry |
| `IP inválida` | Invalid IP format | Use valid IPv4 like `192.168.1.101` |

---

## Security Considerations

### Sensitive Values

**Never** put real passwords/secrets in `devices.yaml` versioned in git. Use environment variables:

```bash
# Good: env var
docker run -e PLATFORM_API_KEY=$REAL_API_KEY ...

# Bad: in config
api_key: "sk_live_123abc"  # Don't do this!
```

### Encryption

For extra security, encrypt sensitive values with Fernet:

1. **Generate key**: `python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"`
2. **Set env var**: `-e FERNET_KEY=your-generated-key`
3. **Encrypt values**: Use the encryption script in `scripts/encrypt_config.py`
4. **In config**: Replace plain text with encrypted strings

Example with encryption:
```yaml
platform:
  api_key: "gAAAAAB..."    # Fernet-encrypted value
```

### Network Security

- Port 4370 (ZK devices) **MUST NOT** be exposed to internet
- Port 8080 (Web GUI) **MUST** be protected (firewall/VPN/Tailscale)
- Use reverse proxy (nginx, Caddy) with HTTPS for production

---

## Running with Docker Compose

### Full Example (uses project's docker-compose.yml)

```bash
# The project includes a docker-compose.yml - just configure .env and run:
cp .env.example .env
# Edit .env with your values
nano .env
docker-compose up -d
```

### Custom docker-compose.yml (if needed)

```yaml
version: '3.8'

services:
  zk-collector:
    build: .
    container_name: zk-collector
    restart: unless-stopped
    ports:
      - "8080:8080"
    volumes:
      - zk-data:/app/data
      - ./configs:/app/configs:ro
    environment:
      # Required
      - ZK_ADMIN_PASSWORD=${ZK_ADMIN_PASSWORD}
      - ENCRYPTION_KEY=${ENCRYPTION_KEY}
      # Optional cloud sync
      - ZK_SYNC_URL=${ZK_SYNC_URL}
      - ZK_SYNC_TOKEN=${ZK_SYNC_TOKEN}
      # Optional
      - LOG_LEVEL=${LOG_LEVEL:-INFO}
      - LOG_FORMAT=${LOG_FORMAT:-text}
      - WEBGUI_SECRET_KEY=${WEBGUI_SECRET_KEY}
    entrypoint: ["/app/docker-entrypoint.sh"]
    # Native HEALTHCHECK from Dockerfile (interval=30s, timeout=5s, retries=3)

volumes:
  zk-data:
```

### .env file (from .env.example)

```bash
# Copy .env.example to .env and fill in your values
# .env (add to .gitignore!)
ZK_ADMIN_PASSWORD=SecurePassword123!
ENCRYPTION_KEY=gAAAAABl8...  # Generate with: python -m src.security.encryption generate-key
ZK_SYNC_URL=https://api.example.com
ZK_SYNC_TOKEN=eyJhbGciOiJIUzI1NiIs...
LOG_LEVEL=INFO
LOG_FORMAT=text
WEBGUI_SECRET_KEY=your-32-char-hex-string
```

---

## Testing Configuration

### Validate YAML Syntax

```bash
python3 -c "import yaml; yaml.safe_load(open('configs/devices.yaml'))"
```

### Check Startup Logs

```bash
# Docker
docker logs zk-collector --tail 50

# Bare metal
tail -f /var/log/attendance/collector.log

# Or use built-in test
zk-collector --validate-config configs/devices.yaml
```

### Dry Run (Best for Testing)

```bash
# Test without connecting to devices
zk-collector --config configs/devices.yaml --dry-run
```

---

## Common Configuration Changes

| Task | File to Edit | Field |
|------|--------------|-------|
| Change admin password | Environment | `ZK_ADMIN_PASSWORD` |
| Add new device | `devices.yaml` | Add to `devices:` array |
| Change poll frequency | `devices.yaml` | `poll_interval_seconds` |
| Enable debug logging | `devices.yaml` | `logging.level: DEBUG` |
| Change web port | Env var | `PORT=9000` (if supported) |
| Disable cloud sync | `devices.yaml` | Remove `platform:` section |

---

## Troubleshooting

| Issue | Check | Solution |
|-------|-------|----------|
| "Config file not found" | `CONFIG_PATH` env var | Set to correct YAML path |
| "Missing platform.url" | Contains platform section | Add `url:` under `platform:` |
| "No devices configured" | `devices:` array exists | Add at least one device |
| "Invalid IP" | IP format in YAML | Use quoted string: `"192.168.1.1"` |
| Can't login | Password env set | Recheck `ZK_ADMIN_PASSWORD` |
| Dashboard not loading | Port 8080 open | Check firewall, port mapping |

---

*Configuration version: 1.0.0*
*Last updated: $(date +%Y-%m-%d)*
