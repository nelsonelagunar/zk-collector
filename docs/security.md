# Security Hardening Guide

Security best practices for deploying ZK-Collector in production environments.

---

## Threat Model

### Assets to Protect
1. **Attendance data** — Employee PII (user IDs, timestamps, biometric verification)
2. **Device credentials** — ZKTeco communication passwords
3. **Platform API keys** — Cloud sync authentication
4. **Admin credentials** — Web dashboard access

### Attack Vectors
| Vector | Risk | Mitigation |
|--------|------|------------|
| ZKTeco port 4370 exposure | **CRITICAL** — No encryption, no auth on device protocol | **Never expose to internet**, LAN only |
| Web dashboard exposure | **HIGH** — Admin access, data export | Reverse proxy + TLS + IP restriction |
| Config file secrets | **HIGH** — API keys, passwords | Environment variables + Fernet encryption |
| SQLite databases | **MEDIUM** — Local data access | File permissions, encryption at rest (LUKS) |
| Network sniffing | **MEDIUM** — Unencrypted HTTP | TLS termination at reverse proxy |

---

## Network Security

### ✅ Mandatory: LAN-Only for Port 4370

```
┌─────────────────────────────────────────────────────────────┐
│                      CORRECT                                 │
│  Internet                                                    │
│     │                                                        │
│     ▼                                                        │
│  ┌─────────┐     ┌──────────────┐     ┌──────────────┐     │
│  │ Firewall│────▶│ Reverse Proxy│────▶│ ZK-Collector │     │
│  │ (443)   │     │ (8080/HTTPS) │     │  (8080/HTTP) │     │
│  └─────────┘     └──────────────┘     └──────┬───────┘     │
│                                               │             │
│                              ┌────────────────┴────────┐    │
│                              │      LAN (VLAN)         │    │
│                              │  ┌──────────────────┐  │    │
│                              │  │ ZKTeco Device    │  │    │
│                              │  │ 192.168.1.101:4370│  │    │
│                              │  └──────────────────┘  │    │
│                              └───────────────────────┘    │
└─────────────────────────────────────────────────────────────┘

┌─────────────────────────────────────────────────────────────┐
│                      WRONG (NEVER DO THIS)                  │
│  Internet                                                    │
│     │                                                        │
│     ▼                                                        │
│  ┌──────────────┐                                           │
│  │ ZK-Collector │  ← Port 4370 EXPOSED!                    │
│  │ :4370        │                                           │
│  └──────────────┘                                           │
└─────────────────────────────────────────────────────────────┘
```

**Rule:** ZKTeco protocol (port 4370) has **no encryption, no authentication**. It must **never** traverse untrusted networks.

### Firewall Rules

```bash
# On collector host (ufw example)

# 1. Web dashboard - restrict to admin networks
sudo ufw allow from 10.0.0.0/8 to any port 8080 proto tcp
sudo ufw allow from 192.168.0.0/16 to any port 8080 proto tcp
# sudo ufw allow from YOUR_VPN_SUBNET to any port 8080 proto tcp

# 2. Outbound to ZKTeco devices (specific IPs only)
sudo ufw allow out to 192.168.1.101 port 4370 proto tcp
sudo ufw allow out to 192.168.1.102 port 4370 proto tcp
# Add each device IP explicitly

# 3. Outbound HTTPS for cloud sync
sudo ufw allow out 443 proto tcp

# 4. Deny all other inbound
sudo ufw default deny incoming
sudo ufw default allow outgoing
sudo ufw enable
```

### Tailscale (Recommended for Remote Admin)

```bash
# Install Tailscale on collector host
curl -fsSL https://tailscale.com/install.sh | sh
sudo tailscale up

# Allow Tailscale subnet to access dashboard
sudo ufw allow in on tailscale0 to any port 8080

# Now access via: http://<tailscale-ip>:8080
# No port forwarding, no public IP needed
```

### Reverse Proxy with TLS (Production)

**nginx Example:**
```nginx
# /etc/nginx/sites-available/zk-collector
server {
    listen 443 ssl http2;
    server_name attendance.yourdomain.com;

    ssl_certificate /etc/letsencrypt/live/attendance.yourdomain.com/fullchain.pem;
    ssl_certificate_key /etc/letsencrypt/live/attendance.yourdomain.com/privkey.pem;
    
    # Security headers
    add_header X-Frame-Options "SAMEORIGIN";
    add_header X-Content-Type-Options "nosniff";
    add_header X-XSS-Protection "1; mode=block";
    add_header Referrer-Policy "strict-origin-when-cross-origin";

    # Rate limiting
    limit_req_zone $binary_remote_addr zone=api:10m rate=10r/s;
    limit_req zone=api burst=20 nodelay;

    location / {
        proxy_pass http://127.0.0.1:8080;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
        proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
        proxy_set_header X-Forwarded-Proto $scheme;
        
        # WebSocket support (if needed)
        proxy_http_version 1.1;
        proxy_set_header Upgrade $http_upgrade;
        proxy_set_header Connection "upgrade";
    }

    # Health check - no rate limit
    location /health {
        proxy_pass http://127.0.0.1:8080/health;
        limit_req zone=api burst=100 nodelay;
    }
}

# Redirect HTTP to HTTPS
server {
    listen 80;
    server_name attendance.yourdomain.com;
    return 301 https://$server_name$request_uri;
}
```

**Caddy Example (Simpler, Auto-TLS):**
```caddy
# /etc/caddy/Caddyfile
attendance.yourdomain.com {
    reverse_proxy 127.0.0.1:8080
    
    # Rate limiting
    ratelimit {
        zone api 10m
        rate 10r/s
        burst 20
    }
    
    # Security headers
    header {
        X-Frame-Options "SAMEORIGIN"
        X-Content-Type-Options "nosniff"
    }
}
```

---

## Secrets Management

### ❌ Never Commit Secrets

```yaml
# BAD - devices.yaml committed to git
platform:
  api_key: "sk_live_abc123..."  # NEVER DO THIS
```

### ✅ Use Environment Variables

```yaml
# GOOD - devices.yaml (committed)
platform:
  url: "https://api.example.com"
  api_key: ""  # Empty, loaded from env
  tenant_id: "tenant-001"
```

```bash
# .env file (NOT committed, in .gitignore)
ZK_ADMIN_PASSWORD=SecurePass123!
PLATFORM_API_KEY=sk_live_actual_key_here
TENANT_ID=tenant-001
FERNET_KEY=gAAAAAB...  # For config encryption
```

```yaml
# docker-compose.yml
services:
  zk-collector:
    env_file: .env
    environment:
      - ZK_ADMIN_PASSWORD=${ZK_ADMIN_PASSWORD}
      - PLATFORM_API_KEY=${PLATFORM_API_KEY}
      - FERNET_KEY=${FERNET_KEY}
```

### ✅ Fernet Encryption for Config Values

For extra security, encrypt sensitive config values:

**1. Generate Key:**
```bash
python3 -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
# Output: gAAAAAB... (save this as FERNET_KEY env var)
```

**2. Encrypt Values:**
```python
# scripts/encrypt_value.py
import os
from cryptography.fernet import Fernet

key = os.environ['FERNET_KEY']
fernet = Fernet(key.encode())

value = "sk_live_actual_api_key_here"
encrypted = fernet.encrypt(value.encode()).decode()
print(f"Encrypted: {encrypted}")
```

**3. Use in Config:**
```yaml
platform:
  api_key: "gAAAAABh...encrypted_value..."  # Encrypted
```

**4. Decryption at Runtime:**
```python
# In config loader
from src.security.encryption import decrypt_config_value

api_key = decrypt_config_value(config['platform']['api_key'])
```

### Docker Secrets (Swarm/Kubernetes)

```yaml
# docker-compose.yml with secrets
services:
  zk-collector:
    secrets:
      - platform_api_key
      - fernet_key
      - admin_password
    environment:
      - PLATFORM_API_KEY_FILE=/run/secrets/platform_api_key
      - FERNET_KEY_FILE=/run/secrets/fernet_key
      - ZK_ADMIN_PASSWORD_FILE=/run/secrets/admin_password

secrets:
  platform_api_key:
    file: ./secrets/platform_api_key.txt
  fernet_key:
    file: ./secrets/fernet_key.txt
  admin_password:
    file: ./secrets/admin_password.txt
```

---

## File Permissions

### SQLite Databases

```bash
# Data directory permissions
sudo chown -R zkcollector:zkcollector /opt/attendance/data
sudo chmod 750 /opt/attendance/data
sudo chmod 640 /opt/attendance/data/*.db

# Log directory
sudo chown -R zkcollector:zkcollector /var/log/attendance
sudo chmod 750 /var/log/attendance
```

### Config Files

```bash
# Config directory (read-only for collector)
sudo chown -R root:zkcollector /etc/attendance
sudo chmod 750 /etc/attendance
sudo chmod 640 /etc/attendance/collector.yaml
```

### Systemd Service Hardening

```ini
# /etc/systemd/system/zk-collector.service
[Unit]
Description=ZK-Collector Attendance Service
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=zkcollector
Group=zkcollector
WorkingDirectory=/opt/attendance

# Security hardening
NoNewPrivileges=yes
PrivateTmp=yes
ProtectSystem=strict
ProtectHome=yes
ReadWritePaths=/opt/attendance/data /var/log/attendance
ProtectKernelTunables=yes
ProtectKernelModules=yes
ProtectControlGroups=yes
RestrictNamespaces=yes
LockPersonality=yes
MemoryDenyWriteExecute=yes
RestrictRealtime=yes
RestrictSUIDSGID=yes

# Environment
EnvironmentFile=/etc/attendance/collector.env
ExecStart=/usr/local/bin/zk-collector --config /etc/attendance/collector.yaml

# Restart policy
Restart=on-failure
RestartSec=10
StartLimitInterval=60
StartLimitBurst=3

[Install]
WantedBy=multi-user.target
```

---

## Application Security

### Web Dashboard

**Session Security:**
```python
# src/webgui/server.py - already configured
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_SECURE"] = True  # Only with HTTPS
app.config["PERMANENT_SESSION_LIFETIME"] = timedelta(hours=8)
```

**Password Hashing (Argon2id):**
```python
# src/webgui/auth.py - uses argon2
from argon2 import PasswordHasher
ph = PasswordHasher()
hash = ph.hash(password)  # Argon2id with secure defaults
ph.verify(hash, password)  # Constant-time verification
```

**Rate Limiting:**
```python
# Add to Flask app
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address

limiter = Limiter(
    get_remote_address,
    app=app,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

# On auth endpoints
@app.route("/auth/login", methods=["POST"])
@limiter.limit("5 per minute")
def login():
    ...
```

### RBAC: Roles y Permisos (ADR-001)

Authorization is enforced by role (RBAC) on every route, via the
`require()` / `api_require()` decorators (`src/webgui/middleware/auth.py`).
Roles are a closed catalog (`src/webgui/permissions.py` — `ALLOWED_ROLES`);
legacy values are normalized to `auditor` by `migrations/008_rbac_roles.sql`.
Unknown roles deny everything (fail-closed).

| Rol | Alcance |
|---|---|
| `admin` | Control total: usuarios, dispositivos, configuración, datos |
| `rrhh` | ABC de colaboradores, incapacidades y reportes |
| `supervisor` | Lectura de asistencia y reportes |
| `auditor` | Solo lectura: reportes y logs |

Permission matrix (`recurso:acción`, `has_permission(role, perm)`):

| Permiso | admin | rrhh | supervisor | auditor |
|---|:--:|:--:|:--:|:--:|
| devices:read / write / sync | ✅ | ❌ | ❌ | ❌ |
| employees:read / write | ✅ | ✅ | read | read |
| medical_leaves:read / write | ✅ | ✅ | read | read |
| attendance:read, reports:read / export | ✅ | ✅ | ✅ | ✅ |
| users:manage, settings:manage | ✅ | ❌ | ❌ | ❌ |
| audit:read | ✅ | ❌ | ❌ | ✅ |

**Role-change semantics:** the role is taken from the credential (session
claim or JWT claim), not re-queried per request. A role change applies in
the WebGUI after **re-login** (session) and in the API when the access
token expires (**30 min** — `Auth.token_expiry_minutes`). Accept and
document this window; do not add per-request DB lookups.

**User management API** (`/api/users`, requires `users:manage`, MYK-415):

- Full CRUD contract in `docs/openapi.yaml` (schemas `User`/`UserInput`/`UserPatch`,
  401/403 documented).
- Role validated against `ALLOWED_ROLES` on every write path; passwords hashed
  with Argon2id and checked by `Auth.validate_password_strength`.
- `DELETE` is a soft delete (`is_active = 0`); rows are never removed.
- **Last-admin rule:** the last active `admin` can never be demoted or
  deactivated (PATCH and DELETE return `409`), and a caller cannot deactivate
  their own account — prevents lockout of the appliance.

### Input Validation

All API endpoints validate input:
- Device IPs: IPv4 format validation
- Port numbers: 1-65535 range
- Pagination: max limit 1000
- Date formats: ISO 8601

### CORS Policy

```python
# Restrict to known origins
from flask_cors import CORS

CORS(app, origins=[
    "https://attendance.yourdomain.com",
    "http://localhost:8080"  # dev only
])
```

---

## Encryption at Rest

### Option 1: LUKS Full Disk Encryption (Recommended)

```bash
# Encrypt data partition
sudo cryptsetup luksFormat /dev/sdX1
sudo cryptsetup open /dev/sdX1 attendance-data
sudo mkfs.ext4 /dev/mapper/attendance-data
sudo mount /dev/mapper/attendance-data /opt/attendance/data

# Auto-mount on boot (/etc/crypttab + /etc/fstab)
```

### Option 2: fscrypt (File-Level)

```bash
# Enable fscrypt on ext4
sudo apt install fscrypt
sudo fscrypt setup /opt/attendance/data
sudo fscrypt encrypt /opt/attendance/data --user=zkcollector
```

### Option 3: Application-Level (Fernet)

For specific sensitive fields in database:
```python
# Encrypt PII before storing
from src.security.encryption import encrypt_value, decrypt_value

encrypted_user_id = encrypt_value(user_id, FERNET_KEY)
# Store encrypted_user_id in DB
```

---

## Audit & Monitoring

### Log Security Events

```python
# Security-relevant events to log
SECURITY_EVENTS = [
    "login_success",
    "login_failure",
    "password_change",
    "device_added",
    "device_removed",
    "config_changed",
    "sync_failure",
    "export_requested",
]

# Structured logging
logger.info("security_event", extra={
    "event": "login_failure",
    "username": username,
    "ip": request.remote_addr,
    "user_agent": request.user_agent.string,
})
```

### Log Retention

```bash
# /etc/logrotate.d/zk-collector
/var/log/attendance/*.log {
    daily
    rotate 30
    compress
    delaycompress
    missingok
    notifempty
    create 640 zkcollector zkcollector
    sharedscripts
    postrotate
        systemctl reload zk-collector > /dev/null 2>&1 || true
    endscript
}
```

### Health Check Endpoint

```bash
# Monitor this endpoint
curl -f https://attendance.yourdomain.com/health
# Returns 200 OK with {"status": "healthy", "version": "1.0.0"}

# Detailed health (requires auth)
curl -b cookies.txt https://attendance.yourdomain.com/devices/api/sync/status
```

---

## Compliance Considerations

### GDPR / Mexico LFPDPPP

| Requirement | Implementation |
|-------------|----------------|
| Data minimization | Only collect: user_id, timestamp, punch_type |
| Right to access | API: `/devices/api/attendance?user_id=X` |
| Right to erasure | `DELETE /devices/api/attendance/{id}` (add endpoint) |
| Data portability | CSV export: `/devices/api/attendance/export` |
| Encryption in transit | TLS via reverse proxy |
| Encryption at rest | LUKS + Fernet for sensitive fields |
| Access logs | Structured logging with user/IP |

### Data Retention Policy

LFT 804-III (MYK-419): attendance records are kept >= 24 months (730 days).
There is NO automatic deletion. Deletion is manual-only and always audited:

```yaml
# In devices.yaml
buffer:
  max_records: 10000
  retention_days: 730  # Min days to KEEP records (LFT 804-III)
```

```python
# Manual purge (the only sanctioned deletion path) — leaves a
# retention_audit bitácora entry; never deletes unsynced records.
repo.purge_synced_older_than(days=730, reason="annual archive", operator="admin")
```

Never run raw `DELETE` against `attendance_records` outside this API —
unlogged deletions are a legal risk (LFT 805: failure to exhibit records
creates a presumption against the employer).

---

## Incident Response

### Compromise Checklist

1. **Immediate:**
   - Block collector internet access (keep LAN for devices)
   - Rotate all credentials (admin, API keys, Fernet key)
   - Check logs for unauthorized access

2. **Investigate:**
   ```bash
   # Check for unusual access
   grep "login_failure" /var/log/attendance/collector.log
   grep "export_requested" /var/log/attendance/collector.log
   
   # Check database integrity
   sqlite3 /opt/attendance/data/buffer.db ".schema"
   ```

3. **Recover:**
   - Restore from known-good backup
   - Re-deploy with new secrets
   - Verify device connections

---

## Security Checklist (Pre-Deploy)

- [ ] Port 4370 NOT exposed to internet
- [ ] Web dashboard behind reverse proxy with TLS
- [ ] Dashboard access restricted (IP allowlist / Tailscale / VPN)
- [ ] All secrets in environment variables (not config files)
- [ ] Fernet encryption for sensitive config values
- [ ] Strong admin password (20+ chars, random)
- [ ] Systemd hardening enabled (NoNewPrivileges, PrivateTmp, etc.)
- [ ] File permissions: 750 dirs, 640 files, owned by service user
- [ ] Log rotation configured
- [ ] Health monitoring alerting configured
- [ ] Backup strategy tested (SQLite dumps)
- [ ] Incident response plan documented

---

## Reporting Security Issues

**Do NOT** open public issues for security vulnerabilities.

Email: security@zk-collector.dev (or use GitHub Security Advisories)

Include:
- Description of vulnerability
- Steps to reproduce
- Impact assessment
- Suggested fix (if any)

---

*Last updated: 2026-10-27*
*Version: 1.1.0*
